from __future__ import annotations

from pathlib import Path
from typing import Any

from portable_pipe_tools.render_farm.queue import (
    JOB_FILENAME,
    QUEUE_FOLDER_NAMES,
    RENDER_COMPLETE_FOLDER,
    RENDER_FAILED_FOLDER,
    RESULT_FILENAME,
    read_json_object,
)
from portable_pipe_tools.render_farm.render_job import RenderJob


RENDER_FARM_FOLDER_NAME = "renderFarm"

QUEUE_STATUSES = {
    "00_Submitting": "submitting",
    "01_NeedsRendering": "queued",
    "02_IsRendering": "rendering",
    RENDER_COMPLETE_FOLDER: "complete",
    RENDER_FAILED_FOLDER: "failed",
}


def get_all_render_jobs(dropbox_folder: str | Path) -> list[RenderJob]:
    """Return every job found in every project's five render-farm queues."""
    repository_root = Path(dropbox_folder).expanduser()
    if not repository_root.exists():
        raise FileNotFoundError(f"Dropbox repository does not exist: {repository_root}")
    if not repository_root.is_dir():
        raise NotADirectoryError(
            f"Dropbox repository is not a folder: {repository_root}"
        )

    jobs: list[RenderJob] = []
    project_folders = sorted(
        (path for path in repository_root.iterdir() if path.is_dir()),
        key=lambda path: path.name.casefold(),
    )

    for project_folder in project_folders:
        render_farm_folder = project_folder / RENDER_FARM_FOLDER_NAME
        if not render_farm_folder.is_dir():
            continue

        for queue_name in QUEUE_FOLDER_NAMES:
            queue_folder = render_farm_folder / queue_name
            if not queue_folder.is_dir():
                continue

            job_folders = sorted(
                (path for path in queue_folder.iterdir() if path.is_dir()),
                key=lambda path: path.name.casefold(),
            )
            for job_folder in job_folders:
                job_json_path = job_folder / JOB_FILENAME
                result_json_path = job_folder / RESULT_FILENAME
                job_data: dict[str, Any] = {}
                result_data: dict[str, Any] = {}
                load_errors: list[str] = []

                try:
                    job_data = read_json_object(job_json_path)
                except (FileNotFoundError, OSError, ValueError) as error:
                    load_errors.append(f"Could not read {JOB_FILENAME}: {error}")

                if result_json_path.is_file():
                    try:
                        result_data = read_json_object(result_json_path)
                    except (OSError, ValueError) as error:
                        load_errors.append(
                            f"Could not read {RESULT_FILENAME}: {error}"
                        )

                status = QUEUE_STATUSES[queue_name]
                render_version = _optional_int(job_data.get("render_version"))
                shot_name = _text(job_data.get("shot_name"))
                job_id = _text(job_data.get("job_id"))
                fallback_name = job_folder.name.split("__", 1)[0]
                if shot_name and render_version is not None:
                    job_name = f"{shot_name}_v{render_version:03d}"
                else:
                    job_name = job_id or fallback_name

                worker = _text(job_data.get("worker"))
                if not worker and "__" in job_folder.name:
                    worker = job_folder.name.rsplit("__", 1)[-1]

                jobs.append(
                    RenderJob(
                        project=project_folder.name,
                        submitted_project=_text(job_data.get("project")),
                        queue_name=queue_name,
                        status=status,
                        job_folder=job_folder,
                        job_json_path=job_json_path,
                        result_json_path=result_json_path,
                        job_id=job_id or fallback_name,
                        job_name=job_name,
                        shot_name=shot_name,
                        render_version=render_version,
                        submitted_user=_text(job_data.get("submitted_user")),
                        submitted_by=_text(job_data.get("submitted_by")),
                        submitted_utc=_text(job_data.get("submitted_utc")),
                        priority=_optional_int(job_data.get("priority")),
                        worker=worker,
                        frame_start=_optional_int(job_data.get("frame_start")),
                        frame_end=_optional_int(job_data.get("frame_end")),
                        frame_count=_optional_int(job_data.get("frame_count")),
                        progress=_progress_percent(job_data, status),
                        error_count=1 if status == "failed" else 0,
                        render_started_utc=_text(
                            job_data.get("render_started_utc")
                            or result_data.get("render_started_utc")
                        ),
                        render_finished_utc=_text(
                            job_data.get("render_finished_utc")
                            or result_data.get("render_finished_utc")
                        ),
                        output_directory=_text(job_data.get("output_directory")),
                        render_config=_text(job_data.get("render_config")),
                        job_data=job_data,
                        result_data=result_data,
                        load_error="; ".join(load_errors) or None,
                    )
                )

    return sorted(
        jobs,
        key=lambda job: (
            job.submitted_utc,
            job.project.casefold(),
            job.job_name.casefold(),
        ),
        reverse=True,
    )


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _progress_percent(job_data: dict[str, Any], status: str) -> float:
    if status == "complete":
        return 100.0

    snapshot = job_data.get("mrq_snapshot")
    raw_progress = snapshot.get("status_progress", 0) if isinstance(snapshot, dict) else 0
    try:
        progress = float(raw_progress)
    except (TypeError, ValueError):
        return 0.0
    if 0 < progress <= 1:
        progress *= 100
    return max(0.0, min(100.0, progress))
