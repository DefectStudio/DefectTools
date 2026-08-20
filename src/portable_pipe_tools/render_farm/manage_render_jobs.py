from __future__ import annotations

from copy import deepcopy
import getpass
from pathlib import Path
from typing import Any
from uuid import uuid4

from portable_pipe_tools.render_farm.cloud_dispatch import (
    DispatcherClient,
    DispatcherError,
)
from portable_pipe_tools.render_farm.delete_render_jobs import delete_render_jobs
from portable_pipe_tools.render_farm.queue import (
    BLACKLISTED_WORKERS_FIELD,
    CLOUD_DISPATCHER_COORDINATION,
    DISPATCHER_COORDINATION_FIELD,
    IS_RENDERING_FOLDER,
    JOB_FILENAME,
    RENDER_FAILED_FOLDER,
    create_directory_with_retry,
    create_queue_folders,
    default_worker_name,
    path_exists_with_retry,
    read_json_object,
    rename_path_with_retry,
    safe_name,
    utc_now,
    write_json_atomic,
)
from portable_pipe_tools.render_farm.render_job import RenderJob


_WORKER_RUNTIME_FIELDS = frozenset(
    {
        "git_branch",
        "git_commit_after_pull",
        "git_commit_before_pull",
        "git_pull_completed_utc",
        "git_pull_summary",
        "git_sync_status",
        "git_upstream",
        "rendered_git_commit",
        "worker_output_directory",
        "worker_show_file_server_path",
        "worker_sync_policy",
        "worker_uproject",
    }
)
DISPATCHER_SUBMISSION_RECEIPT_FILENAME = "dispatcher_submission.json"


def clear_render_job_blacklist(
    job: RenderJob,
    dispatcher_client: DispatcherClient | None = None,
) -> bool:
    """Clear a non-rendering job's live blacklist and report whether it changed."""
    if job.queue_name == IS_RENDERING_FOLDER:
        raise ValueError(f'Cannot clear the blacklist while "{job.job_name}" is rendering')

    if job.control_source == "cloud":
        if dispatcher_client is None:
            raise DispatcherError(
                "Clearing a D1 job blacklist requires the Manager Cloud "
                "Dispatcher key.",
                code="dispatcher_not_configured",
            )
        response = dispatcher_client.clear_blacklist(job.job_id)
        raw_cleared = response.get("cleared", 0)
        return isinstance(raw_cleared, int) and raw_cleared > 0

    data = read_json_object(job.job_json_path)
    blacklist = data.get(BLACKLISTED_WORKERS_FIELD, [])
    if not isinstance(blacklist, list):
        raise ValueError(
            f"Invalid {BLACKLISTED_WORKERS_FIELD} in {job.job_json_path}; "
            "expected a list"
        )
    cloud_cleared = 0
    if dispatcher_client is not None:
        try:
            response = dispatcher_client.clear_blacklist(job.job_id)
        except DispatcherError as error:
            if error.status != 404:
                raise
            # Legacy filesystem jobs created before D1 cutover have no cloud row.
        else:
            raw_cleared = response.get("cleared", 0)
            cloud_cleared = raw_cleared if isinstance(raw_cleared, int) else 0

    if blacklist:
        data[BLACKLISTED_WORKERS_FIELD] = []
        write_json_atomic(job.job_json_path, data)
    return bool(blacklist) or cloud_cleared > 0


