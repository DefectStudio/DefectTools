from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import socket
import stat as stat_module
import time
from typing import Any, TypeVar
from uuid import uuid4


SCHEMA_VERSION = 1
JOB_FILENAME = "job.json"
RESULT_FILENAME = "result.json"
BLACKLISTED_WORKERS_FIELD = "blacklisted_workers"
DISPATCHER_COORDINATION_FIELD = "dispatcher_coordination"
CLOUD_DISPATCHER_COORDINATION = "cloud"

WINDOWS_LOCK_RETRY_TIMEOUT_SECONDS = 15.0
WINDOWS_LOCK_RETRY_INITIAL_DELAY_SECONDS = 0.1
WINDOWS_LOCK_RETRY_MAX_DELAY_SECONDS = 1.0
COMPLETED_JOB_RECONCILIATION_GRACE_SECONDS = 60.0
TRANSIENT_WINDOWS_LOCK_ERRORS = frozenset((32, 33))
# Dropbox can report an atomic replacement or directory rename lock first as a
# sharing violation and then as access denied while it finishes observing the
# path. Limit WinError 5 retries to existence/publish/rename operations so
# genuine content read/write permission failures still fail immediately.
TRANSIENT_WINDOWS_PUBLISH_ERRORS = TRANSIENT_WINDOWS_LOCK_ERRORS | frozenset((5,))
TRANSIENT_WINDOWS_RENAME_ERRORS = TRANSIENT_WINDOWS_PUBLISH_ERRORS

SUBMITTING_FOLDER = "00_Submitting"
NEEDS_RENDERING_FOLDER = "01_NeedsRendering"
IS_RENDERING_FOLDER = "02_IsRendering"
RENDER_COMPLETE_FOLDER = "03_RenderComplete"
RENDER_FAILED_FOLDER = "04_RenderFailed"
WORKERS_FOLDER = "Workers"

QUEUE_FOLDER_NAMES: tuple[str, ...] = (
    SUBMITTING_FOLDER,
    NEEDS_RENDERING_FOLDER,
    IS_RENDERING_FOLDER,
    RENDER_COMPLETE_FOLDER,
    RENDER_FAILED_FOLDER,
)

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
LOGGER = logging.getLogger("render_worker.queue")
_OperationResult = TypeVar("_OperationResult")


@dataclass(frozen=True)
class QueuePaths:
    root: Path
    submitting: Path
    needs_rendering: Path
    is_rendering: Path
    render_complete: Path
    render_failed: Path
    workers: Path

    @classmethod
    def from_root(cls, farm_root: str | Path) -> QueuePaths:
        # Avoid resolving through a network/sync provider just to normalize text.
        root = Path(os.path.abspath(Path(farm_root).expanduser()))
        return cls(
            root=root,
            submitting=root / SUBMITTING_FOLDER,
            needs_rendering=root / NEEDS_RENDERING_FOLDER,
            is_rendering=root / IS_RENDERING_FOLDER,
            render_complete=root / RENDER_COMPLETE_FOLDER,
            render_failed=root / RENDER_FAILED_FOLDER,
            workers=root / WORKERS_FOLDER,
        )

    def all_queue_folders(self) -> tuple[Path, ...]:
        return (
            self.submitting,
            self.needs_rendering,
            self.is_rendering,
            self.render_complete,
            self.render_failed,
        )


@dataclass(frozen=True)
class JobCandidate:
    folder: Path
    priority: int
    submitted_utc: str

    def sort_key(self) -> tuple[int, str, str]:
        # Larger priority numbers render first. Equal priorities are FIFO.
        return (-self.priority, self.submitted_utc, self.folder.name.casefold())


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def safe_name(value: str, fallback: str) -> str:
    cleaned = _SAFE_NAME_RE.sub("-", value.strip()).strip("-._")
    return cleaned or fallback


def default_worker_name() -> str:
    return safe_name(os.environ.get("COMPUTERNAME") or socket.gethostname(), "WORKER")


def create_queue_folders(farm_root: str | Path) -> QueuePaths:
    paths = QueuePaths.from_root(farm_root)
    create_directory_with_retry(paths.root, parents=True, exist_ok=True)
    for folder in paths.all_queue_folders():
        create_directory_with_retry(folder, exist_ok=True)
    create_directory_with_retry(paths.workers, exist_ok=True)
    return paths


