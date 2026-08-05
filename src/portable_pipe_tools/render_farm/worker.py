from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
import sys
import time
from typing import TypeVar

from portable_pipe_tools.render_farm.git_sync import (
    GIT_PULL_LOG_FILENAME,
    GitPullResult,
    pull_latest_branch,
    write_git_pull_log,
)
from portable_pipe_tools.render_farm.dropbox_coordination import (
    DropboxJobClaim,
    DropboxJobCoordinator,
)
from portable_pipe_tools.render_farm.filesystem_coordination import (
    DEFAULT_CLAIM_SETTLE_SECONDS,
    DEFAULT_ELECTION_VERIFY_SECONDS,
    DEFAULT_INITIAL_JITTER_SECONDS,
    DEFAULT_POST_CLAIM_VERIFY_SECONDS,
    FilesystemCoordinationError,
    FilesystemJobClaim,
    FilesystemJobCoordinator,
)
from portable_pipe_tools.render_farm.queue import (
    JOB_FILENAME,
    QueuePaths,
    claim_job_candidate,
    create_queue_folders,
    default_worker_name,
    fail_unreadable_claimed_job,
    finish_claimed_job,
    list_job_candidates,
    mark_job_rendering,
    read_json_object,
    safe_name,
    utc_now,
    write_json_atomic,
)
from portable_pipe_tools.render_farm.unreal_runner import (
    DEFAULT_RENDER_TIMEOUT_SECONDS,
    UnrealExecutionResult,
    execute_unreal_job,
    resolve_unreal_project,
)


LOGGER = logging.getLogger("render_worker")
DEFAULT_MINIMUM_STAGE_SECONDS = 5.0
_StageResult = TypeVar("_StageResult")


class WorkerStage(str, Enum):
    STOPPED = "stopped"
    WAITING = "waiting"
    MOVING = "moving"
    RENDERING = "rendering"
    FINISHING = "finishing"


WORKER_STAGE_LABELS: dict[WorkerStage, str] = {
    WorkerStage.STOPPED: "Worker stopped",
    WorkerStage.WAITING: "Waiting to find a job",
    WorkerStage.MOVING: "Moving files and claiming the job",
    WorkerStage.RENDERING: "Rendering",
    WorkerStage.FINISHING: "Finishing render tasks",
}

StageCallback = Callable[[WorkerStage], None]
JobCallback = Callable[[dict], None]
GitSyncCallback = Callable[[Path], GitPullResult]


@dataclass(frozen=True)
class WorkerResult:
    status: str
    final_folder: Path
    reason: str


@dataclass(frozen=True)
class _ClaimedJob:
    folder: Path
    job: dict | None
    failure_reason: str | None = None


def _git_project_directory_for_candidate(
    candidate_folder: Path,
    local_uproject: str | Path | None,
) -> Path | None:
    try:
        preview_job = read_json_object(candidate_folder / JOB_FILENAME)
    except (OSError, ValueError) as error:
        LOGGER.warning(
            "Skipping Git preflight for unreadable queued job %s; it will be "
            "claimed and failed normally. Error: %s",
            candidate_folder,
            error,
        )
        return None

    uproject = resolve_unreal_project(preview_job, local_uproject)
    return uproject.parent


def _record_git_pull(
    claimed_folder: Path,
    job: dict,
    result: GitPullResult,
) -> None:
    job["worker_sync_policy"] = "latest_branch_git_pull_ff_only"
    job["git_sync_status"] = "success"
    job["git_branch"] = result.branch
    job["git_upstream"] = result.upstream
    job["git_commit_before_pull"] = result.commit_before
    job["git_commit_after_pull"] = result.commit_after
    job["git_pull_summary"] = result.summary
    job["git_pull_completed_utc"] = utc_now()
    job["rendered_git_commit"] = result.commit_after
    write_git_pull_log(claimed_folder / GIT_PULL_LOG_FILENAME, result)
    write_json_atomic(claimed_folder / JOB_FILENAME, job)

    submitted_commit = str(job.get("submitted_git_commit") or "").strip()
    if submitted_commit and submitted_commit.casefold() != result.commit_after.casefold():
        LOGGER.info(
            "Latest-branch policy selected: submitted commit=%s, pulled commit=%s",
            submitted_commit,
            result.commit_after,
        )


