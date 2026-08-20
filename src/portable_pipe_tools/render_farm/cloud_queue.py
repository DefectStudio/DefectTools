from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import shutil
from typing import Any

from portable_pipe_tools.render_farm.cloud_dispatch import (
    CloudJobLease,
    DispatcherClient,
    DispatcherError,
)
from portable_pipe_tools.render_farm.queue import (
    JOB_FILENAME,
    QueuePaths,
    TRANSIENT_WINDOWS_PUBLISH_ERRORS,
    create_directory_with_retry,
    fail_unreadable_claimed_job,
    finish_claimed_job,
    path_exists_with_retry,
    read_json_object,
    recover_stranded_cloud_job_to_queue,
    rename_path_with_retry,
    retry_transient_windows_lock,
    safe_name,
    utc_now,
    write_json_atomic,
)


PENDING_DISPATCHER_UPDATE_FILENAME = "dispatcher_update_pending.json"
STALE_DISPATCHER_UPDATE_PREFIX = "dispatcher_update_stale"
PENDING_UPDATE_RECONCILIATION_GRACE_SECONDS = 60.0
LOGGER = logging.getLogger("render_worker.cloud_queue")
DEFAULT_LOCAL_SPOOL_FOLDER_NAME = "CloudJobSpool"
MAX_CLOUD_RENDER_LOG_TAIL_BYTES = 64 * 1024
CLOUD_RENDER_LOG_FILENAMES = (
    "unreal.log",
    "unreal_stdout.log",
    "git_pull.log",
)


