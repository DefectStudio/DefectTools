from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
from queue import Empty, Queue
import socket
from threading import Event, Lock, Thread
from typing import Any
from uuid import uuid4

from portable_pipe_tools.render_farm.queue import (
    create_directory_with_retry,
    path_exists_with_retry,
    read_json_object,
    retry_transient_windows_lock,
    safe_name,
    utc_now,
    write_json_atomic,
)


LOGGER = logging.getLogger("render_worker")

WORKERS_FOLDER_NAME = "Workers"
WORKER_STATUS_SUFFIX = "_STATUS.json"
WORKER_STOP_SUFFIX = "_STOP.json"
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 10.0
DEFAULT_STALE_AFTER_SECONDS = 45.0
WORKER_STATUS_TRANSIENT_ERRORS = frozenset((5, 32, 33))


class WorkerAlreadyActiveError(RuntimeError):
    """Raised when a fresh status file already owns a worker name."""


class WorkerStopRequestedError(RuntimeError):
    """Raised when a pending empty STOP marker prevents worker startup."""


@dataclass(frozen=True)
class WorkerPaths:
    workers_folder: Path
    status_file: Path
    stop_file: Path

    @classmethod
    def from_farm_root(
        cls,
        farm_root: str | Path,
        worker_name: str,
    ) -> WorkerPaths:
        root = Path(os.path.abspath(Path(farm_root).expanduser()))
        safe_worker_name = safe_name(worker_name, "WORKER")
        workers_folder = root / WORKERS_FOLDER_NAME
        return cls(
            workers_folder=workers_folder,
            status_file=workers_folder / f"{safe_worker_name}{WORKER_STATUS_SUFFIX}",
            stop_file=workers_folder / f"{safe_worker_name}{WORKER_STOP_SUFFIX}",
        )


@dataclass(frozen=True)
class WorkerRecord:
    project: str
    farm_root: Path
    status_file: Path
    stop_file: Path
    worker_name: str
    machine_name: str
    session_id: str
    status: str
    started_utc: str
    last_heartbeat_utc: str
    heartbeat_age_seconds: float | None
    stale: bool
    stop_requested: bool
    current_job_id: str
    shot_name: str
    render_version: str
    render_setting: str
    worker_git_branch: str
    worker_git_commit: str
    process_id: int | None
    raw_data: dict[str, Any]
    load_error: str | None = None

    @property
    def status_label(self) -> str:
        if self.load_error:
            return "Unreadable"
        if self.stale:
            return "Stale"
        if self.stop_requested and self.status != "stopping_after_current_job":
            return "Stop Requested"
        labels = {
            "starting": "Starting",
            "waiting": "Waiting",
            "moving_files": "Moving Files",
            "rendering": "Rendering",
            "finishing": "Finishing",
            "stopping_after_current_job": "Stopping After Job",
        }
        return labels.get(
            self.status,
            self.status.replace("_", " ").strip().title() or "Unknown",
        )

    @property
    def current_job_label(self) -> str:
        pieces = [piece for piece in (self.shot_name, self.render_version) if piece]
        return " ".join(pieces) or self.current_job_id or "—"

    @property
    def last_seen_label(self) -> str:
        age = self.heartbeat_age_seconds
        if age is None:
            return "Unknown"
        seconds = max(0, int(age))
        if seconds < 60:
            return f"{seconds} sec ago"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} min ago"
        hours = minutes // 60
        return f"{hours} hr ago"


def ensure_workers_folder(farm_root: str | Path) -> Path:
    workers_folder = Path(os.path.abspath(Path(farm_root).expanduser())) / WORKERS_FOLDER_NAME
    create_directory_with_retry(workers_folder, parents=True, exist_ok=True)
    return workers_folder


def create_worker_stop_request(
    farm_root: str | Path,
    worker_name: str,
) -> Path:
    paths = WorkerPaths.from_farm_root(farm_root, worker_name)
    ensure_workers_folder(farm_root)
    retry_transient_windows_lock(
        operation=lambda: paths.stop_file.touch(exist_ok=True),
        description=f"Create worker STOP marker {paths.stop_file}",
    )
    return paths.stop_file


def clear_worker_stop_request(
    farm_root: str | Path,
    worker_name: str,
) -> None:
    paths = WorkerPaths.from_farm_root(farm_root, worker_name)
    retry_transient_windows_lock(
        operation=lambda: paths.stop_file.unlink(missing_ok=True),
        description=f"Remove worker STOP marker {paths.stop_file}",
    )


