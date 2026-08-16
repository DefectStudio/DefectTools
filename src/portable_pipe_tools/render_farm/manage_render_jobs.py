from __future__ import annotations

from copy import deepcopy
import getpass
from pathlib import Path
from typing import Any
from uuid import uuid4

from portable_pipe_tools.render_farm.local_paths import (
    OVERWRITE_EXISTING_EXR_FIELD,
    OVERWRITE_EXISTING_MP4_FIELD,
)
from portable_pipe_tools.render_farm.queue import (
    BLACKLISTED_WORKERS_FIELD,
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


def clear_render_job_blacklist(job: RenderJob) -> bool:
    """Clear a non-rendering job's live blacklist and report whether it changed."""
    if job.queue_name == IS_RENDERING_FOLDER:
        raise ValueError(f'Cannot clear the blacklist while "{job.job_name}" is rendering')

    data = read_json_object(job.job_json_path)
    blacklist = data.get(BLACKLISTED_WORKERS_FIELD, [])
    if not isinstance(blacklist, list):
        raise ValueError(
            f"Invalid {BLACKLISTED_WORKERS_FIELD} in {job.job_json_path}; "
            "expected a list"
        )
    if not blacklist:
        return False

    data[BLACKLISTED_WORKERS_FIELD] = []
    write_json_atomic(job.job_json_path, data)
    return True


def set_render_job_output_overwrite(job: RenderJob, enabled: bool) -> bool:
    """Set a non-rendering job's explicit MP4/EXR overwrite permissions."""
    if job.queue_name == IS_RENDERING_FOLDER:
        raise ValueError(
            f'Cannot change output overwrite permission while "{job.job_name}" '
            "is rendering"
        )

    data = read_json_object(job.job_json_path)
    outputs = data.get("outputs")
    mp4_enabled = isinstance(outputs, dict) and outputs.get("mp4") is True
    exr_enabled = isinstance(outputs, dict) and outputs.get("exr") is True
    if enabled and not mp4_enabled and not exr_enabled:
        raise ValueError(f'"{job.job_name}" has no MP4 or EXR output enabled')

    new_mp4_value = enabled and mp4_enabled
    new_exr_value = enabled and exr_enabled
    current_mp4_value = data.get(OVERWRITE_EXISTING_MP4_FIELD) is True
    current_exr_value = data.get(OVERWRITE_EXISTING_EXR_FIELD) is True
    if (
        current_mp4_value == new_mp4_value
        and current_exr_value == new_exr_value
    ):
        return False

    data[OVERWRITE_EXISTING_MP4_FIELD] = new_mp4_value
    data[OVERWRITE_EXISTING_EXR_FIELD] = new_exr_value
    write_json_atomic(job.job_json_path, data)
    return True


def resubmit_failed_render_job(job: RenderJob) -> Path:
    """Publish a failed package as a fresh job in 01_NeedsRendering."""
    if job.queue_name != RENDER_FAILED_FOLDER:
        raise ValueError(
            f'Only jobs in {RENDER_FAILED_FOLDER} can be resubmitted; '
            f'"{job.job_name}" is in {job.queue_name}'
        )

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
