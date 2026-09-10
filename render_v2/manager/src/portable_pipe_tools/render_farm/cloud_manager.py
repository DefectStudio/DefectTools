from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

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
    IS_RENDERING_FOLDER,
    NEEDS_RENDERING_FOLDER,
    RENDER_COMPLETE_FOLDER,
    RENDER_FAILED_FOLDER,
    RESULT_FILENAME,
    JOB_FILENAME,
)
from portable_pipe_tools.render_farm.render_job import RenderJob
from portable_pipe_tools.render_farm.workers import WorkerPaths, WorkerRecord


CLOUD_CONTROL_SOURCE = "cloud"
CLOUD_WORKER_STALE_AFTER_SECONDS = 180.0
_STATUS_QUEUE_NAMES = {
    "queued": NEEDS_RENDERING_FOLDER,
    "rendering": IS_RENDERING_FOLDER,
    "complete": RENDER_COMPLETE_FOLDER,
    "failed": RENDER_FAILED_FOLDER,
    "canceled": RENDER_FAILED_FOLDER,
}
_D1_RUNTIME_FIELDS = (
    "job_id",
    "batch_id",
    "project",
    "job_type",
    "shot_name",
    "render_version",
    "status",
    "priority",
    "submitted_utc",
    "submitted_by",
    "submitted_user",
    "attempt",
    "worker",
    "claimed_utc",
    "render_started_utc",
    "render_finished_utc",
    "progress",
    "result",
    "last_failure",
    "blacklisted_workers",
    "resubmitted_from_job_id",
    "revision",
)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _number(value: Any, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _queue_name(status: str) -> str:
    return _STATUS_QUEUE_NAMES.get(status.casefold(), RENDER_FAILED_FOLDER)


def _cloud_job_folder(
    repository_root: Path,
    project: str,
    status: str,
    job_id: str,
) -> Path:
    return (
        repository_root
        / project
        / RENDER_FARM_FOLDER_NAME
        / _queue_name(status)
        / job_id
    )


def _render_job_from_cloud_payload(
    payload: dict[str, Any],
    repository_root: Path,
    *,
    result_data: dict[str, Any] | None = None,
) -> RenderJob:
    project = _text(payload.get("project")) or "Unknown"
    status = _text(payload.get("status")) or "failed"
    job_id = _text(payload.get("job_id")) or "unknown-cloud-job"
    shot_name = _text(payload.get("shot_name"))
    render_version = _optional_int(payload.get("render_version"))
    job_name = (
        f"{shot_name}_v{render_version:03d}"
        if shot_name and render_version is not None
        else job_id
    )
    job_folder = _cloud_job_folder(repository_root, project, status, job_id)
    job_data = {
        **payload,
        DISPATCHER_COORDINATION_FIELD: CLOUD_DISPATCHER_COORDINATION,
    }
    selected_result = result_data or {}
    return RenderJob(
        project=project,
        submitted_project=project,
        queue_name=_queue_name(status),
        status=status,
        job_folder=job_folder,
        job_json_path=job_folder / JOB_FILENAME,
        result_json_path=job_folder / RESULT_FILENAME,
        job_id=job_id,
        job_name=job_name,
        shot_name=shot_name,
        render_version=render_version,
        submitted_user=_text(payload.get("submitted_user")),
        submitted_by=_text(payload.get("submitted_by")),
        submitted_utc=_text(payload.get("submitted_utc")),
        priority=_optional_int(payload.get("priority")),
        worker=_text(payload.get("worker")),
        frame_start=_optional_int(payload.get("frame_start")),
        frame_end=_optional_int(payload.get("frame_end")),
        frame_count=_optional_int(payload.get("frame_count")),
        progress=max(0.0, min(100.0, _number(payload.get("progress")))),
        error_count=1 if status.casefold() == "failed" else 0,
        render_started_utc=_text(payload.get("render_started_utc")),
        render_finished_utc=_text(
            payload.get("render_finished_utc")
            or selected_result.get("render_finished_utc")
        ),
        output_directory=_text(
            payload.get("worker_output_directory")
            or payload.get("output_directory")
            or payload.get("submitted_output_directory")
        ),
        render_config=_text(payload.get("render_config")),
        job_data=job_data,
        result_data=selected_result,
        load_error=None,
        control_source=CLOUD_CONTROL_SOURCE,
    )


def get_cloud_render_jobs(
    dispatcher: DispatcherClient,
    repository_root: str | Path,
) -> list[RenderJob]:
    """Load every Manager row from D1 without touching Dropbox queue folders."""
    root = Path(repository_root).expanduser()
    jobs: list[RenderJob] = []
    offset = 0
    page_size = 100
    while True:
        page = dispatcher.list_jobs(limit=page_size, offset=offset)
        jobs.extend(
            _render_job_from_cloud_payload(dict(summary), root)
            for summary in page
        )
        if len(page) < page_size:
            break
        offset += len(page)
    return jobs


def hydrate_cloud_render_job(
    job: RenderJob,
    dispatcher: DispatcherClient,
    repository_root: str | Path,
) -> RenderJob:
    """Load one full D1 payload for details, actions, and its bounded log tail."""
    response = dispatcher.get_job(job.job_id)
    payload_value = response.get("job")
    if not isinstance(payload_value, dict):
        raise DispatcherError(
            f"Cloud Dispatcher returned no payload for {job.job_id}.",
            code="invalid_dispatcher_response",
            response=response,
        )
    payload = dict(payload_value)
    result_value = payload.get("result")
    if not isinstance(result_value, dict):
        result_value = payload.get("last_failure")
    result = dict(result_value) if isinstance(result_value, dict) else {}
    snapshot = result.get("job_snapshot")
    if isinstance(snapshot, dict):
        # Worker-added path/Git diagnostics come from the terminal snapshot,
        # while lease/status/retry fields remain authoritative in D1.
        d1_runtime = {
            key: payload.get(key)
            for key in _D1_RUNTIME_FIELDS
            if key in payload
        }
        payload = {**payload, **snapshot, **d1_runtime}
    hydrated = _render_job_from_cloud_payload(
        payload,
        Path(repository_root).expanduser(),
        result_data=result,
    )
    return replace(hydrated, load_error=job.load_error)


def _parse_capabilities(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except ValueError:
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _parse_utc(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def get_cloud_render_workers(
    dispatcher: DispatcherClient,
    repository_root: str | Path,
    jobs: list[RenderJob],
) -> list[WorkerRecord]:
    """Build the Manager worker table from D1 check-ins."""
    root = Path(repository_root).expanduser()
    jobs_by_id = {job.job_id: job for job in jobs}
    now = datetime.now(timezone.utc)
    records: list[WorkerRecord] = []
    for raw_worker in dispatcher.list_workers():
        worker_name = _text(raw_worker.get("id"))
        if not worker_name:
            continue
        capabilities = _parse_capabilities(raw_worker.get("capabilities_json"))
        current_job_id = _text(raw_worker.get("current_job_id"))
        current_job = jobs_by_id.get(current_job_id)
        project = (
            _text(capabilities.get("project"))
            or (current_job.project if current_job is not None else "Cloud")
        )
        farm_root = root / project / RENDER_FARM_FOLDER_NAME
        paths = WorkerPaths.from_farm_root(farm_root, worker_name)
        last_seen_utc = _text(raw_worker.get("last_seen_at"))
        last_seen = _parse_utc(last_seen_utc)
        age = (
            max(0.0, (now - last_seen).total_seconds())
            if last_seen is not None
            else None
        )
        status = _text(raw_worker.get("status")) or "offline"
        stale = (
            status.casefold() == "offline"
            or age is None
            or age > CLOUD_WORKER_STALE_AFTER_SECONDS
        )
        raw_data = {
            **raw_worker,
            "capabilities": capabilities,
            "control_source": CLOUD_CONTROL_SOURCE,
        }
        records.append(
            WorkerRecord(
                project=project,
                farm_root=farm_root,
                status_file=paths.status_file,
                stop_file=paths.stop_file,
                worker_name=worker_name,
                machine_name=_text(raw_worker.get("display_name")) or worker_name,
                session_id="",
                status=status,
                started_utc=_text(raw_worker.get("first_seen_at")),
                last_heartbeat_utc=last_seen_utc,
                heartbeat_age_seconds=age,
                stale=stale,
                stop_requested=bool(raw_worker.get("stop_requested")),
                current_job_id=current_job_id,
                shot_name=current_job.shot_name if current_job is not None else "",
                render_version=(
                    f"v{current_job.render_version:03d}"
                    if current_job is not None
                    and current_job.render_version is not None
                    else ""
                ),
                render_setting=(
                    Path(current_job.render_config).stem
                    if current_job is not None and current_job.render_config
                    else ""
                ),
                worker_git_branch=_text(capabilities.get("git_branch")),
                worker_git_commit=_text(capabilities.get("git_commit")),
                process_id=None,
                raw_data=raw_data,
            )
        )
    return sorted(records, key=lambda item: item.worker_name.casefold())