def retry_transient_windows_lock(
    operation: Callable[[], _OperationResult],
    description: str,
    timeout_seconds: float = WINDOWS_LOCK_RETRY_TIMEOUT_SECONDS,
    initial_delay_seconds: float = WINDOWS_LOCK_RETRY_INITIAL_DELAY_SECONDS,
    max_delay_seconds: float = WINDOWS_LOCK_RETRY_MAX_DELAY_SECONDS,
    sleep: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
    transient_winerrors: frozenset[int] = TRANSIENT_WINDOWS_LOCK_ERRORS,
) -> _OperationResult:
    """Retry the supplied Windows errors for a bounded filesystem operation."""
    sleep_function = sleep or time.sleep
    monotonic_function = monotonic or time.monotonic
    deadline = monotonic_function() + timeout_seconds
    delay_seconds = initial_delay_seconds

    while True:
        try:
            return operation()
        except OSError as error:
            winerror = getattr(error, "winerror", None)
            if winerror not in transient_winerrors:
                raise

            remaining_seconds = deadline - monotonic_function()
            if remaining_seconds <= 0:
                LOGGER.error(
                    "%s remained locked for %.1f seconds; giving up",
                    description,
                    timeout_seconds,
                )
                raise

            wait_seconds = min(delay_seconds, remaining_seconds)
            LOGGER.warning(
                "%s is temporarily locked by another process (WinError %s); "
                "retrying in %.1f seconds",
                description,
                winerror,
                wait_seconds,
            )
            sleep_function(wait_seconds)
            delay_seconds = min(delay_seconds * 2, max_delay_seconds)


def create_directory_with_retry(
    path: Path,
    parents: bool = False,
    exist_ok: bool = False,
) -> None:
    retry_transient_windows_lock(
        operation=lambda: path.mkdir(parents=parents, exist_ok=exist_ok),
        description=f"Create directory {path}",
    )


def path_exists_with_retry(path: Path) -> bool:
    def check_path() -> bool:
        try:
            path.stat()
        except FileNotFoundError:
            return False
        return True

    return retry_transient_windows_lock(
        operation=check_path,
        description=f"Check path {path}",
        transient_winerrors=TRANSIENT_WINDOWS_PUBLISH_ERRORS,
    )


def rename_path_with_retry(source: Path, destination: Path) -> None:
    retry_transient_windows_lock(
        operation=lambda: source.rename(destination),
        description=f"Rename {source} -> {destination}",
        transient_winerrors=TRANSIENT_WINDOWS_RENAME_ERRORS,
    )


def read_json_object(path: Path) -> dict[str, Any]:
    def read_json() -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"Expected a JSON object in {path}")
        return data

    return retry_transient_windows_lock(
        operation=read_json,
        description=f"Read JSON {path}",
    )


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    """Write JSON beside its destination, then replace the destination."""
    temporary_paths: list[Path] = []

    def write_temporary_json() -> Path:
        temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        temporary_paths.append(temporary_path)
        with temporary_path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=4, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return temporary_path

    try:
        temporary_path = retry_transient_windows_lock(
            operation=write_temporary_json,
            description=f"Write temporary JSON for {path}",
        )
        retry_transient_windows_lock(
            operation=lambda: os.replace(temporary_path, path),
            description=f"Publish JSON {path}",
            transient_winerrors=TRANSIENT_WINDOWS_PUBLISH_ERRORS,
        )
    finally:
        for temporary_path in temporary_paths:
            try:
                retry_transient_windows_lock(
                    operation=lambda path_to_remove=temporary_path: (
                        path_to_remove.unlink(missing_ok=True)
                    ),
                    description=f"Remove temporary JSON {temporary_path}",
                )
            except OSError as cleanup_error:
                LOGGER.warning(
                    "Could not remove temporary JSON file %s: %s",
                    temporary_path,
                    cleanup_error,
                )


def _validated_blacklisted_workers(
    job: dict[str, Any],
    job_path: Path,
) -> list[str]:
    raw_blacklisted_workers = job.get(BLACKLISTED_WORKERS_FIELD, [])
    if not isinstance(raw_blacklisted_workers, list):
        raise ValueError(
            f"Invalid {BLACKLISTED_WORKERS_FIELD} in {job_path}; expected a list"
        )

    blacklisted_workers: list[str] = []
    for worker_name in raw_blacklisted_workers:
        if not isinstance(worker_name, str) or not worker_name.strip():
            raise ValueError(
                f"Invalid worker name in {BLACKLISTED_WORKERS_FIELD} in {job_path}"
            )
        blacklisted_workers.append(worker_name.strip())
    return blacklisted_workers