def recover_stalled_render_job(
    job: RenderJob,
    dispatcher_client: DispatcherClient | None,
) -> Path:
    """Return a D1-queued package stranded in 02_IsRendering to 01."""
    if job.queue_name != IS_RENDERING_FOLDER:
        raise ValueError(
            f'Only jobs in {IS_RENDERING_FOLDER} can be recovered; '
            f'"{job.job_name}" is in {job.queue_name}'
        )
    if job.control_source == "cloud":
        raise ValueError(
            "D1 jobs recover automatically when their worker lease expires; "
            "there is no Dropbox package to move. Refresh the Manager to run "
            "lease recovery."
        )
    if dispatcher_client is None:
        raise DispatcherError(
            "Recover Stalled Job requires the Manager Cloud Dispatcher key.",
            code="dispatcher_not_configured",
        )

    source_data = read_json_object(job.job_json_path)
    job_id = str(source_data.get("job_id") or job.job_id).strip()
    if (
        str(source_data.get(DISPATCHER_COORDINATION_FIELD) or "").casefold()
        != CLOUD_DISPATCHER_COORDINATION
    ):
        raise ValueError(
            f'"{job.job_name}" is not coordinated by the Cloud Dispatcher.'
        )

    response = dispatcher_client.get_job(job_id)
    summary = response.get("summary")
    cloud_job = response.get("job")
    if not isinstance(summary, dict) or not isinstance(cloud_job, dict):
        raise DispatcherError(
            f"Cloud Dispatcher returned incomplete state for {job_id}.",
            code="invalid_dispatcher_response",
            response=response,
        )
    if (
        summary.get("status") != "queued"
        or summary.get("worker") is not None
        or summary.get("lease_expires_at") is not None
    ):
        owner = summary.get("worker") or "another worker"
        raise DispatcherError(
            f"{job_id} is not recoverable because D1 currently reports "
            f"status={summary.get('status')!r}, owner={owner!r}.",
            status=409,
            code="job_has_active_lease",
            response=response,
        )
    if cloud_job.get("job_id") != job_id or cloud_job.get("status") != "queued":
        raise DispatcherError(
            f"Cloud Dispatcher payload does not describe queued job {job_id}.",
            code="invalid_dispatcher_response",
            response=response,
        )

    paths = create_queue_folders(job.job_folder.parent.parent)
    destination = paths.needs_rendering / job_id
    if path_exists_with_retry(destination):
        raise FileExistsError(
            f"A queued package already exists for {job_id}: {destination}"
        )

    # Publish the D1-authoritative queued state before the atomic directory move.
    # If Dropbox briefly locks the rename, the package remains visibly recoverable
    # in 02 and the same action can be retried without creating a second job.
    write_json_atomic(job.job_json_path, dict(cloud_job))
    rename_path_with_retry(job.job_folder, destination)
    return destination