def get_default_cloud_spool_root(worker_name: str) -> Path:
    """Return this machine's private control-package root for one worker."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data)
    else:
        base = Path.home() / "AppData" / "Local"
    override = os.environ.get("DEFECT_FARM_LOCAL_SPOOL_ROOT")
    spool_base = (
        Path(override).expanduser()
        if override
        else base / "DefectStudio" / "RenderFarm" / DEFAULT_LOCAL_SPOOL_FOLDER_NAME
    )
    return spool_base / safe_name(worker_name, "WORKER")


def materialize_cloud_job_package(
    paths: QueuePaths,
    cloud_job: dict[str, Any],
) -> Path:
    """Atomically materialize a D1-leased payload into the local worker spool."""
    job_id = str(cloud_job.get("job_id") or "").strip()
    if not job_id or safe_name(job_id, "") != job_id:
        raise ValueError("Cloud-leased job has an invalid job_id")
    if cloud_job.get("status") != "rendering":
        raise ValueError(f"Cloud-leased job {job_id} is not rendering")

    queued_folder = paths.needs_rendering / job_id
    if not path_exists_with_retry(queued_folder):
        recovered = recover_stranded_cloud_job_to_queue(paths, job_id)
        if recovered is not None:
            queued_folder = recovered

    if path_exists_with_retry(queued_folder):
        write_json_atomic(queued_folder / JOB_FILENAME, dict(cloud_job))
        return queued_folder

    staging_folder = paths.submitting / job_id
    if path_exists_with_retry(staging_folder):
        if not staging_folder.is_dir():
            raise NotADirectoryError(
                f"Local Cloud staging path is not a directory: {staging_folder}"
            )
        LOGGER.warning(
            "Recovering interrupted local Cloud job staging folder: %s",
            staging_folder,
        )
    else:
        create_directory_with_retry(staging_folder)
    write_json_atomic(staging_folder / JOB_FILENAME, dict(cloud_job))
    try:
        rename_path_with_retry(staging_folder, queued_folder)
    except Exception:
        # The complete D1 payload remains durable in D1. Leaving the staging
        # folder intact makes a local disk failure visible for diagnosis.
        raise
    return queued_folder


def _pending_path(folder: Path) -> Path:
    return folder / PENDING_DISPATCHER_UPDATE_FILENAME


def _read_render_log_tail(
    claimed_folder: Path,
    result: dict[str, Any],
) -> str:
    requested_names = (
        result.get("unreal_log_file"),
        "unreal.log",
        result.get("unreal_stdout_file"),
        "unreal_stdout.log",
    )
    seen: set[Path] = set()
    for requested_name in requested_names:
        if not requested_name:
            continue
        candidate = claimed_folder / Path(str(requested_name)).name
        if candidate in seen or not candidate.is_file():
            continue
        seen.add(candidate)

        def read_tail(path: Path = candidate) -> bytes:
            with path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                length = handle.tell()
                handle.seek(max(0, length - MAX_CLOUD_RENDER_LOG_TAIL_BYTES))
                return handle.read(MAX_CLOUD_RENDER_LOG_TAIL_BYTES)

        raw_tail = retry_transient_windows_lock(
            operation=read_tail,
            description=f"Read Cloud render log tail {candidate}",
        )
        if raw_tail:
            return raw_tail.decode("utf-8", errors="replace")
    return ""


def _cloud_result_details(
    claimed_folder: Path,
    job: dict[str, Any],
    result_details: dict[str, Any] | None,
) -> dict[str, Any]:
    result = dict(result_details or {})
    # Preserve worker-added path/Git diagnostics without rewriting the queued
    # D1 payload. Manager detail views merge this bounded snapshot lazily.
    result["job_snapshot"] = dict(job)
    log_tail = _read_render_log_tail(claimed_folder, result)
    if log_tail:
        result["render_log_tail"] = log_tail
        result["render_log_tail_truncated"] = (
            len(log_tail.encode("utf-8", errors="replace"))
            >= MAX_CLOUD_RENDER_LOG_TAIL_BYTES
        )
    return result


def _render_log_archive_folder(
    shared_farm_root: str | Path,
    job: dict[str, Any],
    worker_name: str,
    success: bool,
) -> Path:
    job_id = safe_name(str(job.get("job_id") or ""), "JOB")
    worker = safe_name(worker_name, "WORKER")
    raw_attempt = job.get("attempt")
    attempt = (
        raw_attempt
        if isinstance(raw_attempt, int)
        and not isinstance(raw_attempt, bool)
        and raw_attempt >= 0
        else 0
    )
    shared_paths = QueuePaths.from_root(shared_farm_root)
    state_folder = (
        shared_paths.render_complete if success else shared_paths.render_failed
    )
    return state_folder / f"{job_id}__{worker}__attempt_{attempt:03d}"


def _copy_render_log_atomic(source: Path, destination: Path) -> None:
    temporary = destination.with_name(f".{destination.name}.uploading")
    try:
        retry_transient_windows_lock(
            operation=lambda: shutil.copyfile(source, temporary),
            description=f"Copy render log {source} -> {temporary}",
            transient_winerrors=TRANSIENT_WINDOWS_PUBLISH_ERRORS,
        )
        retry_transient_windows_lock(
            operation=lambda: os.replace(temporary, destination),
            description=f"Publish render log {temporary} -> {destination}",
            transient_winerrors=TRANSIENT_WINDOWS_PUBLISH_ERRORS,
        )
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            LOGGER.warning(
                "Could not remove temporary Dropbox render log: %s",
                temporary,
            )


def publish_cloud_render_logs(
    *,
    claimed_folder: Path,
    shared_farm_root: str | Path,
    job: dict[str, Any],
    worker_name: str,
    success: bool,
) -> list[Path]:
    """Best-effort copy of small terminal logs into the Dropbox archive."""
    try:
        sources = [
            claimed_folder / filename
            for filename in CLOUD_RENDER_LOG_FILENAMES
            if (claimed_folder / filename).is_file()
        ]
    except OSError as error:
        LOGGER.warning(
            "Could not inspect worker-local render logs for Dropbox publication: "
            "%s: %s",
            type(error).__name__,
            error,
        )
        return []
    if not sources:
        LOGGER.warning(
            "No worker-local render logs were available for Dropbox publication: %s",
            claimed_folder,
        )
        return []

    destination_folder = _render_log_archive_folder(
        shared_farm_root,
        job,
        worker_name,
        success,
    )
    try:
        retry_transient_windows_lock(
            operation=lambda: destination_folder.mkdir(parents=True, exist_ok=True),
            description=f"Create Dropbox render log folder {destination_folder}",
            transient_winerrors=TRANSIENT_WINDOWS_PUBLISH_ERRORS,
        )
    except OSError as error:
        LOGGER.warning(
            "Could not create the Dropbox render log folder; D1 job completion "
            "will continue: %s (%s: %s)",
            destination_folder,
            type(error).__name__,
            error,
        )
        return []

    published: list[Path] = []
    for source in sources:
        destination = destination_folder / source.name
        try:
            _copy_render_log_atomic(source, destination)
        except OSError as error:
            LOGGER.warning(
                "Could not publish render log to Dropbox; D1 job completion "
                "will continue: %s -> %s (%s: %s)",
                source,
                destination,
                type(error).__name__,
                error,
            )
            continue
        published.append(destination)

    if published:
        LOGGER.info(
            "Published %d render log file(s) to Dropbox: %s",
            len(published),
            destination_folder,
        )
    return published


def _remove_pending_update(path: Path) -> None:
    retry_transient_windows_lock(
        operation=lambda: path.unlink(missing_ok=True),
        description=f"Remove completed Dispatcher update {path}",
    )


def _quarantine_stale_update(path: Path) -> Path | None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    destination = path.with_name(
        f"{STALE_DISPATCHER_UPDATE_PREFIX}_{timestamp}.json"
    )
    try:
        retry_transient_windows_lock(
            operation=lambda: path.rename(destination),
            description=f"Quarantine stale Dispatcher update {path}",
        )
    except FileNotFoundError:
        # Another worker may have quarantined the shared receipt first.
        return None
    return destination


def _send_pending_update(
    dispatcher: DispatcherClient,
    pending: dict[str, Any],
) -> None:
    action = pending.get("action")
    job_id = str(pending.get("job_id") or "").strip()
    worker_id = str(pending.get("worker_id") or "").strip()
    lease_token = str(pending.get("lease_token") or "").strip()
    reason = str(pending.get("reason") or "").strip()
    result = pending.get("result")
    if not isinstance(result, dict):
        result = {}
    if not job_id or not worker_id or not lease_token:
        raise ValueError("Pending Dispatcher update is missing its lease identity")
    if action == "complete":
        dispatcher.complete_job(
            job_id,
            worker_id,
            lease_token,
            result=result,
            reason=reason,
        )
        return
    if action == "fail":
        dispatcher.fail_job(
            job_id,
            worker_id,
            lease_token,
            reason=reason or "Render failed",
            retryable=bool(pending.get("retryable", True)),
            result=result,
        )
        return
    raise ValueError(f"Unsupported pending Dispatcher action: {action!r}")


def finish_cloud_claimed_job(
    *,
    dispatcher: DispatcherClient,
    paths: QueuePaths,
    claimed_folder: Path,
    job: dict[str, Any],
    worker_name: str,
    lease: CloudJobLease,
    success: bool,
    reason: str,
    result_details: dict[str, Any] | None,
    shared_farm_root: str | Path,
) -> Path:
    cloud_result = _cloud_result_details(
        claimed_folder,
        job,
        result_details,
    )
    published_logs = (
        publish_cloud_render_logs(
            claimed_folder=claimed_folder,
            shared_farm_root=shared_farm_root,
            job=job,
            worker_name=worker_name,
            success=success,
        )
        if result_details is not None
        and result_details.get("simulated") is False
        else []
    )
    if published_logs:
        archive_folder = published_logs[0].parent
        cloud_result["dropbox_render_log_relative_folder"] = archive_folder.relative_to(
            QueuePaths.from_root(shared_farm_root).root
        ).as_posix()
        cloud_result["dropbox_render_log_files"] = [
            path.name for path in published_logs
        ]
    pending = {
        "schema_version": 1,
        "created_utc": utc_now(),
        "action": "complete" if success else "fail",
        "job_id": lease.job_id,
        "worker_id": worker_name,
        "lease_token": lease.lease_token,
        "reason": reason,
        "retryable": not success,
        "result": cloud_result,
        "invalid_package": False,
    }
    write_json_atomic(_pending_path(claimed_folder), pending)
    final_folder = finish_claimed_job(
        paths=paths,
        claimed_folder=claimed_folder,
        job=job,
        worker_name=worker_name,
        success=success,
        reason=reason,
        result_details=cloud_result,
    )
    final_pending_path = _pending_path(final_folder)
    _send_pending_update(dispatcher, pending)
    _remove_pending_update(final_pending_path)
    return final_folder


def finish_invalid_cloud_claim(
    *,
    dispatcher: DispatcherClient,
    paths: QueuePaths,
    claimed_folder: Path,
    worker_name: str,
    lease: CloudJobLease,
    reason: str,
) -> Path:
    pending = {
        "schema_version": 1,
        "created_utc": utc_now(),
        "action": "fail",
        "job_id": lease.job_id,
        "worker_id": worker_name,
        "lease_token": lease.lease_token,
        "reason": reason,
        "retryable": False,
        "result": {"invalid_package": True},
        "invalid_package": True,
    }
    write_json_atomic(_pending_path(claimed_folder), pending)
    final_folder = fail_unreadable_claimed_job(
        paths=paths,
        claimed_folder=claimed_folder,
        worker_name=worker_name,
        reason=reason,
    )
    final_pending_path = _pending_path(final_folder)
    _send_pending_update(dispatcher, pending)
    _remove_pending_update(final_pending_path)
    return final_folder


def _created_age_seconds(pending: dict[str, Any]) -> float | None:
    value = pending.get("created_utc")
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        created = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if created.tzinfo is None:
        return None
    return (datetime.now(timezone.utc) - created.astimezone(timezone.utc)).total_seconds()


def reconcile_pending_cloud_updates(
    paths: QueuePaths,
    dispatcher: DispatcherClient,
    *,
    minimum_age_seconds: float = PENDING_UPDATE_RECONCILIATION_GRACE_SECONDS,
) -> list[Path]:
    """Finish durable local outbox records left by a crash/network outage."""
    reconciled: list[Path] = []
    for state_folder in paths.all_queue_folders():
        try:
            entries = retry_transient_windows_lock(
                operation=lambda folder=state_folder: list(folder.iterdir()),
                description=f"Scan pending Dispatcher updates in {state_folder}",
            )
        except OSError as error:
            LOGGER.warning("Could not scan %s for Dispatcher updates: %s", state_folder, error)
            continue
        for folder in entries:
            if not folder.is_dir():
                continue
            pending_path = _pending_path(folder)
            try:
                pending = read_json_object(pending_path)
            except FileNotFoundError:
                continue
            age_seconds = _created_age_seconds(pending)
            if age_seconds is not None and age_seconds < minimum_age_seconds:
                continue

            final_folder = folder
            if folder.parent == paths.is_rendering:
                worker_name = str(pending.get("worker_id") or "").strip()
                reason = str(pending.get("reason") or "").strip()
                if pending.get("invalid_package") is True:
                    final_folder = fail_unreadable_claimed_job(
                        paths=paths,
                        claimed_folder=folder,
                        worker_name=worker_name,
                        reason=reason,
                    )
                else:
                    job = read_json_object(folder / JOB_FILENAME)
                    result = pending.get("result")
                    final_folder = finish_claimed_job(
                        paths=paths,
                        claimed_folder=folder,
                        job=job,
                        worker_name=worker_name,
                        success=pending.get("action") == "complete",
                        reason=reason,
                        result_details=result if isinstance(result, dict) else {},
                    )

            try:
                _send_pending_update(dispatcher, pending)
            except DispatcherError as error:
                if error.status != 409 or error.code != "lease_lost":
                    raise
                quarantined_path = _quarantine_stale_update(
                    _pending_path(final_folder)
                )
                LOGGER.warning(
                    "Cloud Dispatcher rejected stale update for %s because its "
                    "lease is no longer authoritative; quarantined receipt: %s",
                    pending.get("job_id"),
                    quarantined_path or "already quarantined by another worker",
                )
                continue
            _remove_pending_update(_pending_path(final_folder))
            LOGGER.info("Reconciled pending Cloud Dispatcher update: %s", final_folder)
            reconciled.append(final_folder)
    return reconciled