def _parse_utc(value: str) -> datetime | None:
    raw_value = value.strip()
    if not raw_value:
        return None
    try:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _heartbeat_age_seconds(
    heartbeat_utc: str,
    now: datetime,
) -> float | None:
    parsed = _parse_utc(heartbeat_utc)
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds())


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def read_worker_record(
    status_file: Path,
    *,
    project: str,
    farm_root: Path,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
    now: datetime | None = None,
) -> WorkerRecord:
    selected_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    load_error: str | None = None
    try:
        data = read_json_object(status_file)
    except (FileNotFoundError, OSError, ValueError) as error:
        data = {}
        load_error = str(error)

    filename_worker_name = status_file.name[: -len(WORKER_STATUS_SUFFIX)]
    worker_name = _text(data.get("worker_name")) or filename_worker_name
    paths = WorkerPaths.from_farm_root(farm_root, worker_name)
    last_heartbeat_utc = _text(data.get("last_heartbeat_utc"))
    heartbeat_age = _heartbeat_age_seconds(last_heartbeat_utc, selected_now)
    stale = (
        load_error is not None
        or heartbeat_age is None
        or heartbeat_age > stale_after_seconds
    )
    try:
        stop_requested = path_exists_with_retry(paths.stop_file)
    except OSError:
        stop_requested = False

    return WorkerRecord(
        project=project,
        farm_root=farm_root,
        status_file=status_file,
        stop_file=paths.stop_file,
        worker_name=worker_name,
        machine_name=_text(data.get("machine_name")),
        session_id=_text(data.get("session_id")),
        status=_text(data.get("status")),
        started_utc=_text(data.get("started_utc")),
        last_heartbeat_utc=last_heartbeat_utc,
        heartbeat_age_seconds=heartbeat_age,
        stale=stale,
        stop_requested=stop_requested,
        current_job_id=_text(data.get("current_job_id")),
        shot_name=_text(data.get("shot_name")),
        render_version=_text(data.get("render_version")),
        render_setting=_text(data.get("render_setting")),
        worker_git_branch=_text(data.get("worker_git_branch")),
        worker_git_commit=_text(data.get("worker_git_commit")),
        process_id=_optional_int(data.get("process_id")),
        raw_data=data,
        load_error=load_error,
    )


def list_render_workers(
    repository_root: str | Path,
    *,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
    now: datetime | None = None,
) -> list[WorkerRecord]:
    root = Path(repository_root).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Dropbox repository does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Dropbox repository is not a folder: {root}")

    records: list[WorkerRecord] = []
    for project_folder in sorted(
        (path for path in root.iterdir() if path.is_dir()),
        key=lambda path: path.name.casefold(),
    ):
        farm_root = project_folder / "renderFarm"
        workers_folder = farm_root / WORKERS_FOLDER_NAME
        if not workers_folder.is_dir():
            continue
        status_files = sorted(
            (
                path
                for path in workers_folder.iterdir()
                if path.is_file()
                and path.name.casefold().endswith(WORKER_STATUS_SUFFIX.casefold())
            ),
            key=lambda path: path.name.casefold(),
        )
        records.extend(
            read_worker_record(
                status_file,
                project=project_folder.name,
                farm_root=farm_root,
                stale_after_seconds=stale_after_seconds,
                now=now,
            )
            for status_file in status_files
        )

    return sorted(
        records,
        key=lambda record: (record.project.casefold(), record.worker_name.casefold()),
    )


