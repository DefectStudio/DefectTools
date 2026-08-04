from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from portable_pipe_tools.render_farm.get_all_render_jobs import (
    RENDER_FARM_FOLDER_NAME,
)
from portable_pipe_tools.render_farm.queue import (
    QUEUE_FOLDER_NAMES,
    retry_transient_windows_lock,
)
from portable_pipe_tools.render_farm.render_job import RenderJob


@dataclass(frozen=True)
class DeleteRenderJobsResult:
    deleted_folders: tuple[Path, ...]
    errors: tuple[str, ...]


def delete_render_jobs(jobs: list[RenderJob]) -> DeleteRenderJobsResult:
    """Permanently delete validated render-job package folders."""
    deleted_folders: list[Path] = []
    errors: list[str] = []
    seen_folders: set[Path] = set()

    for job in jobs:
        job_folder = job.job_folder.absolute()
        if job_folder in seen_folders:
            continue
        seen_folders.add(job_folder)

        queue_folder = job_folder.parent
        render_farm_folder = queue_folder.parent
        if (
            queue_folder.name not in QUEUE_FOLDER_NAMES
            or render_farm_folder.name != RENDER_FARM_FOLDER_NAME
            or job_folder == queue_folder
        ):
            errors.append(
                f"Refused unsafe delete target for {job.job_name}: {job_folder}"
            )
            continue
        if not job_folder.exists():
            errors.append(f"Job folder no longer exists: {job_folder}")
            continue
        if not job_folder.is_dir():
            errors.append(f"Job target is not a folder: {job_folder}")
            continue

        try:
            retry_transient_windows_lock(
                operation=lambda folder=job_folder: shutil.rmtree(folder),
                description=f"Delete render job folder {job_folder}",
            )
        except OSError as error:
            errors.append(f"Could not delete {job.job_name}: {error}")
        else:
            deleted_folders.append(job_folder)

    return DeleteRenderJobsResult(
        deleted_folders=tuple(deleted_folders),
        errors=tuple(errors),
    )
