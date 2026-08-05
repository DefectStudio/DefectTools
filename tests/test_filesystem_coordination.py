from __future__ import annotations

from pathlib import Path
from threading import Barrier, Lock, Thread
import tempfile
import unittest
from uuid import uuid4

from portable_pipe_tools.render_farm.filesystem_coordination import (
    FilesystemClaimAmbiguousError,
    FilesystemJobCoordinator,
)
from portable_pipe_tools.render_farm.queue import (
    JOB_FILENAME,
    read_json_object,
    write_json_atomic,
)
from portable_pipe_tools.render_farm.test_job import create_test_job
from portable_pipe_tools.render_farm.worker import run_once


class FilesystemCoordinationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.farm_root = Path(self.temporary_directory.name) / "renderFarm"
        self.queued_folder = create_test_job(self.farm_root)
        self.job = read_json_object(self.queued_folder / JOB_FILENAME)

    def coordinator(self, session_id: str) -> FilesystemJobCoordinator:
        return FilesystemJobCoordinator(
            self.farm_root,
            session_id=session_id,
            initial_jitter_seconds=0,
            claim_settle_seconds=0,
            election_verify_seconds=0,
            post_claim_verify_seconds=0,
        )

    def test_simultaneous_claim_intents_have_one_deterministic_winner(self) -> None:
        barrier = Barrier(2)
        result_lock = Lock()
        results = []
        errors = []

        def contender(worker_name: str) -> None:
            coordinator = FilesystemJobCoordinator(
                self.farm_root,
                session_id=f"session-{worker_name}",
                initial_jitter_seconds=0,
                claim_settle_seconds=1,
                election_verify_seconds=0,
                post_claim_verify_seconds=0,
                sleep=lambda _seconds: barrier.wait(timeout=2),
            )
            try:
                result = coordinator.try_claim(
                    self.queued_folder,
                    self.job,
                    worker_name,
                )
                with result_lock:
                    results.append((coordinator, result))
            except Exception as error:
                with result_lock:
                    errors.append(error)

        threads = [
            Thread(target=contender, args=(worker,))
            for worker in ("RENDER-A", "RENDER-B")
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3)

        winners = [(coordinator, claim) for coordinator, claim in results if claim]
        self.assertEqual([], errors)
        self.assertEqual(2, len(results))
        self.assertEqual(1, len(winners))
        winners[0][0].verify_claim(winners[0][1])

    def test_late_contender_cannot_replace_an_active_seal(self) -> None:
        winner = self.coordinator("session-a")
        late_worker = self.coordinator("session-b")
        first_claim = winner.try_claim(self.queued_folder, self.job, "RENDER-A")
        assert first_claim is not None
        marker_count_before = len(
            list((first_claim.coordination_folder / "Claims").glob("*.json"))
        )

        late_claim = late_worker.try_claim(
            self.queued_folder,
            self.job,
            "RENDER-B",
        )

        self.assertIsNone(late_claim)
        marker_count_after = len(
            list((first_claim.coordination_folder / "Claims").glob("*.json"))
        )
        self.assertEqual(marker_count_before, marker_count_after)
        winner.verify_claim(first_claim)

    def test_changed_package_is_released_and_fails_closed(self) -> None:
        changed = False

        def change_during_settle(_seconds: float) -> None:
            nonlocal changed
            if changed:
                return
            changed = True
            updated_job = read_json_object(self.queued_folder / JOB_FILENAME)
            updated_job["priority"] += 1
            write_json_atomic(self.queued_folder / JOB_FILENAME, updated_job)

        coordinator = FilesystemJobCoordinator(
            self.farm_root,
            session_id="session-a",
            initial_jitter_seconds=0,
            claim_settle_seconds=1,
            election_verify_seconds=0,
            post_claim_verify_seconds=0,
            sleep=change_during_settle,
        )

        with self.assertRaises(FilesystemClaimAmbiguousError):
            coordinator.try_claim(self.queued_folder, self.job, "RENDER-A")

        release_files = list(
            (coordinator.root / self.job["job_id"] / "attempt-000000" / "Releases")
            .glob("*.json")
        )
        self.assertEqual(1, len(release_files))

    def test_new_attempt_is_not_blocked_by_previous_attempt_seal(self) -> None:
        first = self.coordinator("session-a")
        second = self.coordinator("session-b")
        first_claim = first.try_claim(self.queued_folder, self.job, "RENDER-A")
        assert first_claim is not None

        retry_job = dict(self.job)
        retry_job["attempt"] = 1
        retry_job["blacklisted_workers"] = ["RENDER-A"]
        write_json_atomic(self.queued_folder / JOB_FILENAME, retry_job)
        second_claim = second.try_claim(
            self.queued_folder,
            retry_job,
            "RENDER-B",
        )

        self.assertIsNotNone(second_claim)
        self.assertEqual(1, second_claim.attempt)

    def test_released_winner_allows_a_new_worker_to_claim_same_attempt(self) -> None:
        first = self.coordinator("session-a")
        second = self.coordinator("session-b")
        first_claim = first.try_claim(self.queued_folder, self.job, "RENDER-A")
        assert first_claim is not None
        first.release_claim(first_claim, "Git preflight failed")

        second_claim = second.try_claim(
            self.queued_folder,
            self.job,
            "RENDER-B",
        )

        self.assertIsNotNone(second_claim)
        second.verify_claim(second_claim)

    def test_multiple_active_seals_are_ambiguous(self) -> None:
        coordinator = self.coordinator("session-a")
        claim = coordinator.try_claim(self.queued_folder, self.job, "RENDER-A")
        assert claim is not None
        competing_token = uuid4().hex
        competing_record = {
            "schema_version": 1,
            "job_id": claim.job_id,
            "attempt": claim.attempt,
            "worker_name": "RENDER-B",
            "session_id": "session-b",
            "claim_token": competing_token,
            "package_fingerprint": claim.package_fingerprint,
        }
        write_json_atomic(
            claim.coordination_folder / "Claims" / f"{competing_token}.json",
            competing_record,
        )
        write_json_atomic(
            claim.coordination_folder / "Seals" / f"{competing_token}.json",
            competing_record,
        )

        with self.assertRaises(FilesystemClaimAmbiguousError):
            coordinator.verify_claim(claim)

    def test_run_once_records_filesystem_fencing_identity(self) -> None:
        result = run_once(
            self.farm_root,
            "RENDER-A",
            simulate_success=True,
            minimum_stage_seconds=0,
            filesystem_coordination_delays=(0, 0, 0, 0),
        )
        assert result is not None
        completed_job = read_json_object(result.final_folder / JOB_FILENAME)

        self.assertEqual("complete", result.status)
        self.assertTrue(completed_job["filesystem_claim_token"])
        self.assertTrue(completed_job["filesystem_owner_session"])
        self.assertEqual(0, completed_job["filesystem_coordination_generation"])

    def test_default_worker_claim_uses_slow_stabilization_intervals(self) -> None:
        sleep_calls = []

        result = run_once(
            self.farm_root,
            "RENDER-A",
            simulate_success=True,
            minimum_stage_seconds=0,
            sleep=sleep_calls.append,
        )

        self.assertIsNotNone(result)
        self.assertEqual([30.0, 10.0, 15.0], sleep_calls[-3:])
        self.assertGreaterEqual(sleep_calls[0], 0.0)
        self.assertLessEqual(sleep_calls[0], 5.0)

    def test_ambiguous_job_is_skipped_without_starving_lower_priority_job(self) -> None:
        high_job = dict(self.job)
        high_job["priority"] = 100
        write_json_atomic(self.queued_folder / JOB_FILENAME, high_job)
        lower_folder = self.queued_folder.parent / "lower-priority-job"
        lower_folder.mkdir()
        lower_job = dict(self.job)
        lower_job.update(
            {
                "job_id": "lower-priority-job",
                "priority": 1,
                "submitted_utc": "2026-08-05T12:00:00.000Z",
            }
        )
        write_json_atomic(lower_folder / JOB_FILENAME, lower_job)

        ambiguous_folder = self.queued_folder

        class SelectiveCoordinator(FilesystemJobCoordinator):
            def try_claim(self, queued_folder, job, worker_name):
                if queued_folder == ambiguous_folder:
                    raise FilesystemClaimAmbiguousError("competing seals")
                return super().try_claim(queued_folder, job, worker_name)

        coordinator = SelectiveCoordinator(
            self.farm_root,
            initial_jitter_seconds=0,
            claim_settle_seconds=0,
            election_verify_seconds=0,
            post_claim_verify_seconds=0,
        )

        result = run_once(
            self.farm_root,
            "RENDER-A",
            simulate_success=True,
            minimum_stage_seconds=0,
            filesystem_coordinator=coordinator,
        )

        self.assertIsNotNone(result)
        self.assertIn("lower-priority-job", result.final_folder.name)
        self.assertTrue(self.queued_folder.is_dir())


if __name__ == "__main__":
    unittest.main()
