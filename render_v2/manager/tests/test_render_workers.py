from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import time
import unittest

from portable_pipe_tools.render_farm.queue import (
    create_queue_folders,
    read_json_object,
    write_json_atomic,
)
from portable_pipe_tools.render_farm.workers import (
    WorkerAlreadyActiveError,
    WorkerHeartbeat,
    WorkerStopRequestedError,
    create_worker_stop_request,
    list_render_workers,
)


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _wait_until(predicate, timeout_seconds: float = 1.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for worker heartbeat state")


class RenderWorkersTests(unittest.TestCase):
    def test_queue_initialization_creates_workers_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            paths = create_queue_folders(Path(temporary_directory) / "renderFarm")

            self.assertTrue(paths.workers.is_dir())
            self.assertEqual("Workers", paths.workers.name)

    def test_stop_request_is_an_empty_existence_only_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            farm_root = Path(temporary_directory) / "renderFarm"
            create_queue_folders(farm_root)

            stop_file = create_worker_stop_request(farm_root, "VENGEANCE")

            self.assertTrue(stop_file.is_file())
            self.assertEqual(0, stop_file.stat().st_size)
            self.assertEqual("VENGEANCE_STOP.json", stop_file.name)

            heartbeat = WorkerHeartbeat(farm_root, "VENGEANCE")
            self.assertTrue(heartbeat.poll_remote_stop())
            self.assertTrue(heartbeat.remote_stop_event.is_set())

    def test_heartbeat_publishes_activity_and_honors_stop_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            farm_root = Path(temporary_directory) / "show" / "renderFarm"
            create_queue_folders(farm_root)
            heartbeat = WorkerHeartbeat(
                farm_root,
                "BUCKET",
                worker_git_branch="main",
                worker_git_commit="a" * 40,
                heartbeat_interval_seconds=0.02,
            )

            heartbeat.start()
            try:
                heartbeat.update_activity(
                    "rendering",
                    {
                        "job_id": "job-123",
                        "shot_name": "JNG_000_0330",
                        "render_version": 11,
                        "render_config": "/Game/Render/beauty.beauty",
                    },
                )
                _wait_until(
                    lambda: read_json_object(heartbeat.paths.status_file).get(
                        "status"
                    )
                    == "rendering"
                )
                status = read_json_object(heartbeat.paths.status_file)
                self.assertEqual("JNG_000_0330", status["shot_name"])
                self.assertEqual("v011", status["render_version"])
                self.assertEqual("beauty", status["render_setting"])

                create_worker_stop_request(farm_root, "BUCKET")
                self.assertTrue(heartbeat.remote_stop_event.wait(timeout=1.0))
                _wait_until(
                    lambda: read_json_object(heartbeat.paths.status_file).get(
                        "status"
                    )
                    == "stopping_after_current_job"
                )
            finally:
                heartbeat.stop()

            self.assertFalse(heartbeat.paths.status_file.exists())
            self.assertFalse(heartbeat.paths.stop_file.exists())

    def test_pending_stop_marker_prevents_start_and_is_consumed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            farm_root = Path(temporary_directory) / "renderFarm"
            create_queue_folders(farm_root)
            stop_file = create_worker_stop_request(farm_root, "RENDER-02")
            heartbeat = WorkerHeartbeat(farm_root, "RENDER-02")

            with self.assertRaises(WorkerStopRequestedError):
                heartbeat.start()

            self.assertFalse(stop_file.exists())
            self.assertFalse(heartbeat.paths.status_file.exists())

    def test_fresh_duplicate_worker_name_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            farm_root = Path(temporary_directory) / "renderFarm"
            create_queue_folders(farm_root)
            first = WorkerHeartbeat(farm_root, "SAME-NAME")
            second = WorkerHeartbeat(farm_root, "SAME-NAME")

            first.start()
            try:
                with self.assertRaises(WorkerAlreadyActiveError):
                    second.start()
            finally:
                first.stop()

    def test_repository_scan_marks_old_heartbeats_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            paths = create_queue_folders(repository / "show" / "renderFarm")
            now = datetime.now(timezone.utc)
            for name, heartbeat_time in (
                ("FRESH", now - timedelta(seconds=5)),
                ("OLD", now - timedelta(minutes=5)),
            ):
                write_json_atomic(
                    paths.workers / f"{name}_STATUS.json",
                    {
                        "worker_name": name,
                        "session_id": f"session-{name}",
                        "status": "waiting",
                        "last_heartbeat_utc": _utc_text(heartbeat_time),
                    },
                )

            workers = list_render_workers(repository, now=now)

            self.assertEqual(["FRESH", "OLD"], [worker.worker_name for worker in workers])
            self.assertFalse(workers[0].stale)
            self.assertTrue(workers[1].stale)
            self.assertEqual("Stale", workers[1].status_label)


if __name__ == "__main__":
    unittest.main()
