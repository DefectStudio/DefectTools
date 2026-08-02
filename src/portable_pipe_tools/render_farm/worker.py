from __future__ import annotations

import argparse
from dataclasses import dataclass
import logging
from pathlib import Path
import sys

from portable_pipe_tools.render_farm.queue import (
    QueuePaths,
    claim_next_job,
    create_queue_folders,
    default_worker_name,
    fail_unreadable_claimed_job,
    finish_claimed_job,
    mark_job_rendering,
    safe_name,
)


LOGGER = logging.getLogger("render_worker")


@dataclass(frozen=True)
class WorkerResult:
    status: str
    final_folder: Path
    reason: str


def run_once(
    farm_root: str | Path,
    worker_name: str,
    simulate_success: bool,
) -> WorkerResult | None:
    paths = create_queue_folders(farm_root)
    worker = safe_name(worker_name, "WORKER")
    claimed_folder = claim_next_job(paths, worker)

    if claimed_folder is None:
        LOGGER.info("Queue is empty: %s", paths.needs_rendering)
        return None

    LOGGER.info("Claimed job: %s", claimed_folder)
    try:
        job = mark_job_rendering(claimed_folder, worker)
    except Exception as error:
        reason = f"Claimed job is invalid or unreadable: {type(error).__name__}: {error}"
        LOGGER.error(reason)
        final_folder = fail_unreadable_claimed_job(
            paths=paths,
            claimed_folder=claimed_folder,
            worker_name=worker,
            reason=reason,
        )
        return WorkerResult("failed", final_folder, reason)

    success = simulate_success
    reason = "Simulated render completed successfully" if success else "Simulated render failure"
    final_folder = finish_claimed_job(
        paths=paths,
        claimed_folder=claimed_folder,
        job=job,
        worker_name=worker,
        success=success,
        reason=reason,
    )
    status = "complete" if success else "failed"
    LOGGER.info("Job %s: %s", status, final_folder)
    return WorkerResult(status, final_folder, reason)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Claim and simulate one job from the PortablePipeTools render queue."
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
        "--init-only",
        action="store_true",
        help="Create/validate queue folders without claiming a job",
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
        )
    except Exception:
        LOGGER.exception("Worker stopped because of an unexpected queue error")
        return 2

    if result is None:
        return 0
    return 0 if result.status == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
