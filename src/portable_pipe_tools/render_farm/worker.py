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

from portable_pipe_tools.render_farm.queue import (
    QueuePaths,
    claim_next_job,
    create_queue_folders,
    default_worker_name,
    fail_unreadable_claimed_job,
    finish_claimed_job,
    list_job_candidates,
    mark_job_rendering,
    safe_name,
)
from portable_pipe_tools.render_farm.unreal_runner import (
    DEFAULT_RENDER_TIMEOUT_SECONDS,
    UnrealExecutionResult,
    execute_unreal_job,
)


LOGGER = logging.getLogger("render_worker")
DEFAULT_MINIMUM_STAGE_SECONDS = 5.0
_StageResult = TypeVar("_StageResult")


class WorkerStage(str, Enum):
    WAITING = "waiting"
    MOVING = "moving"
    RENDERING = "rendering"
    FINISHING = "finishing"


WORKER_STAGE_LABELS: dict[WorkerStage, str] = {
    WorkerStage.WAITING: "Waiting to find a job",
    WorkerStage.MOVING: "Moving files and claiming the job",
    WorkerStage.RENDERING: "Rendering",
    WorkerStage.FINISHING: "Finishing render tasks",
}

StageCallback = Callable[[WorkerStage], None]
JobCallback = Callable[[dict], None]


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
) -> WorkerResult | None:
    if minimum_stage_seconds < 0:
        raise ValueError("minimum_stage_seconds cannot be negative")

    sleep_function = sleep or time.sleep
    monotonic_function = monotonic or time.monotonic
    paths = create_queue_folders(farm_root)
    worker = safe_name(worker_name, "WORKER")

    queued_candidates = _run_stage(
        stage=WorkerStage.WAITING,
        operation=lambda: list_job_candidates(paths),
        minimum_stage_seconds=minimum_stage_seconds,
        stage_callback=stage_callback,
        sleep=sleep_function,
        monotonic=monotonic_function,
    )
    if not queued_candidates:
        LOGGER.info("Queue is empty: %s", paths.needs_rendering)
        return None

    if should_stop_before_claim is not None and should_stop_before_claim():
        LOGGER.info("Stop requested before claiming the next queued job.")
        return None

    def claim_and_prepare_job() -> _ClaimedJob | None:
        if should_stop_before_claim is not None and should_stop_before_claim():
            LOGGER.info("Stop requested before claiming the next queued job.")
            return None
        claimed_folder = claim_next_job(paths, worker)
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
        final_folder = finish_claimed_job(
            paths=paths,
            claimed_folder=claimed_job.folder,
            job=claimed_job.job,
            worker_name=worker,
            success=success,
            reason=reason,
            result_details=result_details,
        )
        status = "complete" if success else "failed"
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
        )
    except Exception:
        LOGGER.exception("Worker stopped because of an unexpected queue error")
        return 2

    if result is None:
        return 0
    return 0 if result.status == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