def resubmit_failed_render_job(
    job: RenderJob,
    dispatcher_client: DispatcherClient | None = None,
) -> Path | str:
    """Replace a failed D1 job or legacy package with a fresh job."""
    if job.queue_name != RENDER_FAILED_FOLDER:
        raise ValueError(
            f'Only jobs in {RENDER_FAILED_FOLDER} can be resubmitted; '
            f'"{job.job_name}" is in {job.queue_name}'
        )

    if job.control_source == "cloud":
        if dispatcher_client is None:
            raise DispatcherError(
                "Resubmitting a D1 job requires the Manager Cloud Dispatcher key.",
                code="dispatcher_not_configured",
            )
        detail = dispatcher_client.get_job(job.job_id)
        cloud_job = detail.get("job")
        if not isinstance(cloud_job, dict):
            raise DispatcherError(
                f"Cloud Dispatcher returned no payload for {job.job_id}.",
                code="invalid_dispatcher_response",
                response=detail,
            )
        source_data = dict(cloud_job)
    else:
        source_data = read_json_object(job.job_json_path)
    old_job_id = str(source_data.get("job_id") or job.job_id).strip()
    submitted_utc = utc_now()
    compact_timestamp = (
        submitted_utc.replace("-", "").replace(":", "").replace(".", "")
    )
    unique_suffix = uuid4().hex[:6]
    new_job_id = _new_job_id(
        source_data,
        old_job_id,
        compact_timestamp,
        unique_suffix,
    )

    data = _fresh_job_data(
        source_data,
        old_job_id=old_job_id,
        new_job_id=new_job_id,
        submitted_utc=submitted_utc,
        compact_timestamp=compact_timestamp,
        unique_suffix=unique_suffix,
    )
    if dispatcher_client is not None:
        data[DISPATCHER_COORDINATION_FIELD] = CLOUD_DISPATCHER_COORDINATION

    if job.control_source == "cloud":
        assert dispatcher_client is not None
        response = dispatcher_client.replace_job(old_job_id, data)
        if response.get("source_deleted") is not True:
            raise DispatcherError(
                "The Cloud Dispatcher did not confirm deletion of the old failed "
                "job.",
                code="replacement_not_confirmed",
                response=response,
            )
        return new_job_id

    farm_root = job.job_folder.parent.parent
    paths = create_queue_folders(farm_root)
    staging_folder = paths.submitting / new_job_id
    destination = paths.needs_rendering / new_job_id
    if path_exists_with_retry(staging_folder) or path_exists_with_retry(destination):
        raise FileExistsError(
            f"Fresh resubmission destination already exists: {destination}"
        )

    create_directory_with_retry(staging_folder)
    write_json_atomic(staging_folder / JOB_FILENAME, data)
    rename_path_with_retry(staging_folder, destination)
    if dispatcher_client is not None:
        response = dispatcher_client.replace_job(old_job_id, data)
        if response.get("source_deleted") is not True:
            raise DispatcherError(
                "The Cloud Dispatcher did not confirm deletion of the old failed "
                "job, so its Dropbox package was preserved.",
                code="replacement_not_confirmed",
                response=response,
            )
        write_json_atomic(
            destination / DISPATCHER_SUBMISSION_RECEIPT_FILENAME,
            {
                "schema_version": 1,
                "job_id": new_job_id,
                "replaced_job_id": old_job_id,
                "submitted_utc": utc_now(),
                "created": response.get("created") is True,
                "idempotent_replay": response.get("idempotent_replay") is True,
                "source_deleted": response.get("source_deleted") is True,
            },
        )

    deletion = delete_render_jobs([job])
    if deletion.errors:
        raise OSError(
            "The replacement job was queued, but its old failed package could "
            f"not be deleted: {'; '.join(deletion.errors)}"
        )
    return destination


def _new_job_id(
    data: dict[str, Any],
    old_job_id: str,
    compact_timestamp: str,
    unique_suffix: str,
) -> str:
    shot_name = safe_name(str(data.get("shot_name") or ""), "render_job")
    raw_version = data.get("render_version")
    try:
        version = f"v{int(raw_version):03d}"
    except (TypeError, ValueError):
        version = "v000"
    fallback = safe_name(old_job_id, "render_job")
    base_name = safe_name(f"{shot_name}_{version}", fallback)
    return f"{base_name}_{compact_timestamp}_{unique_suffix}"


def _fresh_job_data(
    source_data: dict[str, Any],
    *,
    old_job_id: str,
    new_job_id: str,
    submitted_utc: str,
    compact_timestamp: str,
    unique_suffix: str,
) -> dict[str, Any]:
    data = deepcopy(source_data)
    for field_name in _WORKER_RUNTIME_FIELDS:
        data.pop(field_name, None)

    submitted_output_directory = data.get("submitted_output_directory")
    if submitted_output_directory:
        data["output_directory"] = submitted_output_directory

    project = safe_name(str(data.get("project") or "project"), "project")
    data.update(
        {
            "job_id": new_job_id,
            "batch_id": (
                f"{project}_manager_resubmit_{compact_timestamp}_{unique_suffix}"
            ),
            "status": "queued",
            "attempt": 0,
            BLACKLISTED_WORKERS_FIELD: [],
            "worker": None,
            "claimed_utc": None,
            "render_started_utc": None,
            "render_finished_utc": None,
            "result": None,
            "last_failure": None,
            "submitted_utc": submitted_utc,
            "submitted_by": default_worker_name(),
            "submitted_user": getpass.getuser(),
            "resubmitted_from_job_id": old_job_id,
            "resubmitted_utc": submitted_utc,
            "resubmitted_by": default_worker_name(),
            "resubmitted_user": getpass.getuser(),
        }
    )
    return data
