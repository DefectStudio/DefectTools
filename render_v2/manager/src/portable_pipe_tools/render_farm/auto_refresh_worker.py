from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from threading import Event, Lock, Thread, current_thread

from portable_pipe_tools.render_farm.get_all_render_jobs import (
    get_all_render_jobs,
)
from portable_pipe_tools.render_farm.render_job import RenderJob
from portable_pipe_tools.render_farm.workers import (
    WorkerRecord,
    list_render_workers,
)


AUTO_REFRESH_INTERVAL_SECONDS = 60.0
SnapshotLoader = Callable[
    [Path],
    tuple[list[RenderJob], list[WorkerRecord]],
]


@dataclass(frozen=True)
class AutoRefreshResult:
    repository_path: Path
    jobs: tuple[RenderJob, ...] = ()
    workers: tuple[WorkerRecord, ...] = ()
    error: Exception | None = None


class AutoRefreshWorker:
    """Periodically scan the current repository without blocking Tk's thread."""

    def __init__(
        self,
        repository_path_provider: Callable[[], Path | None],
        result_queue: Queue[AutoRefreshResult],
        interval_seconds: float = AUTO_REFRESH_INTERVAL_SECONDS,
        snapshot_loader: SnapshotLoader | None = None,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("Auto-refresh interval must be greater than zero")
        self.repository_path_provider = repository_path_provider
        self.result_queue = result_queue
        self.interval_seconds = interval_seconds
        self.snapshot_loader = snapshot_loader
        self._stop_event = Event()
        self._state_lock = Lock()
        self._thread: Thread | None = None

    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self) -> None:
        with self._state_lock:
            if self.running:
                return
            self._stop_event = Event()
            self._thread = Thread(
                target=self._run,
                name="FarmRenderManagerAutoRefresh",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._state_lock:
            thread = self._thread
            self._stop_event.set()
        if thread is not None and thread is not current_thread():
            thread.join(timeout=1.0)
        with self._state_lock:
            if self._thread is thread:
                self._thread = None

    def set_interval_seconds(self, interval_seconds: float) -> None:
        if interval_seconds <= 0:
            raise ValueError("Auto-refresh interval must be greater than zero")
        with self._state_lock:
            self.interval_seconds = interval_seconds

    def _run(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            repository_path = self.repository_path_provider()
            if repository_path is None:
                continue
            try:
                if self.snapshot_loader is None:
                    loaded_jobs = get_all_render_jobs(repository_path)
                    loaded_workers = list_render_workers(repository_path)
                else:
                    loaded_jobs, loaded_workers = self.snapshot_loader(repository_path)
                jobs = tuple(loaded_jobs)
                workers = tuple(loaded_workers)
            except Exception as error:
                result = AutoRefreshResult(
                    repository_path=repository_path,
                    error=error,
                )
            else:
                result = AutoRefreshResult(
                    repository_path=repository_path,
                    jobs=jobs,
                    workers=workers,
                )
            self.result_queue.put(result)