def is_worker_blacklisted(
    job: dict[str, Any],
    worker_name: str,
    job_path: Path,
) -> bool:
    selected_worker = safe_name(worker_name, "WORKER").casefold()
    return any(
        blacklisted_worker.casefold() == selected_worker
        for blacklisted_worker in _validated_blacklisted_workers(job, job_path)
    )


def list_job_candidates(
    paths: QueuePaths,
    worker_name: str | None = None,
) -> list[JobCandidate]:
    candidates: list[JobCandidate] = []
    queue_entries = retry_transient_windows_lock(
        operation=lambda: list(paths.needs_rendering.iterdir()),
        description=f"Scan queue folder {paths.needs_rendering}",
    )
    for folder in queue_entries:
        try:
            folder_status = retry_transient_windows_lock(
                operation=folder.stat,
                description=f"Inspect queued path {folder}",
            )
        except FileNotFoundError:
            # Another worker may have claimed it after the directory scan.
            continue
        if not stat_module.S_ISDIR(folder_status.st_mode):
            continue

        priority = -1_000_000
        submitted_utc = "9999-12-31T23:59:59.999Z"
        try:
            job_path = folder / JOB_FILENAME
            job = read_json_object(job_path)
            if (
                worker_name is not None
                and str(job.get(DISPATCHER_COORDINATION_FIELD) or "").casefold()
                == CLOUD_DISPATCHER_COORDINATION
            ):
                # Cloud jobs may only be claimed after D1 grants the worker lease.
                continue
            if worker_name is not None and is_worker_blacklisted(
                job,
                worker_name,
                job_path,
            ):
                continue
            raw_priority = job.get("priority", priority)
            if isinstance(raw_priority, int) and not isinstance(raw_priority, bool):
                priority = raw_priority
            raw_submitted_utc = job.get("submitted_utc", submitted_utc)
            if isinstance(raw_submitted_utc, str) and raw_submitted_utc:
                submitted_utc = raw_submitted_utc
        except (OSError, ValueError):
            # Broken packages sort last, but are still claimed and failed so they
            # cannot poison the queue forever.
            pass

        candidates.append(
            JobCandidate(
                folder=folder,
                priority=priority,
                submitted_utc=submitted_utc,
            )
        )

    return sorted(candidates, key=JobCandidate.sort_key)


def claim_next_job(paths: QueuePaths, worker_name: str) -> Path | None:
    """Claim one job using a same-filesystem directory rename."""
    safe_worker_name = safe_name(worker_name, "WORKER")

    for candidate in list_job_candidates(paths, safe_worker_name):
        claimed_folder = paths.is_rendering / f"{candidate.folder.name}__{safe_worker_name}"
        if path_exists_with_retry(claimed_folder):
            raise FileExistsError(
                f"Claim destination already exists; manual inspection is required: "
                f"{claimed_folder}"
            )

        try:
            rename_path_with_retry(candidate.folder, claimed_folder)
        except FileNotFoundError:
            # Another worker won the rename race.
            continue

        # Re-read after the rename so a blacklist update that raced the initial
        # queue scan cannot result in this worker rendering the job.
        try:
            claimed_job_path = claimed_folder / JOB_FILENAME
            claimed_job = read_json_object(claimed_job_path)
            if is_worker_blacklisted(
                claimed_job,
                safe_worker_name,
                claimed_job_path,
            ):
                rename_path_with_retry(claimed_folder, candidate.folder)
                continue
        except (OSError, ValueError):
            # Invalid packages are intentionally returned as claimed so the
            # worker can move them to 04_RenderFailed instead of circulating.
            pass

        return claimed_folder

    return None


