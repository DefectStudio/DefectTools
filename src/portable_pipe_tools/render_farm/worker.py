from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
import sys
import time
from typing import Any, TypeVar

from portable_pipe_tools.render_farm.cloud_dispatch import (
    CloudJobLease,
    DispatcherClient,
    DispatcherConnectionError,
    DispatcherError,
)
from portable_pipe_tools.render_farm.cloud_queue import (
    finish_cloud_claimed_job,
    finish_invalid_cloud_claim,
    reconcile_pending_cloud_updates,
)
from portable_pipe_tools.render_farm.git_sync import (
    GIT_PULL_LOG_FILENAME,
    GitPullResult,
    pull_latest_branch,
    write_git_pull_log,
)
from portable_pipe_tools.render_farm.queue import (
    JOB_FILENAME,
    JobCandidate,
    QueuePaths,
    claim_job_by_id,
    claim_next_job,
    create_queue_folders,
    default_worker_name,
    fail_unreadable_claimed_job,
    finish_claimed_job,
    list_job_candidates,
    mark_cloud_job_rendering,
    mark_job_rendering,
    path_exists_with_retry,
    read_json_object,
    reconcile_completed_jobs,
    recover_stranded_cloud_job_to_queue,
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
from portable_pipe_tools.render_farm.workers import (
    WorkerPaths,
    clear_worker_stop_request,
)


LOGGER = logging.getLogger("render_worker")
DEFAULT_MINIMUM_STAGE_SECONDS = 5.0
CLOUD_LEASE_SAFETY_MARGIN_SECONDS = 30.0
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
    cloud_lease: CloudJobLease | None = None


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
    should_cancel_render: Callable[[], bool] | None = None,
    job_callback: JobCallback | None = None,
    local_uproject: str | Path | None = None,
    git_sync: GitSyncCallback | None = None,
    dispatcher_client: DispatcherClient | None = None,
    dispatcher_app_version: str | None = None,
    dispatcher_heartbeat_interval_seconds: float = 60.0,
) -> WorkerResult | None:
    if minimum_stage_seconds < 0:
        raise ValueError("minimum_stage_seconds cannot be negative")
    if dispatcher_heartbeat_interval_seconds <= 0:
        raise ValueError("dispatcher_heartbeat_interval_seconds must be positive")

    sleep_function = sleep or time.sleep
    monotonic_function = monotonic or time.monotonic
    paths = create_queue_folders(farm_root)
    worker = safe_name(worker_name, "WORKER")
    cloud_lease: CloudJobLease | None = None
    cloud_dispatcher_stop_requested = False

    def release_cloud_lease(reason: str) -> None:
        nonlocal cloud_lease
        if dispatcher_client is None or cloud_lease is None:
            return
        dispatcher_client.release_job(
            cloud_lease.job_id,
            worker,
            cloud_lease.lease_token,
            reason=reason,
        )
        LOGGER.info("Released Cloud Dispatcher lease for %s: %s", cloud_lease.job_id, reason)
        cloud_lease = None

    def reconcile_and_list_candidates():
        nonlocal cloud_lease
        nonlocal cloud_dispatcher_stop_requested
        reconciled_folders = reconcile_completed_jobs(paths)
        if reconciled_folders:
            LOGGER.info(
                "Recovered %d completed job(s) before checking the render queue.",
                len(reconciled_folders),
            )
        if dispatcher_client is not None:
            cloud_reconciled = reconcile_pending_cloud_updates(
                paths,
                dispatcher_client,
            )
            if cloud_reconciled:
                LOGGER.info(
                    "Delivered %d pending Cloud Dispatcher update(s).",
                    len(cloud_reconciled),
                )
            claim = dispatcher_client.claim_job(
                worker,
                app_version=dispatcher_app_version,
                capabilities={"unreal_mrq": True, "dropbox_packages": True},
            )
            if claim.stop_requested:
                LOGGER.info("Cloud Dispatcher requested that worker %s stop.", worker)
                if claim.lease is not None:
                    cloud_lease = claim.lease
                    release_cloud_lease("Worker stop was requested before package claim")
                dispatcher_client.acknowledge_worker_stop(worker)
                cloud_dispatcher_stop_requested = True
                return []
            if claim.lease is None:
                return []
            cloud_lease = claim.lease
            queued_folder = paths.needs_rendering / cloud_lease.job_id
            if not path_exists_with_retry(queued_folder):
                try:
                    recovered_folder = recover_stranded_cloud_job_to_queue(
                        paths,
                        cloud_lease.job_id,
                    )
                except Exception as error:
                    release_cloud_lease(
                        "Automatic recovery of the stranded Dropbox package "
                        f"failed: {type(error).__name__}: {error}"
                    )
                    raise
                if recovered_folder is not None:
                    queued_folder = recovered_folder
                    LOGGER.warning(
                        "Recovered stranded Cloud job package to the queue: %s",
                        recovered_folder,
                    )
            priority = cloud_lease.job.get("priority", 50)
            submitted_utc = cloud_lease.job.get("submitted_utc", "")
            return [
                JobCandidate(
                    folder=queued_folder,
                    priority=(
                        priority
                        if isinstance(priority, int) and not isinstance(priority, bool)
                        else 50
                    ),
                    submitted_utc=(
                        submitted_utc
                        if isinstance(submitted_utc, str)
                        else ""
                    ),
                )
            ]
        return list_job_candidates(paths, worker)

    queued_candidates = _run_stage(
        stage=WorkerStage.WAITING,
        operation=reconcile_and_list_candidates,
        minimum_stage_seconds=minimum_stage_seconds,
        stage_callback=stage_callback,
        sleep=sleep_function,
        monotonic=monotonic_function,
    )
    if not queued_candidates:
        if cloud_dispatcher_stop_requested:
            return WorkerResult(
                "stopped",
                paths.root,
                "Cloud Dispatcher requested that this worker stop",
            )
        LOGGER.info(
            "No queued jobs are eligible for worker %s: %s",
            worker,
            paths.needs_rendering,
        )
        return None

    if should_stop_before_claim is not None and should_stop_before_claim():
        LOGGER.info("Stop requested before claiming the next queued job.")
        release_cloud_lease("Worker stop was requested before package claim")
        return None

    git_pull_result: GitPullResult | None = None
    should_sync_git = render_with_unreal and (
        unreal_runner is None or git_sync is not None
    )
    if should_sync_git:
        project_directory = _git_project_directory_for_candidate(
            queued_candidates[0].folder,
            local_uproject,
        )
        if project_directory is not None:
            LOGGER.info(
                "Queued job found. Pulling the latest Git branch before claim: %s",
                project_directory,
            )
            sync_operation = git_sync or pull_latest_branch
            git_pull_result = sync_operation(project_directory)

    def claim_and_prepare_job() -> _ClaimedJob | None:
        if should_stop_before_claim is not None and should_stop_before_claim():
            LOGGER.info("Stop requested before claiming the next queued job.")
            release_cloud_lease("Worker stop was requested before package claim")
            return None
        claimed_folder = (
            claim_job_by_id(paths, worker, cloud_lease.job_id)
            if cloud_lease is not None
            else claim_next_job(paths, worker)
        )
        if claimed_folder is None:
            release_cloud_lease(
                "Dropbox job package has not synced to this worker yet"
            )
            return None

        LOGGER.info("Claimed job: %s", claimed_folder)
        job: dict | None = None
        try:
            job = (
                mark_cloud_job_rendering(
                    claimed_folder,
                    worker,
                    cloud_lease.job,
                )
                if cloud_lease is not None
                else mark_job_rendering(claimed_folder, worker)
            )
            if git_pull_result is not None:
                _record_git_pull(claimed_folder, job, git_pull_result)
        except Exception as error:
            if job is None:
                reason = (
                    f"Claimed job is invalid or unreadable: "
                    f"{type(error).__name__}: {error}"
                )
            else:
                reason = (
                    f"Post-claim job preparation failed: "
                    f"{type(error).__name__}: {error}"
                )
            LOGGER.exception(reason)
            return _ClaimedJob(
                folder=claimed_folder,
                job=None,
                failure_reason=reason,
                cloud_lease=cloud_lease,
            )
        if job_callback is not None:
            try:
                job_callback(dict(job))
            except Exception:
                LOGGER.exception("Could not report the claimed job to the interface")
        return _ClaimedJob(
            folder=claimed_folder,
            job=job,
            cloud_lease=cloud_lease,
        )

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
            if dispatcher_client is not None and claimed_job.cloud_lease is not None:
                final_folder = finish_invalid_cloud_claim(
                    dispatcher=dispatcher_client,
                    paths=paths,
                    claimed_folder=claimed_job.folder,
                    worker_name=worker,
                    lease=claimed_job.cloud_lease,
                    reason=failure_reason,
                )
            else:
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
        if not render_with_unreal:
            success = simulate_success
            reason = (
                "Simulated render completed successfully"
                if success
                else "Simulated render failure"
            )
            return success, reason, None

        runner = unreal_runner or execute_unreal_job
        last_heartbeat_success = monotonic_function()
        last_heartbeat_attempt = last_heartbeat_success
        cloud_cancel_reason: str | None = None
        cloud_lease_deadline = (
            last_heartbeat_success
            + max(0.0, claimed_job.cloud_lease.lease_expires_at - time.time())
            if claimed_job.cloud_lease is not None
            else None
        )

        def should_cancel() -> bool:
            nonlocal last_heartbeat_success
            nonlocal last_heartbeat_attempt
            nonlocal cloud_cancel_reason
            nonlocal cloud_lease_deadline
            if should_cancel_render is not None and should_cancel_render():
                return True
            if dispatcher_client is None or claimed_job.cloud_lease is None:
                return False
            current_time = monotonic_function()
            retry_interval = (
                dispatcher_heartbeat_interval_seconds
                if last_heartbeat_attempt == last_heartbeat_success
                else min(
                    10.0,
                    max(1.0, dispatcher_heartbeat_interval_seconds / 6.0),
                )
            )
            if current_time - last_heartbeat_attempt < retry_interval:
                return False
            last_heartbeat_attempt = current_time
            try:
                heartbeat = dispatcher_client.heartbeat_job(
                    claimed_job.cloud_lease.job_id,
                    worker,
                    claimed_job.cloud_lease.lease_token,
                )
            except DispatcherConnectionError as error:
                LOGGER.warning("Cloud Dispatcher heartbeat unavailable: %s", error)
                if (
                    cloud_lease_deadline is not None
                    and current_time
                    >= cloud_lease_deadline - CLOUD_LEASE_SAFETY_MARGIN_SECONDS
                ):
                    cloud_cancel_reason = (
                        "Cloud Dispatcher heartbeat remained unavailable too "
                        "close to lease expiry; canceling before the job can be "
                        "assigned to another worker"
                    )
                    LOGGER.error(cloud_cancel_reason)
                    return True
                return False
            except DispatcherError as error:
                cloud_cancel_reason = (
                    "Cloud Dispatcher lease was lost: "
                    f"{error.code}: {error}"
                )
                LOGGER.error(cloud_cancel_reason)
                return True
            last_heartbeat_success = current_time
            last_heartbeat_attempt = current_time
            lease_expires_at = heartbeat.get("lease_expires_at")
            if isinstance(lease_expires_at, (int, float)) and not isinstance(
                lease_expires_at,
                bool,
            ):
                cloud_lease_deadline = current_time + max(
                    0.0,
                    float(lease_expires_at) - time.time(),
                )
            if heartbeat.get("stop_requested"):
                cloud_cancel_reason = "Cloud Dispatcher requested that this worker stop"
                LOGGER.warning(cloud_cancel_reason)
                return True
            return False

        runner_arguments: dict[str, Any] = {
            "claimed_folder": claimed_job.folder,
            "job": claimed_job.job,
            "unreal_editor_cmd": unreal_editor_cmd,
            "timeout_seconds": render_timeout_seconds,
            "local_uproject": local_uproject,
        }
        if claimed_job.cloud_lease is not None:
            runner_arguments["should_cancel"] = should_cancel
        elif should_cancel_render is not None:
            runner_arguments["should_cancel"] = should_cancel_render
        try:
            execution_result = runner(**runner_arguments)
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
        if cloud_cancel_reason:
            return False, cloud_cancel_reason, execution_result.terminal_result_details()
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
        if dispatcher_client is not None and claimed_job.cloud_lease is not None:
            final_folder = finish_cloud_claimed_job(
                dispatcher=dispatcher_client,
                paths=paths,
                claimed_folder=claimed_job.folder,
                job=claimed_job.job,
                worker_name=worker,
                lease=claimed_job.cloud_lease,
                success=success,
                reason=reason,
                result_details=result_details,
            )
        else:
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

    worker_paths = WorkerPaths.from_farm_root(args.farm_root, args.worker_name)

    def stop_requested() -> bool:
        return path_exists_with_retry(worker_paths.stop_file)

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
            should_stop_before_claim=stop_requested,
            should_cancel_render=stop_requested,
        )
    except Exception:
        LOGGER.exception("Worker stopped because of an unexpected queue error")
        return 2
    finally:
        try:
            if stop_requested():
                clear_worker_stop_request(args.farm_root, args.worker_name)
                LOGGER.info("Consumed worker STOP marker: %s", worker_paths.stop_file)
        except Exception:
            LOGGER.exception("Could not consume the worker STOP marker")

    if result is None:
        return 0
    return 0 if result.status == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