class WorkerHeartbeat:
    """Publish one worker session and observe its empty STOP marker."""

    def __init__(
        self,
        farm_root: str | Path,
        worker_name: str,
        *,
        worker_git_branch: str = "",
        worker_git_commit: str = "",
        heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
    ) -> None:
        if heartbeat_interval_seconds <= 0:
            raise ValueError("Heartbeat interval must be greater than zero.")
        self.farm_root = Path(os.path.abspath(Path(farm_root).expanduser()))
        self.worker_name = safe_name(worker_name, "WORKER")
        self.paths = WorkerPaths.from_farm_root(self.farm_root, self.worker_name)
        self.worker_git_branch = worker_git_branch
        self.worker_git_commit = worker_git_commit
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.stale_after_seconds = stale_after_seconds
        self.session_id = uuid4().hex
        self.started_utc = utc_now()
        self.remote_stop_event = Event()
        self._shutdown_event = Event()
        self._state_lock = Lock()
        self._error_queue: Queue[Exception] = Queue()
        self._thread: Thread | None = None
        self._status = "starting"
        self._stop_requested = False
        self._current_job: dict[str, str] = {}
        self._remove_files_on_shutdown = False

    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self) -> None:
        if self.running:
            raise RuntimeError("Worker heartbeat is already running.")
        ensure_workers_folder(self.farm_root)

        if path_exists_with_retry(self.paths.status_file):
            existing = read_worker_record(
                self.paths.status_file,
                project=self.farm_root.parent.name,
                farm_root=self.farm_root,
                stale_after_seconds=self.stale_after_seconds,
            )
            if not existing.stale:
                raise WorkerAlreadyActiveError(
                    f"Worker name '{self.worker_name}' already has a fresh session "
                    f"heartbeat ({existing.last_seen_label})."
                )

        if path_exists_with_retry(self.paths.stop_file):
            clear_worker_stop_request(self.farm_root, self.worker_name)
            raise WorkerStopRequestedError(
                f"A pending remote STOP marker was consumed: {self.paths.stop_file}"
            )

        self._publish_status()
        self._shutdown_event.clear()
        self._remove_files_on_shutdown = False
        self._thread = Thread(
            target=self._run,
            name=f"RenderWorkerHeartbeat-{self.worker_name}",
            daemon=True,
        )
        self._thread.start()

    def update_activity(
        self,
        status: str,
        job: dict[str, Any] | None = None,
    ) -> None:
        with self._state_lock:
            self._status = status
            if job is not None:
                raw_version = _text(job.get("render_version"))
                version_digits = (
                    raw_version[1:]
                    if raw_version.lower().startswith("v")
                    else raw_version
                )
                try:
                    version = f"v{int(version_digits):03d}"
                except ValueError:
                    version = raw_version
                render_config = _text(job.get("render_config"))
                render_setting = render_config.rsplit("/", 1)[-1].split(".", 1)[0]
                self._current_job = {
                    "current_job_id": _text(job.get("job_id")),
                    "shot_name": _text(job.get("shot_name")),
                    "render_version": version,
                    "render_setting": render_setting,
                }

    def clear_current_job(self) -> None:
        with self._state_lock:
            self._current_job = {}

    def request_stop(self) -> None:
        with self._state_lock:
            self._stop_requested = True

    def poll_remote_stop(self) -> bool:
        if self.remote_stop_event.is_set():
            return True
        if not path_exists_with_retry(self.paths.stop_file):
            return False
        self.remote_stop_event.set()
        self.request_stop()
        return True

    def pop_errors(self) -> tuple[Exception, ...]:
        errors: list[Exception] = []
        while True:
            try:
                errors.append(self._error_queue.get_nowait())
            except Empty:
                break
        return tuple(errors)

    def stop(self, *, remove_files: bool = True) -> None:
        self._remove_files_on_shutdown = remove_files
        self._shutdown_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
        if thread is None or not thread.is_alive():
            self._thread = None
            if remove_files:
                self._remove_worker_files()

    def _run(self) -> None:
        try:
            while not self._shutdown_event.wait(self.heartbeat_interval_seconds):
                try:
                    self.poll_remote_stop()
                    self._publish_status()
                except Exception as error:
                    LOGGER.warning("Worker heartbeat update failed: %s", error)
                    self._error_queue.put(error)
        finally:
            if self._remove_files_on_shutdown:
                self._remove_worker_files()

    def _status_document(self) -> dict[str, Any]:
        with self._state_lock:
            status = (
                "stopping_after_current_job"
                if self._stop_requested
                else self._status
            )
            current_job = dict(self._current_job)
        return {
            "schema_version": 1,
            "worker_name": self.worker_name,
            "machine_name": socket.gethostname(),
            "project": self.farm_root.parent.name,
            "session_id": self.session_id,
            "process_id": os.getpid(),
            "status": status,
            "started_utc": self.started_utc,
            "last_heartbeat_utc": utc_now(),
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
            "worker_git_branch": self.worker_git_branch,
            "worker_git_commit": self.worker_git_commit,
            **current_job,
        }

    def _publish_status(self) -> None:
        retry_transient_windows_lock(
            operation=lambda: write_json_atomic(
                self.paths.status_file,
                self._status_document(),
            ),
            description=f"Publish worker heartbeat {self.paths.status_file}",
            transient_winerrors=WORKER_STATUS_TRANSIENT_ERRORS,
        )

    def _remove_worker_files(self) -> None:
        for path, description in (
            (self.paths.status_file, "worker status"),
            (self.paths.stop_file, "worker STOP marker"),
        ):
            try:
                retry_transient_windows_lock(
                    operation=lambda selected_path=path: selected_path.unlink(
                        missing_ok=True
                    ),
                    description=f"Remove {description} {path}",
                )
            except OSError as error:
                LOGGER.warning("Could not remove %s %s: %s", description, path, error)
