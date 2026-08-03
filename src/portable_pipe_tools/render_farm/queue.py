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

WINDOWS_LOCK_RETRY_TIMEOUT_SECONDS = 15.0
WINDOWS_LOCK_RETRY_INITIAL_DELAY_SECONDS = 0.1
WINDOWS_LOCK_RETRY_MAX_DELAY_SECONDS = 1.0
TRANSIENT_WINDOWS_LOCK_ERRORS = frozenset((32, 33))

SUBMITTING_FOLDER = "00_Submitting"
NEEDS_RENDERING_FOLDER = "01_NeedsRendering"
IS_RENDERING_FOLDER = "02_IsRendering"
RENDER_COMPLETE_FOLDER = "03_RenderComplete"
RENDER_FAILED_FOLDER = "04_RenderFailed"

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
    return paths


def retry_transient_windows_lock(
    operation: Callable[[], _OperationResult],
    description: str,
    timeout_seconds: float = WINDOWS_LOCK_RETRY_TIMEOUT_SECONDS,
    initial_delay_seconds: float = WINDOWS_LOCK_RETRY_INITIAL_DELAY_SECONDS,
    max_delay_seconds: float = WINDOWS_LOCK_RETRY_MAX_DELAY_SECONDS,
    sleep: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
) -> _OperationResult:
    """Retry only Windows sharing/lock violations from filesystem observers."""
    sleep_function = sleep or time.sleep
    monotonic_function = monotonic or time.monotonic
    deadline = monotonic_function() + timeout_seconds
    delay_seconds = initial_delay_seconds

    while True:
        try:
            return operation()
        except OSError as error:
            winerror = getattr(error, "winerror", None)
            if winerror not in TRANSIENT_WINDOWS_LOCK_ERRORS:
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
    )


def rename_path_with_retry(source: Path, destination: Path) -> None:
    retry_transient_windows_lock(
        operation=lambda: source.rename(destination),
        description=f"Rename {source} -> {destination}",
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


def list_job_candidates(paths: QueuePaths) -> list[JobCandidate]:
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
            job = read_json_object(folder / JOB_FILENAME)
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

    for candidate in list_job_candidates(paths):
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

        return claimed_folder

    return None


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

    job["status"] = status
    job["render_finished_utc"] = finished_utc
    job["result"] = result
    write_json_atomic(claimed_folder / JOB_FILENAME, job)
    write_json_atomic(claimed_folder / RESULT_FILENAME, result)

    destination_root = paths.render_complete if success else paths.render_failed
    destination = destination_root / claimed_folder.name
    if path_exists_with_retry(destination):
        raise FileExistsError(
            f"Terminal job destination already exists; manual inspection is required: "
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