def _run_stage(
    stage: WorkerStage,
    operation: Callable[[], _StageResult],
    minimum_stage_seconds: float,
    stage_callback: StageCallback | None,
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
) -> _StageResult:
    started_at = monotonic()
    LOGGER.info("Stage: %s", WORKER_STAGE_LABELS[stage])
    try:
        if stage_callback is not None:
            stage_callback(stage)
        return operation()
    finally:
        elapsed_seconds = monotonic() - started_at
        remaining_seconds = max(0.0, minimum_stage_seconds - elapsed_seconds)
        if remaining_seconds > 0:
            sleep(remaining_seconds)


def run_once(
    farm_root: str | Path,
    worker_name: str,
    simulate_success: bool,
    minimum_stage_seconds: float = DEFAULT_MINIMUM_STAGE_SECONDS,
    stage_callback: StageCallback | None = None,
    sleep: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
    render_with_unreal: bool = False,
    unreal_editor_cmd: str | Path | None = None,
    render_timeout_seconds: float = DEFAULT_RENDER_TIMEOUT_SECONDS,
    unreal_runner: Callable[..., UnrealExecutionResult] | None = None,
    should_stop_before_claim: Callable[[], bool] | None = None,
    job_callback: JobCallback | None = None,
    local_uproject: str | Path | None = None,
    git_sync: GitSyncCallback | None = None,
    use_dropbox_api_sync: bool = False,
    dropbox_coordinator: DropboxJobCoordinator | None = None,
    filesystem_coordinator: FilesystemJobCoordinator | None = None,
    filesystem_coordination_delays: tuple[float, float, float, float] | None = None,
) -> WorkerResult | None:
    if minimum_stage_seconds < 0:
        raise ValueError("minimum_stage_seconds cannot be negative")

    sleep_function = sleep or time.sleep
    monotonic_function = monotonic or time.monotonic
    paths = create_queue_folders(farm_root)
    worker = safe_name(worker_name, "WORKER")
    selected_coordinator = (
        dropbox_coordinator
        if use_dropbox_api_sync
        else None
    )
    if use_dropbox_api_sync and selected_coordinator is None:
        selected_coordinator = DropboxJobCoordinator.from_environment(paths.root)
    selected_filesystem_coordinator = None
    if selected_coordinator is None:
        if filesystem_coordinator is not None:
            selected_filesystem_coordinator = filesystem_coordinator
        else:
            delays = filesystem_coordination_delays or (
                DEFAULT_INITIAL_JITTER_SECONDS,
                DEFAULT_CLAIM_SETTLE_SECONDS,
                DEFAULT_ELECTION_VERIFY_SECONDS,
                DEFAULT_POST_CLAIM_VERIFY_SECONDS,
            )
            if len(delays) != 4:
                raise ValueError(
                    "filesystem_coordination_delays must contain four values"
                )
            selected_filesystem_coordinator = FilesystemJobCoordinator(
                paths.root,
                initial_jitter_seconds=delays[0],
                claim_settle_seconds=delays[1],
                election_verify_seconds=delays[2],
                post_claim_verify_seconds=delays[3],
                sleep=sleep_function,
            )

    queued_candidates = _run_stage(
        stage=WorkerStage.WAITING,
        operation=lambda: list_job_candidates(paths, worker),
        minimum_stage_seconds=minimum_stage_seconds,
        stage_callback=stage_callback,
        sleep=sleep_function,
        monotonic=monotonic_function,
    )
    if not queued_candidates:
        LOGGER.info(
            "No queued jobs are eligible for worker %s: %s",
            worker,
            paths.needs_rendering,
        )
        return None

    if should_stop_before_claim is not None and should_stop_before_claim():
        LOGGER.info("Stop requested before claiming the next queued job.")
        return None

    selected_candidate = None
    api_claim: DropboxJobClaim | None = None
    filesystem_claim: FilesystemJobClaim | None = None
    if selected_coordinator is not None:
        for candidate in queued_candidates:
            try:
                preview_job = read_json_object(candidate.folder / JOB_FILENAME)
            except (OSError, ValueError):
                preview_job = {
                    "job_id": candidate.folder.name,
                    "blacklisted_workers": [],
                }
            if not str(preview_job.get("job_id") or "").strip():
                preview_job = dict(preview_job)
                preview_job["job_id"] = candidate.folder.name
            api_claim = selected_coordinator.try_claim(preview_job, worker)
            if api_claim is not None:
                selected_candidate = candidate
                LOGGER.info(
                    "Won Dropbox API claim for %s at generation %s",
                    api_claim.job_id,
                    api_claim.generation,
                )
                break
        if api_claim is None or selected_candidate is None:
            LOGGER.info(
                "No queued jobs have an available Dropbox API claim for %s.",
                worker,
            )
            return None
    else:
        assert selected_filesystem_coordinator is not None
        for candidate in queued_candidates:
            try:
                preview_job = read_json_object(candidate.folder / JOB_FILENAME)
            except (OSError, ValueError):
                preview_job = {
                    "job_id": candidate.folder.name,
                    "blacklisted_workers": [],
                }
            if not str(preview_job.get("job_id") or "").strip():
                preview_job = dict(preview_job)
                preview_job["job_id"] = candidate.folder.name
            try:
                filesystem_claim = selected_filesystem_coordinator.try_claim(
                    candidate.folder,
                    preview_job,
                    worker,
                )
            except FilesystemCoordinationError as error:
                LOGGER.error(
                    "Skipping ambiguous filesystem-coordinated job %s: %s",
                    candidate.folder,
                    error,
                )
                continue
            if filesystem_claim is not None:
                selected_candidate = candidate
                LOGGER.info(
                    "Won stabilized filesystem claim for %s attempt %s",
                    filesystem_claim.job_id,
                    filesystem_claim.attempt,
                )
                break
        if filesystem_claim is None or selected_candidate is None:
            LOGGER.info(
                "No queued jobs have a stable filesystem claim for %s.",
                worker,
            )
            return None

    git_pull_result: GitPullResult | None = None
    should_sync_git = render_with_unreal and (
        unreal_runner is None or git_sync is not None
    )
    if should_sync_git:
        project_directory = _git_project_directory_for_candidate(
            (
                selected_candidate.folder
                if selected_candidate is not None
                else queued_candidates[0].folder
            ),
            local_uproject,
        )
        if project_directory is not None:
            LOGGER.info(
                "Queued job found. Pulling the latest Git branch before claim: %s",
                project_directory,
            )
            sync_operation = git_sync or pull_latest_branch
            try:
                git_pull_result = sync_operation(project_directory)
            except Exception:
                if selected_coordinator is not None and api_claim is not None:
                    selected_coordinator.release_claim(
                        api_claim,
                        "Git preflight failed before the local job claim.",
                    )
                if (
                    selected_filesystem_coordinator is not None
                    and filesystem_claim is not None
                ):
                    selected_filesystem_coordinator.release_claim(
                        filesystem_claim,
                        "Git preflight failed before the local job claim.",
                    )
                raise

    def claim_and_prepare_job() -> _ClaimedJob | None:
        nonlocal api_claim
        if should_stop_before_claim is not None and should_stop_before_claim():
            LOGGER.info("Stop requested before claiming the next queued job.")
            if selected_coordinator is not None and api_claim is not None:
                selected_coordinator.release_claim(
                    api_claim,
                    "Worker stop requested before the local job claim.",
                )
            if (
                selected_filesystem_coordinator is not None
                and filesystem_claim is not None
            ):
                selected_filesystem_coordinator.release_claim(
                    filesystem_claim,
                    "Worker stop requested before the local job claim.",
                )
            return None
        if selected_coordinator is not None:
            assert api_claim is not None
            assert selected_candidate is not None
            api_claim = selected_coordinator.settle_and_verify(api_claim)

            # The API claim can arrive before Dropbox has synchronized the
            # requeued package from a previous failed attempt. Never render an
            # older local replica merely because its folder is visible.
            try:
                settled_job = read_json_object(
                    selected_candidate.folder / JOB_FILENAME
                )
            except (OSError, ValueError):
                settled_job = None
            if settled_job is not None:
                local_attempt = settled_job.get("attempt", 0)
                if (
                    isinstance(local_attempt, int)
                    and not isinstance(local_attempt, bool)
                    and local_attempt >= 0
                    and local_attempt != api_claim.attempt - 1
                ):
                    selected_coordinator.release_claim(
                        api_claim,
                        "The synchronized local package is from a stale attempt.",
                    )
                    LOGGER.info(
                        "Skipped stale local package for %s: local attempt=%s, "
                        "Dropbox claim attempt=%s",
                        api_claim.job_id,
                        local_attempt,
                        api_claim.attempt,
                    )
                    return None

            api_claim = selected_coordinator.mark_rendering(api_claim)
            claimed_folder = claim_job_candidate(
                paths,
                selected_candidate.folder,
                worker,
            )
            if claimed_folder is None:
                selected_coordinator.release_claim(
                    api_claim,
                    "The local queued package disappeared before its rename.",
                )
                return None
        else:
            assert selected_filesystem_coordinator is not None
            assert filesystem_claim is not None
            assert selected_candidate is not None
            claimed_folder = claim_job_candidate(
                paths,
                selected_candidate.folder,
                worker,
            )
            if claimed_folder is None:
                selected_filesystem_coordinator.release_claim(
                    filesystem_claim,
                    "The local queued package disappeared before its rename.",
                )
                return None
            selected_filesystem_coordinator.settle_after_local_claim(
                filesystem_claim
            )
        if claimed_folder is None:
            return None

        LOGGER.info("Claimed job: %s", claimed_folder)
        try:
            job = mark_job_rendering(claimed_folder, worker)
        except Exception as error:
            reason = (
                f"Claimed job is invalid or unreadable: "
                f"{type(error).__name__}: {error}"
            )
            LOGGER.error(reason)
            return _ClaimedJob(
                folder=claimed_folder,
                job=None,
                failure_reason=reason,
            )
        if selected_coordinator is not None and api_claim is not None:
            if job.get("attempt") != api_claim.attempt:
                raise RuntimeError(
                    "Local job attempt changed after the Dropbox API claim; "
                    "manual inspection is required."
                )
            job["dropbox_api_sync"] = True
            job["dropbox_coordination_generation"] = api_claim.generation
            job["dropbox_claim_token"] = api_claim.claim_token
            job["dropbox_owner_session"] = api_claim.session_id
            write_json_atomic(claimed_folder / JOB_FILENAME, job)
        if (
            selected_filesystem_coordinator is not None
            and filesystem_claim is not None
        ):
            if job.get("attempt") != filesystem_claim.attempt + 1:
                raise RuntimeError(
                    "Local job attempt changed after the filesystem election; "
                    "manual inspection is required."
                )
            job["filesystem_coordination_generation"] = filesystem_claim.attempt
            job["filesystem_claim_token"] = filesystem_claim.claim_token
            job["filesystem_owner_session"] = filesystem_claim.session_id
            write_json_atomic(claimed_folder / JOB_FILENAME, job)
        if git_pull_result is not None:
            _record_git_pull(claimed_folder, job, git_pull_result)
        if job_callback is not None:
            try:
                job_callback(dict(job))
            except Exception:
                LOGGER.exception("Could not report the claimed job to the interface")
        return _ClaimedJob(folder=claimed_folder, job=job)

    claimed_job = _run_stage(
        stage=WorkerStage.MOVING,
        operation=claim_and_prepare_job,
        minimum_stage_seconds=minimum_stage_seconds,
        stage_callback=stage_callback,
        sleep=sleep_function,
        monotonic=monotonic_function,
    )

    if claimed_job is None:
        LOGGER.info("Queue is empty: %s", paths.needs_rendering)
        return None

    if claimed_job.job is None:
        failure_reason = claimed_job.failure_reason or "Claimed job is invalid"

        def finish_invalid_job() -> WorkerResult:
            if selected_coordinator is not None and api_claim is not None:
                selected_coordinator.mark_invalid_failed(
                    api_claim,
                    failure_reason,
                )
            final_folder = fail_unreadable_claimed_job(
                paths=paths,
                claimed_folder=claimed_job.folder,
                worker_name=worker,
                reason=failure_reason,
            )
            LOGGER.info("Job failed: %s", final_folder)
            return WorkerResult("failed", final_folder, failure_reason)

        return _run_stage(
            stage=WorkerStage.FINISHING,
            operation=finish_invalid_job,
            minimum_stage_seconds=minimum_stage_seconds,
            stage_callback=stage_callback,
            sleep=sleep_function,
            monotonic=monotonic_function,
        )

    def render_job() -> tuple[bool, str, dict | None]:
        if selected_coordinator is not None and api_claim is not None:
            selected_coordinator.verify_claim(
                api_claim,
                expected_state="rendering",
            )
        if (
            selected_filesystem_coordinator is not None
            and filesystem_claim is not None
        ):
            selected_filesystem_coordinator.verify_claim(filesystem_claim)
        if not render_with_unreal:
            success = simulate_success
            reason = (
                "Simulated render completed successfully"
                if success
                else "Simulated render failure"
            )
            return success, reason, None

        runner = unreal_runner or execute_unreal_job
        try:
            execution_result = runner(
                claimed_folder=claimed_job.folder,
                job=claimed_job.job,
                unreal_editor_cmd=unreal_editor_cmd,
                timeout_seconds=render_timeout_seconds,
                local_uproject=local_uproject,
            )
        except Exception as error:
            reason = (
                "Real Unreal render could not run: "
                f"{type(error).__name__}: {error}"
            )
            LOGGER.exception(reason)
            return False, reason, {
                "simulated": False,
                "exit_code": None,
            }
        return (
            execution_result.success,
            execution_result.reason,
            execution_result.terminal_result_details(),
        )

    success, reason, result_details = _run_stage(
        stage=WorkerStage.RENDERING,
        operation=render_job,
        minimum_stage_seconds=minimum_stage_seconds,
        stage_callback=stage_callback,
        sleep=sleep_function,
        monotonic=monotonic_function,
    )

    def finish_job() -> WorkerResult:
        if selected_coordinator is not None and api_claim is not None:
            if success:
                selected_coordinator.mark_complete(api_claim)
            else:
                selected_coordinator.requeue_failed_claim(api_claim, reason)
        final_folder = finish_claimed_job(
            paths=paths,
            claimed_folder=claimed_job.folder,
            job=claimed_job.job,
            worker_name=worker,
            success=success,
            reason=reason,
            result_details=result_details,
        )
        status = "complete" if success else "requeued"
        LOGGER.info("Job %s: %s", status, final_folder)
        return WorkerResult(status, final_folder, reason)

    return _run_stage(
        stage=WorkerStage.FINISHING,
        operation=finish_job,
        minimum_stage_seconds=minimum_stage_seconds,
        stage_callback=stage_callback,
        sleep=sleep_function,
        monotonic=monotonic_function,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Claim and process one job from the PortablePipeTools render queue."
    )
    parser.add_argument("farm_root", type=Path, help="Shared RenderFarm folder")
    parser.add_argument(
        "--worker-name",
        default=default_worker_name(),
        help="Worker identity written into the job (defaults to this computer name)",
    )
    parser.add_argument(
        "--use-dropbox-api-sync",
        action="store_true",
        help=(
            "Coordinate claims with Dropbox server revisions instead of relying "
            "only on synchronized filesystem renames"
        ),
    )
    parser.add_argument(
        "--simulate-result",
        choices=("success", "failure"),
        default="success",
        help="Terminal state to simulate for this prototype",
    )
    parser.add_argument(
        "--render-with-unreal",
        action="store_true",
        help="Launch UnrealEditor-Cmd and execute the claimed real MRG job",
    )
    parser.add_argument(
        "--unreal-editor-cmd",
        type=Path,
        default=None,
        help="Optional explicit path to UnrealEditor-Cmd.exe",
    )
    parser.add_argument(
        "--local-uproject",
        type=Path,
        default=None,
        help=(
            "Optional worker-local .uproject path that overrides the path "
            "submitted in the farm job"
        ),
    )
    parser.add_argument(
        "--render-timeout-seconds",
        type=float,
        default=DEFAULT_RENDER_TIMEOUT_SECONDS,
        help="Maximum Unreal process runtime before the worker fails the job",
    )
    parser.add_argument(
        "--init-only",
        action="store_true",
        help="Create/validate queue folders without claiming a job",
    )
    parser.add_argument(
        "--minimum-stage-seconds",
        type=float,
        default=DEFAULT_MINIMUM_STAGE_SECONDS,
        help="Minimum time to display each worker stage (default: 5 seconds)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = build_argument_parser().parse_args(argv)

    if args.init_only:
        paths: QueuePaths = create_queue_folders(args.farm_root)
        LOGGER.info("Queue folders ready: %s", paths.root)
        return 0

    try:
        result = run_once(
            farm_root=args.farm_root,
            worker_name=args.worker_name,
            simulate_success=args.simulate_result == "success",
            minimum_stage_seconds=args.minimum_stage_seconds,
            render_with_unreal=args.render_with_unreal,
            unreal_editor_cmd=args.unreal_editor_cmd,
            local_uproject=args.local_uproject,
            render_timeout_seconds=args.render_timeout_seconds,
            use_dropbox_api_sync=args.use_dropbox_api_sync,
        )
    except Exception:
        LOGGER.exception("Worker stopped because of an unexpected queue error")
        return 2

    if result is None:
        return 0
    return 0 if result.status == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
