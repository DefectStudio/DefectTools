from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import socket
import sys
from uuid import uuid4

from portable_pipe_tools.render_farm.queue import (
    JOB_FILENAME,
    SCHEMA_VERSION,
    create_directory_with_retry,
    create_queue_folders,
    rename_path_with_retry,
    safe_name,
    utc_now,
    write_json_atomic,
)


def create_test_job(
    farm_root: str | Path,
    shot_name: str = "SH030",
    render_version: int = 12,
    priority: int = 50,
    frame_start: int = 1001,
    frame_end: int = 1100,
) -> Path:
    if render_version < 0:
        raise ValueError("render_version cannot be negative")
    if frame_end < frame_start:
        raise ValueError("frame_end must be greater than or equal to frame_start")

    paths = create_queue_folders(farm_root)
    clean_shot_name = safe_name(shot_name, "TEST_SHOT")
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%S.") + f"{now.microsecond // 1000:03d}Z"
    job_id = (
        f"{clean_shot_name}_v{render_version:03d}_{timestamp}_{uuid4().hex[:6]}"
    )
    staging_folder = paths.submitting / job_id
    queued_folder = paths.needs_rendering / job_id
    create_directory_with_retry(staging_folder)

    submitted_by = safe_name(
        os.environ.get("COMPUTERNAME") or socket.gethostname(),
        "UNKNOWN-COMPUTER",
    )
    job = {
        "schema_version": SCHEMA_VERSION,
        "job_id": job_id,
        "status": "queued",
        "priority": priority,
        "shot_name": clean_shot_name,
        "render_version": render_version,
        "submitted_by": submitted_by,
        "submitted_utc": utc_now(),
        "project": "S3Bishop",
        "uproject": "D:/UnrealProjects/s3bishop/s3bishop.uproject",
        "level": "/Game/TEST/ReplaceWithRenderSafeLevel",
        "sequence": "/Game/TEST/ReplaceWithRenderSafeSequence",
        "render_config": "/Game/TEST/ReplaceWithRenderConfig",
        "frame_start": frame_start,
        "frame_end": frame_end,
        "output_directory": "//server/renders/TEST/ReplaceMe",
        "submitted_git_commit": None,
        "rendered_git_commit": None,
        "worker": None,
        "claimed_utc": None,
        "render_started_utc": None,
        "render_finished_utc": None,
        "attempt": 0,
        "result": None,
        "test_job": True,
    }

    # A worker ignores 00_Submitting. Publishing is the folder rename below.
    write_json_atomic(staging_folder / JOB_FILENAME, job)
    rename_path_with_retry(staging_folder, queued_folder)
    return queued_folder


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish a fake job into the filesystem render queue."
    )
    parser.add_argument("farm_root", type=Path, help="Shared RenderFarm folder")
    parser.add_argument("--shot", default="SH030")
    parser.add_argument("--version", type=int, default=12)
    parser.add_argument("--priority", type=int, default=50)
    parser.add_argument("--frame-start", type=int, default=1001)
    parser.add_argument("--frame-end", type=int, default=1100)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    queued_folder = create_test_job(
        farm_root=args.farm_root,
        shot_name=args.shot,
        render_version=args.version,
        priority=args.priority,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
    )
    print(f"Published test job: {queued_folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