def claim_job_by_id(
    paths: QueuePaths,
    worker_name: str,
    job_id: str,
) -> Path | None:
    """Move the exact package already leased by the Cloud Dispatcher."""
    safe_worker_name = safe_name(worker_name, "WORKER")
    if safe_name(job_id, "") != job_id:
        raise ValueError(f"Cloud Dispatcher returned an unsafe job ID: {job_id!r}")

    queued_folder = paths.needs_rendering / job_id
    try:
        queued_job = read_json_object(queued_folder / JOB_FILENAME)
    except FileNotFoundError:
        # Dropbox may have announced the directory before job.json arrived.
        return None
    if str(queued_job.get("job_id") or "").strip() != job_id:
        raise ValueError(
            f"Queued package job ID does not match its Cloud lease: {queued_folder}"
        )

    claimed_folder = paths.is_rendering / f"{job_id}__{safe_worker_name}"
    if path_exists_with_retry(claimed_folder):
        raise FileExistsError(
            "Cloud-leased claim destination already exists; manual inspection "
            f"is required: {claimed_folder}"
        )
    try:
        rename_path_with_retry(queued_folder, claimed_folder)
    except FileNotFoundError:
        return None
    return claimed_folder


def recover_stranded_cloud_job_to_queue(
    paths: QueuePaths,
    job_id: str,
) -> Path | None:
    """Return one D1-coordinated package stranded in 02 to the queue.

    Callers must hold the active Cloud Dispatcher lease for ``job_id``.  The
    directory rename is deliberately exact and refuses ambiguous matches so a
    recovery can never guess which package is authoritative.
    """
    if safe_name(job_id, "") != job_id:
        raise ValueError(f"Cloud Dispatcher returned an unsafe job ID: {job_id!r}")

    queued_folder = paths.needs_rendering / job_id
    if path_exists_with_retry(queued_folder):
        return queued_folder

    prefix = f"{job_id}__"
    rendering_entries = retry_transient_windows_lock(
        operation=lambda: list(paths.is_rendering.iterdir()),
        description=f"Scan for stranded Cloud package {job_id}",
        transient_winerrors=TRANSIENT_WINDOWS_PUBLISH_ERRORS,
    )
    stranded_folders: list[Path] = []
    for entry in rendering_entries:
        try:
            entry_status = retry_transient_windows_lock(
                operation=entry.stat,
                description=f"Inspect possible stranded package {entry}",
            )
        except FileNotFoundError:
            continue
        if (
            stat_module.S_ISDIR(entry_status.st_mode)
            and entry.name.startswith(prefix)
        ):
            stranded_folders.append(entry)

    if not stranded_folders:
        return None
    if len(stranded_folders) > 1:
        matches = ", ".join(folder.name for folder in stranded_folders)
        raise FileExistsError(
            f"Multiple stranded packages match Cloud job {job_id}; manual "
            f"inspection is required: {matches}"
        )

    stranded_folder = stranded_folders[0]
    job_path = stranded_folder / JOB_FILENAME
    stranded_job = read_json_object(job_path)
    if str(stranded_job.get("job_id") or "").strip() != job_id:
        raise ValueError(
            f"Stranded package job ID does not match its Cloud lease: {job_path}"
        )
    if (
        str(stranded_job.get(DISPATCHER_COORDINATION_FIELD) or "").casefold()
        != CLOUD_DISPATCHER_COORDINATION
    ):
        raise ValueError(
            f"Refusing to recover a non-Cloud package as Cloud job {job_id}: "
            f"{job_path}"
        )
    if path_exists_with_retry(queued_folder):
        raise FileExistsError(
            f"Queued Cloud package appeared during recovery: {queued_folder}"
        )

    rename_path_with_retry(stranded_folder, queued_folder)
    return queued_folder


def validate_queued_job(job: dict[str, Any], job_path: Path) -> None:
    if job.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported or missing schema_version in {job_path}; "
            f"expected {SCHEMA_VERSION}"
        )

    if not isinstance(job.get("job_id"), str) or not job["job_id"].strip():
        raise ValueError(f"Missing or invalid job_id in {job_path}")

    if job.get("status") != "queued":
        raise ValueError(f"Expected status 'queued' in {job_path}")

    priority = job.get("priority")
    if not isinstance(priority, int) or isinstance(priority, bool):
        raise ValueError(f"Missing or invalid integer priority in {job_path}")

    if not isinstance(job.get("submitted_utc"), str) or not job["submitted_utc"]:
        raise ValueError(f"Missing or invalid submitted_utc in {job_path}")

    attempt = job.get("attempt", 0)
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 0:
        raise ValueError(f"Invalid attempt in {job_path}")

    _validated_blacklisted_workers(job, job_path)


