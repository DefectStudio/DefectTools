from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any

from portable_pipe_tools.render_farm.cloud_dispatch import (
    CloudJobLease,
    DispatcherClient,
    DispatcherError,
)
from portable_pipe_tools.render_farm.queue import (
    JOB_FILENAME,
    QueuePaths,
    fail_unreadable_claimed_job,
    finish_claimed_job,
    read_json_object,
    retry_transient_windows_lock,
    utc_now,
    write_json_atomic,
)


PENDING_DISPATCHER_UPDATE_FILENAME = "dispatcher_update_pending.json"
STALE_DISPATCHER_UPDATE_PREFIX = "dispatcher_update_stale"
PENDING_UPDATE_RECONCILIATION_GRACE_SECONDS = 60.0
LOGGER = logging.getLogger("render_worker.cloud_queue")


def _pending_path(folder: Path) -> Path:
    return folder / PENDING_DISPATCHER_UPDATE_FILENAME


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
) -> Path:
    pending = {
        "schema_version": 1,
        "created_utc": utc_now(),
        "action": "complete" if success else "fail",
        "job_id": lease.job_id,
        "worker_id": worker_name,
        "lease_token": lease.lease_token,
        "reason": reason,
        "retryable": not success,
        "result": result_details or {},
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
        result_details=result_details,
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
    """Finish durable Dropbox outbox records left by a crash/network outage."""
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
