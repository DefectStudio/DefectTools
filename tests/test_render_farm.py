from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.queue import (
    JOB_FILENAME,
    RESULT_FILENAME,
    claim_next_job,
    create_queue_folders,
    read_json_object,
    write_json_atomic,
)
from portable_pipe_tools.render_farm.test_job import create_test_job
from portable_pipe_tools.render_farm.worker import run_once


class RenderFarmPrototypeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.farm_root = Path(self.temporary_directory.name) / "RenderFarm"
        self.paths = create_queue_folders(self.farm_root)

    def test_create_test_job_publishes_complete_folder(self) -> None:
        queued_folder = create_test_job(self.farm_root)

        self.assertEqual([], list(self.paths.submitting.iterdir()))
        self.assertTrue(queued_folder.is_dir())
        job = read_json_object(queued_folder / JOB_FILENAME)
        self.assertEqual("queued", job["status"])
        self.assertEqual(1001, job["frame_start"])
        self.assertEqual(1100, job["frame_end"])

    def test_claim_prefers_higher_priority_then_older_submission(self) -> None:
        self._queue_job("low", priority=10, submitted_utc="2026-08-03T01:00:00.000Z")
        self._queue_job("high-new", priority=90, submitted_utc="2026-08-03T03:00:00.000Z")
        self._queue_job("high-old", priority=90, submitted_utc="2026-08-03T02:00:00.000Z")

        claimed = claim_next_job(self.paths, "RENDER-03")

        self.assertIsNotNone(claimed)
        assert claimed is not None
        self.assertEqual("high-old__RENDER-03", claimed.name)
        self.assertFalse((self.paths.needs_rendering / "high-old").exists())

    def test_second_worker_cannot_claim_already_claimed_job(self) -> None:
        create_test_job(self.farm_root)

        first_claim = claim_next_job(self.paths, "RENDER-02")
        second_claim = claim_next_job(self.paths, "RENDER-03")

        self.assertIsNotNone(first_claim)
        self.assertIsNone(second_claim)

    def test_successful_simulation_updates_and_moves_job(self) -> None:
        create_test_job(self.farm_root)

        result = run_once(self.farm_root, "RENDER-03", simulate_success=True)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("complete", result.status)
        self.assertEqual(self.paths.render_complete, result.final_folder.parent)
        job = read_json_object(result.final_folder / JOB_FILENAME)
        result_json = read_json_object(result.final_folder / RESULT_FILENAME)
        self.assertEqual("complete", job["status"])
        self.assertEqual("RENDER-03", job["worker"])
        self.assertEqual(1, job["attempt"])
        self.assertEqual("complete", result_json["status"])
        self.assertEqual([], list(self.paths.is_rendering.iterdir()))

    def test_failed_simulation_updates_and_moves_job(self) -> None:
        create_test_job(self.farm_root)

        result = run_once(self.farm_root, "RENDER-04", simulate_success=False)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("failed", result.status)
        self.assertEqual(self.paths.render_failed, result.final_folder.parent)
        result_json = read_json_object(result.final_folder / RESULT_FILENAME)
        self.assertEqual(1, result_json["exit_code"])
        self.assertEqual("Simulated render failure", result_json["reason"])

    def test_invalid_json_is_claimed_and_moved_to_failed(self) -> None:
        broken_folder = self.paths.needs_rendering / "broken-job"
        broken_folder.mkdir()
        (broken_folder / JOB_FILENAME).write_text("{broken", encoding="utf-8")

        result = run_once(self.farm_root, "RENDER-05", simulate_success=True)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("failed", result.status)
        self.assertTrue((result.final_folder / JOB_FILENAME).exists())
        failure = read_json_object(result.final_folder / RESULT_FILENAME)
        self.assertIn("invalid or unreadable", failure["reason"])

    def _queue_job(self, folder_name: str, priority: int, submitted_utc: str) -> None:
        folder = self.paths.needs_rendering / folder_name
        folder.mkdir()
        write_json_atomic(
            folder / JOB_FILENAME,
            {
                "schema_version": 1,
                "job_id": folder_name,
                "status": "queued",
                "priority": priority,
                "submitted_utc": submitted_utc,
                "attempt": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
