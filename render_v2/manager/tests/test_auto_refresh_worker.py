from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
import tempfile
import unittest

from portable_pipe_tools.render_farm.auto_refresh_worker import (
    AutoRefreshResult,
    AutoRefreshWorker,
)
from portable_pipe_tools.render_farm.queue import (
    create_queue_folders,
    utc_now,
    write_json_atomic,
)


class AutoRefreshWorkerTests(unittest.TestCase):
    def test_worker_scans_repository_after_interval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            paths = create_queue_folders(repository / "show" / "renderFarm")
            job_folder = paths.needs_rendering / "job-1"
            job_folder.mkdir()
            write_json_atomic(job_folder / "job.json", {"job_id": "job-1"})
            write_json_atomic(
                paths.workers / "WORKER-01_STATUS.json",
                {
                    "worker_name": "WORKER-01",
                    "session_id": "session-1",
                    "status": "waiting",
                    "last_heartbeat_utc": utc_now(),
                },
            )
            results: Queue[AutoRefreshResult] = Queue()
            worker = AutoRefreshWorker(
                repository_path_provider=lambda: repository,
                result_queue=results,
                interval_seconds=0.01,
            )

            try:
                worker.start()
                result = results.get(timeout=1.0)
            finally:
                worker.stop()

            self.assertEqual(repository, result.repository_path)
            self.assertIsNone(result.error)
            self.assertEqual(1, len(result.jobs))
            self.assertEqual(1, len(result.workers))
            self.assertEqual("WORKER-01", result.workers[0].worker_name)
            self.assertFalse(worker.running)

    def test_worker_does_not_emit_without_a_connected_repository(self) -> None:
        results: Queue[AutoRefreshResult] = Queue()
        worker = AutoRefreshWorker(
            repository_path_provider=lambda: None,
            result_queue=results,
            interval_seconds=0.01,
        )

        try:
            worker.start()
            with self.assertRaises(Empty):
                results.get(timeout=0.05)
        finally:
            worker.stop()

    def test_interval_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            AutoRefreshWorker(
                repository_path_provider=lambda: None,
                result_queue=Queue(),
                interval_seconds=0,
            )

    def test_interval_can_be_changed(self) -> None:
        worker = AutoRefreshWorker(
            repository_path_provider=lambda: None,
            result_queue=Queue(),
        )

        worker.set_interval_seconds(300)

        self.assertEqual(300, worker.interval_seconds)
        with self.assertRaises(ValueError):
            worker.set_interval_seconds(0)


if __name__ == "__main__":
    unittest.main()