def mark_job_rendering(claimed_folder: Path, worker_name: str) -> dict[str, Any]:
    job_path = claimed_folder / JOB_FILENAME
    job = read_json_object(job_path)
    validate_queued_job(job, job_path)

    now = utc_now()
    job["status"] = "rendering"
    job["worker"] = safe_name(worker_name, "WORKER")
    job["claimed_utc"] = now
    job["render_started_utc"] = now
    job["attempt"] = job.get("attempt", 0) + 1
    write_json_atomic(job_path, job)
    return job


def mark_cloud_job_rendering(
    claimed_folder: Path,
    worker_name: str,
    cloud_job: dict[str, Any],
) -> dict[str, Any]:
    """Publish the D1-authoritative leased payload into the Dropbox package."""
    job = dict(cloud_job)
    job_id = str(job.get("job_id") or "").strip()
    if not job_id or safe_name(job_id, "") != job_id:
        raise ValueError("Cloud-leased job has an invalid job_id")
    if job.get("status") != "rendering":
        raise ValueError(f"Cloud-leased job {job_id} is not rendering")
    expected_worker = safe_name(worker_name, "WORKER")
    if str(job.get("worker") or "").casefold() != expected_worker.casefold():
        raise ValueError(
            f"Cloud-leased job {job_id} belongs to {job.get('worker')!r}, "
            f"not {expected_worker!r}"
        )
    attempt = job.get("attempt")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        raise ValueError(f"Cloud-leased job {job_id} has an invalid attempt")
    write_json_atomic(claimed_folder / JOB_FILENAME, job)
    return job


def reconcile_completed_jobs(paths: QueuePaths) -> list[Path]:
    """Move completed packages stranded in 02_IsRendering to completion."""
    try:
        entries = retry_transient_windows_lock(
            operation=lambda: list(paths.is_rendering.iterdir()),
            description=f"Scan for completed jobs in {paths.is_rendering}",
            transient_winerrors=TRANSIENT_WINDOWS_PUBLISH_ERRORS,
        )
    except OSError as error:
        LOGGER.warning(
            "Could not scan for completed jobs to reconcile; a later worker "
            "check will retry: %s: %s",
            type(error).__name__,
            error,
        )
        return []

    recovered: list[Path] = []
    for folder in sorted(entries, key=lambda entry: entry.name.casefold()):
        try:
            if not folder.is_dir():
                continue
            job = read_json_object(folder / JOB_FILENAME)
        except (OSError, ValueError) as error:
            LOGGER.debug(
                "Skipping unreconcilable package %s: %s: %s",
                folder,
                type(error).__name__,
                error,
            )
            continue

        if job.get("status") != "complete":
            continue

        finished_utc = job.get("render_finished_utc")
        if not isinstance(finished_utc, str) or not finished_utc.strip():
            continue
        try:
            finished_at = datetime.fromisoformat(
                finished_utc.strip().replace("Z", "+00:00")
            )
        except ValueError:
            continue
        if finished_at.tzinfo is None:
            continue
        completion_age_seconds = (
            datetime.now(timezone.utc) - finished_at.astimezone(timezone.utc)
        ).total_seconds()
        if completion_age_seconds < COMPLETED_JOB_RECONCILIATION_GRACE_SECONDS:
            continue

        try:
            result = read_json_object(folder / RESULT_FILENAME)
        except (OSError, ValueError) as error:
            LOGGER.debug(
                "Completed package is not ready for reconciliation %s: %s: %s",
                folder,
                type(error).__name__,
                error,
            )
            continue
        if result.get("status") != "complete":
            continue

        destination = paths.render_complete / folder.name
        try:
            if path_exists_with_retry(destination):
                # Another worker may have completed the same reconciliation
                # after this scan captured its directory entry.
                if not path_exists_with_retry(folder):
                    continue
                LOGGER.error(
                    "Completed job remains stranded because its destination "
                    "already exists: source=%s, destination=%s",
                    folder,
                    destination,
                )
                continue
            rename_path_with_retry(folder, destination)
        except FileNotFoundError:
            # Another worker won the recovery rename.
            continue
        except OSError as error:
            LOGGER.warning(
                "Completed job remains in 02_IsRendering; a later worker check "
                "will retry: %s -> %s (%s: %s)",
                folder,
                destination,
                type(error).__name__,
                error,
            )
            continue

        LOGGER.info("Reconciled completed job: %s", destination)
        recovered.append(destination)

    return recovered


