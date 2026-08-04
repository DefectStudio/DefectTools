from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from portable_pipe_tools.render_farm.queue import (
    JOB_FILENAME,
    RESULT_FILENAME,
    create_queue_folders,
    utc_now,
    write_json_atomic,
)


DEVELOPMENT_PROJECT_NAME = "Development"


def create_development_test_jobs(
    repository_root: str | Path,
    count: int = 5,
) -> list[Path]:
    """Create completed dummy jobs that are safe to use for deletion testing."""
    if count <= 0:
        raise ValueError("Development test job count must be greater than zero")

    repository = Path(repository_root).expanduser()
    if not repository.is_dir():
        raise NotADirectoryError(f"Repository folder does not exist: {repository}")

    project_root = repository / DEVELOPMENT_PROJECT_NAME
    paths = create_queue_folders(project_root / "renderFarm")
    created_folders: list[Path] = []
    batch_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    for index in range(1, count + 1):
        shot_name = f"DEV_DELETE_TEST_{index:03d}"
        job_id = (
            f"{shot_name}_v001_{batch_timestamp}_{uuid4().hex[:6]}"
        )
        job_folder = paths.render_complete / job_id
        if job_folder.exists():
            raise FileExistsError(f"Development test job already exists: {job_folder}")
        job_folder.mkdir()

        submitted_utc = utc_now()
        reason = "Dummy completed job for Farm Render Manager deletion testing."
        result = {
            "schema_version": 1,
            "job_id": job_id,
            "status": "complete",
            "worker": "DEVELOPMENT-TEST",
            "simulated": True,
            "exit_code": 0,
            "reason": reason,
            "render_started_utc": submitted_utc,
            "render_finished_utc": submitted_utc,
        }
        job = {
            "schema_version": 1,
            "job_type": "farm_manager_deletion_test",
            "job_id": job_id,
            "batch_id": f"development_delete_test_{batch_timestamp}",
            "status": "complete",
            "priority": 0,
            "shot_name": shot_name,
            "render_version": 1,
            "submitted_by": "FARM-RENDER-MANAGER",
            "submitted_user": "development",
            "submitted_utc": submitted_utc,
            "project": DEVELOPMENT_PROJECT_NAME,
            "frame_start": 1,
            "frame_end": 2,
            "frame_end_semantics": "exclusive",
            "frame_count": 1,
            "worker": "DEVELOPMENT-TEST",
            "render_started_utc": submitted_utc,
            "render_finished_utc": submitted_utc,
            "attempt": 1,
            "result": result,
            "test_job": True,
            "deletion_test_job": True,
        }
        write_json_atomic(job_folder / JOB_FILENAME, job)
        write_json_atomic(job_folder / RESULT_FILENAME, result)
        created_folders.append(job_folder)

    return created_folders
