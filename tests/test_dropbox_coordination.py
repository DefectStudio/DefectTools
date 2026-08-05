from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from threading import Barrier, Lock, Thread
import tempfile
import unittest

from portable_pipe_tools.render_farm.dropbox_api import (
    DropboxConflictError,
    DropboxFileSnapshot,
    DropboxNotFoundError,
)
from portable_pipe_tools.render_farm.dropbox_coordination import (
    DropboxClaimLostError,
    DropboxJobCoordinator,
)
from portable_pipe_tools.render_farm.queue import (
    JOB_FILENAME,
    create_queue_folders,
    read_json_object,
)
from portable_pipe_tools.render_farm.test_job import create_test_job
from portable_pipe_tools.render_farm.worker import run_once


class InMemoryDropboxStore:
    def __init__(self) -> None:
        self._files: dict[str, tuple[int, dict]] = {}
        self._lock = Lock()
        self.claim_barrier: Barrier | None = None

    def ensure_folder(self, api_path: str) -> None:
        del api_path

    def download_json(self, api_path: str) -> DropboxFileSnapshot:
        with self._lock:
            if api_path not in self._files:
                raise DropboxNotFoundError(api_path)
            revision, data = self._files[api_path]
            return DropboxFileSnapshot(api_path, f"rev-{revision}", deepcopy(data))

    def create_json(self, api_path: str, data: dict) -> DropboxFileSnapshot:
        with self._lock:
            if api_path in self._files:
                raise DropboxConflictError(api_path)
            self._files[api_path] = (1, deepcopy(data))
            return DropboxFileSnapshot(api_path, "rev-1", deepcopy(data))

    def update_json(
        self,
        api_path: str,
        expected_revision: str,
        data: dict,
    ) -> DropboxFileSnapshot:
        barrier = self.claim_barrier if data.get("state") == "claimed" else None
        if barrier is not None:
            barrier.wait(timeout=2.0)
        with self._lock:
            if api_path not in self._files:
                raise DropboxNotFoundError(api_path)
            revision, _current = self._files[api_path]
            if expected_revision != f"rev-{revision}":
                raise DropboxConflictError(api_path)
            next_revision = revision + 1
            self._files[api_path] = (next_revision, deepcopy(data))
            return DropboxFileSnapshot(
                api_path,
                f"rev-{next_revision}",
                deepcopy(data),
            )


class DropboxCoordinationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryDropboxStore()
        self.job = {
            "job_id": "job-123",
            "blacklisted_workers": [],
        }

    def test_simultaneous_workers_have_exactly_one_revision_winner(self) -> None:
        initializer = DropboxJobCoordinator(
            self.store,
            "/show/renderFarm",
            session_id="initializer",
            local_settle_seconds=0,
        )
        initializer._ensure_document("job-123", self.job)
        self.store.claim_barrier = Barrier(2)
        coordinators = (
            DropboxJobCoordinator(
                self.store,
                "/show/renderFarm",
                session_id="session-a",
                local_settle_seconds=0,
            ),
            DropboxJobCoordinator(
                self.store,
                "/show/renderFarm",
                session_id="session-b",
                local_settle_seconds=0,
            ),
        )
        results: list = []

        threads = [
            Thread(
                target=lambda selected=coordinator: results.append(
                    selected.try_claim(self.job, selected.session_id)
                )
            )
            for coordinator in coordinators
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3.0)

        winners = [result for result in results if result is not None]
        self.assertEqual(2, len(results))
        self.assertEqual(1, len(winners))

    def test_failed_worker_is_blacklisted_and_another_worker_can_claim(self) -> None:
        worker_a = DropboxJobCoordinator(
            self.store,
            "/show/renderFarm",
            session_id="session-a",
            local_settle_seconds=0,
        )
        worker_b = DropboxJobCoordinator(
            self.store,
            "/show/renderFarm",
            session_id="session-b",
            local_settle_seconds=0,
        )
        claim_a = worker_a.try_claim(self.job, "RENDER-A")
        assert claim_a is not None
        claim_a = worker_a.mark_rendering(claim_a)
        worker_a.requeue_failed_claim(claim_a, "Render failed")

        synchronized_job = {
            **self.job,
            "attempt": 1,
            "blacklisted_workers": ["RENDER-A"],
        }
        retry_a = worker_a.try_claim(synchronized_job, "render-a")
        claim_b = worker_b.try_claim(synchronized_job, "RENDER-B")

        self.assertIsNone(retry_a)
        self.assertIsNotNone(claim_b)

    def test_stale_local_attempt_is_not_claimed_after_remote_requeue(self) -> None:
        worker_a = DropboxJobCoordinator(
            self.store,
            "/show/renderFarm",
            session_id="session-a",
            local_settle_seconds=0,
        )
        worker_b = DropboxJobCoordinator(
            self.store,
            "/show/renderFarm",
            session_id="session-b",
            local_settle_seconds=0,
        )
        claim_a = worker_a.try_claim(self.job, "RENDER-A")
        assert claim_a is not None
        claim_a = worker_a.mark_rendering(claim_a)
        worker_a.requeue_failed_claim(claim_a, "Render failed")

        stale_claim = worker_b.try_claim(self.job, "RENDER-B")
        synchronized_claim = worker_b.try_claim(
            {
                **self.job,
                "attempt": 1,
                "blacklisted_workers": ["RENDER-A"],
            },
            "RENDER-B",
        )

        self.assertIsNone(stale_claim)
        self.assertIsNotNone(synchronized_claim)

    def test_old_generation_cannot_complete_after_ownership_changes(self) -> None:
        coordinator = DropboxJobCoordinator(
            self.store,
            "/show/renderFarm",
            session_id="session-a",
            local_settle_seconds=0,
        )
        claim = coordinator.try_claim(self.job, "RENDER-A")
        assert claim is not None
        claim = coordinator.mark_rendering(claim)
        snapshot = self.store.download_json(claim.coordination_path)
        changed = dict(snapshot.data)
        changed.update(
            {
                "generation": claim.generation + 1,
                "owner_worker": "RENDER-B",
                "owner_session": "session-b",
                "claim_token": "new-token",
            }
        )
        self.store.update_json(snapshot.path, snapshot.revision, changed)

        with self.assertRaises(DropboxClaimLostError):
            coordinator.mark_complete(claim)

    def test_run_once_uses_api_blacklist_and_requeue_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            farm_root = Path(temporary_directory) / "renderFarm"
            queued_folder = create_test_job(farm_root)
            worker_a = DropboxJobCoordinator(
                self.store,
                "/show/renderFarm",
                session_id="session-a",
                local_settle_seconds=0,
            )
            worker_b = DropboxJobCoordinator(
                self.store,
                "/show/renderFarm",
                session_id="session-b",
                local_settle_seconds=0,
            )

            failed = run_once(
                farm_root,
                "RENDER-A",
                simulate_success=False,
                minimum_stage_seconds=0.0,
                use_dropbox_api_sync=True,
                dropbox_coordinator=worker_a,
            )
            same_worker = run_once(
                farm_root,
                "RENDER-A",
                simulate_success=True,
                minimum_stage_seconds=0.0,
                use_dropbox_api_sync=True,
                dropbox_coordinator=worker_a,
            )
            completed = run_once(
                farm_root,
                "RENDER-B",
                simulate_success=True,
                minimum_stage_seconds=0.0,
                use_dropbox_api_sync=True,
                dropbox_coordinator=worker_b,
            )

            self.assertIsNotNone(failed)
            self.assertEqual("requeued", failed.status)
            self.assertIsNone(same_worker)
            self.assertIsNotNone(completed)
            self.assertEqual("complete", completed.status)
            completed_job = read_json_object(completed.final_folder / JOB_FILENAME)
            self.assertEqual(["RENDER-A"], completed_job["blacklisted_workers"])
            self.assertFalse(queued_folder.exists())

    def test_default_mode_does_not_touch_injected_api_coordinator(self) -> None:
        class ExplodingCoordinator:
            def try_claim(self, job, worker_name):
                del job, worker_name
                raise AssertionError("API coordinator should not be used")

        with tempfile.TemporaryDirectory() as temporary_directory:
            farm_root = Path(temporary_directory) / "renderFarm"
            create_test_job(farm_root)

            result = run_once(
                farm_root,
                "RENDER-A",
                simulate_success=True,
                minimum_stage_seconds=0.0,
                use_dropbox_api_sync=False,
                dropbox_coordinator=ExplodingCoordinator(),  # type: ignore[arg-type]
                filesystem_coordination_delays=(0.0, 0.0, 0.0, 0.0),
            )

        self.assertIsNotNone(result)
        self.assertEqual("complete", result.status)

    def test_multiple_jobs_missing_ids_get_distinct_coordination_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            farm_root = Path(temporary_directory) / "renderFarm"
            paths = create_queue_folders(farm_root)
            for folder_name in ("broken-a", "broken-b"):
                queued_folder = paths.needs_rendering / folder_name
                queued_folder.mkdir()
                (queued_folder / JOB_FILENAME).write_text("{}", encoding="utf-8")

            coordinator = DropboxJobCoordinator(
                self.store,
                "/show/renderFarm",
                session_id="session-a",
                local_settle_seconds=0,
            )
            first = run_once(
                farm_root,
                "RENDER-A",
                simulate_success=True,
                minimum_stage_seconds=0.0,
                use_dropbox_api_sync=True,
                dropbox_coordinator=coordinator,
            )
            second = run_once(
                farm_root,
                "RENDER-A",
                simulate_success=True,
                minimum_stage_seconds=0.0,
                use_dropbox_api_sync=True,
                dropbox_coordinator=coordinator,
            )

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual("failed", first.status)
        self.assertEqual("failed", second.status)
        self.assertNotEqual(first.final_folder.name, second.final_folder.name)


if __name__ == "__main__":
    unittest.main()