def finish_claimed_job(
    paths: QueuePaths,
    claimed_folder: Path,
    job: dict[str, Any],
    worker_name: str,
    success: bool,
    reason: str,
    result_details: dict[str, Any] | None = None,
) -> Path:
    status = "complete" if success else "failed"
    finished_utc = utc_now()
    result = {
        "schema_version": SCHEMA_VERSION,
        "job_id": job.get("job_id"),
        "status": status,
        "worker": safe_name(worker_name, "WORKER"),
        "simulated": True,
        "exit_code": 0 if success else 1,
        "reason": reason,
        "render_started_utc": job.get("render_started_utc"),
        "render_finished_utc": finished_utc,
    }
    if result_details:
        result.update(result_details)

    # State-machine fields are authoritative even when execution-specific
    # diagnostics are merged into the result.
    result["schema_version"] = SCHEMA_VERSION
    result["job_id"] = job.get("job_id")
    result["status"] = status
    result["worker"] = safe_name(worker_name, "WORKER")
    result["reason"] = reason
    result["render_started_utc"] = job.get("render_started_utc")
    result["render_finished_utc"] = finished_utc

    if not success:
        return requeue_failed_job(
            paths=paths,
            claimed_folder=claimed_folder,
            job=job,
            worker_name=worker_name,
            result=result,
        )

    job["status"] = status
    job["render_finished_utc"] = finished_utc
    job["result"] = result
    write_json_atomic(claimed_folder / JOB_FILENAME, job)
    write_json_atomic(claimed_folder / RESULT_FILENAME, result)

    destination = paths.render_complete / claimed_folder.name
    if path_exists_with_retry(destination):
        raise FileExistsError(
            f"Terminal job destination already exists; manual inspection is required: "
            f"{destination}"
        )
    rename_path_with_retry(claimed_folder, destination)
    return destination


def requeue_failed_job(
    paths: QueuePaths,
    claimed_folder: Path,
    job: dict[str, Any],
    worker_name: str,
    result: dict[str, Any],
) -> Path:
    """Blacklist the failed worker and atomically return the job to the queue."""
    safe_worker_name = safe_name(worker_name, "WORKER")
    job_path = claimed_folder / JOB_FILENAME
    blacklisted_workers = _validated_blacklisted_workers(job, job_path)
    if not any(
        existing_worker.casefold() == safe_worker_name.casefold()
        for existing_worker in blacklisted_workers
    ):
        blacklisted_workers.append(safe_worker_name)

    job[BLACKLISTED_WORKERS_FIELD] = blacklisted_workers
    job["status"] = "queued"
    job["worker"] = None
    job["claimed_utc"] = None
    job["render_started_utc"] = None
    job["render_finished_utc"] = None
    job["result"] = None
    job["last_failure"] = result
    write_json_atomic(job_path, job)
    write_json_atomic(claimed_folder / RESULT_FILENAME, result)

    claimed_suffix = f"__{safe_worker_name}"
    if not claimed_folder.name.casefold().endswith(claimed_suffix.casefold()):
        raise ValueError(
            "Claimed job folder does not end with its worker name: "
            f"{claimed_folder}"
        )
    queued_name = claimed_folder.name[: -len(claimed_suffix)]
    destination = paths.needs_rendering / queued_name
    if path_exists_with_retry(destination):
        raise FileExistsError(
            f"Requeued job destination already exists; manual inspection is required: "
            f"{destination}"
        )
    rename_path_with_retry(claimed_folder, destination)
    return destination


def fail_unreadable_claimed_job(
    paths: QueuePaths,
    claimed_folder: Path,
    worker_name: str,
    reason: str,
) -> Path:
    result = {
        "schema_version": SCHEMA_VERSION,
        "job_id": None,
        "status": "failed",
        "worker": safe_name(worker_name, "WORKER"),
        "simulated": True,
        "exit_code": 1,
        "reason": reason,
        "render_started_utc": None,
        "render_finished_utc": utc_now(),
    }
    write_json_atomic(claimed_folder / RESULT_FILENAME, result)

    destination = paths.render_failed / claimed_folder.name
    if path_exists_with_retry(destination):
        raise FileExistsError(
            f"Failed-job destination already exists; manual inspection is required: "
            f"{destination}"
        )
    rename_path_with_retry(claimed_folder, destination)
    return destination
