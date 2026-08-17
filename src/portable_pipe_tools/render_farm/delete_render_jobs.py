from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from portable_pipe_tools.render_farm.cloud_dispatch import (
    DispatcherClient,
    DispatcherError,
)
from portable_pipe_tools.render_farm.get_all_render_jobs import (
    RENDER_FARM_FOLDER_NAME,
)
from portable_pipe_tools.render_farm.queue import (
    CLOUD_DISPATCHER_COORDINATION,
    DISPATCHER_COORDINATION_FIELD,
    QUEUE_FOLDER_NAMES,
    retry_transient_windows_lock,
)
from portable_pipe_tools.render_farm.render_job import RenderJob


@dataclass(frozen=True)
class DeleteRenderJobsResult:
    deleted_folders: tuple[Path, ...]
    errors: tuple[str, ...]


def _delete_target_error(job: RenderJob) -> str | None:
    job_folder = job.job_folder.absolute()
    queue_folder = job_folder.parent
    render_farm_folder = queue_folder.parent
    if (
        queue_folder.name not in QUEUE_FOLDER_NAMES
        or render_farm_folder.name != RENDER_FARM_FOLDER_NAME
        or job_folder == queue_folder
    ):
        return f"Refused unsafe delete target for {job.job_name}: {job_folder}"
    if not job_folder.exists():
        return f"Job folder no longer exists: {job_folder}"
    if not job_folder.is_dir():
        return f"Job target is not a folder: {job_folder}"
    return None


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

        if error := _delete_target_error(job):
            errors.append(error)
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


def delete_render_jobs_with_dispatcher(
    jobs: list[RenderJob],
    dispatcher_client: DispatcherClient | None,
) -> DeleteRenderJobsResult:
    """Delete cloud records first, then their validated Dropbox packages."""
    locally_ready: list[RenderJob] = []
    errors: list[str] = []
    seen_folders: set[Path] = set()

    for job in jobs:
        job_folder = job.job_folder.absolute()
        if job_folder in seen_folders:
            continue
        seen_folders.add(job_folder)

        if error := _delete_target_error(job):
            errors.append(error)
            continue
        cloud_coordinated = (
            str(job.job_data.get(DISPATCHER_COORDINATION_FIELD) or "").casefold()
            == CLOUD_DISPATCHER_COORDINATION
        )
        if not cloud_coordinated:
            locally_ready.append(job)
            continue
        if dispatcher_client is None:
            errors.append(
                f"Could not delete {job.job_name}: this is a cloud-coordinated "
                "job, but the Farm Manager cloud connection is not configured."
            )
            continue
        try:
            response = dispatcher_client.delete_job(job.job_id)
        except DispatcherError as error:
            errors.append(
                f"Could not delete {job.job_name} from the Cloud Dispatcher: "
                f"{error}"
            )
            continue
        if response.get("deletion_confirmed") is not True:
            errors.append(
                f"Could not delete {job.job_name}: the Cloud Dispatcher did not "
                "confirm deletion, so its Dropbox package was preserved."
            )
            continue
        locally_ready.append(job)

    local_result = delete_render_jobs(locally_ready)
    return DeleteRenderJobsResult(
        deleted_folders=local_result.deleted_folders,
        errors=tuple(errors) + local_result.errors,
    )
