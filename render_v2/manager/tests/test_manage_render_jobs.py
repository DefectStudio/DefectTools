from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from portable_pipe_tools.render_farm.get_all_render_jobs import get_all_render_jobs
from portable_pipe_tools.render_farm.manage_render_jobs import (
    clear_render_job_blacklist,
    resubmit_failed_render_job,
)
from portable_pipe_tools.render_farm.queue import (
    create_queue_folders,
    read_json_object,
    write_json_atomic,
)


class ManageRenderJobsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary_directory.name)
        self.paths = create_queue_folders(
            self.repository / "show" / "renderFarm"
        )
        self.source_folder = self.paths.render_failed / "failed-package__WORKER-01"
        self.source_folder.mkdir()
        self.source_data = {
            "schema_version": 1,
            "job_id": "SHOT_010_v007_OLD",
            "batch_id": "old-batch",
            "project": "show",
            "shot_name": "SHOT_010",
            "render_version": 7,
            "priority": 50,
            "submitted_utc": "2026-08-15T07:10:07.051Z",
            "submitted_by": "SUBMITTER",
            "submitted_user": "artist",
            "status": "complete",
            "attempt": 3,
            "blacklisted_workers": ["WORKER-01", "WORKER-02"],
            "worker": "WORKER-02",
            "claimed_utc": "2026-08-15T08:00:00.000Z",
            "render_started_utc": "2026-08-15T08:00:01.000Z",
            "render_finished_utc": "2026-08-15T08:05:00.000Z",
            "result": {"status": "failed"},
            "last_failure": {"reason": "test failure"},
            "outputs": {"mp4": True, "exr": True, "hero": True},
            "submitted_output_directory": "X:/show/output",
            "output_directory": "Y:/worker/output",
            "worker_output_directory": "Y:/worker/output",
            "worker_uproject": "Y:/project/show.uproject",
            "git_sync_status": "success",
            "rendered_git_commit": "abc123",
        }
        write_json_atomic(self.source_folder / "job.json", self.source_data)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _failed_job(self):
        jobs = get_all_render_jobs(self.repository)
        self.assertEqual(1, len(jobs))
        return jobs[0]

    def test_clear_blacklist_updates_the_live_job_json(self) -> None:
        job = self._failed_job()

        self.assertTrue(clear_render_job_blacklist(job))
        self.assertEqual(
            [],
            read_json_object(job.job_json_path)["blacklisted_workers"],
        )
        self.assertFalse(clear_render_job_blacklist(job))

    def test_resubmit_replaces_failed_package_with_fresh_queued_package(self) -> None:
        job = self._failed_job()

        destination = resubmit_failed_render_job(job)
        new_data = read_json_object(destination / "job.json")

        self.assertFalse(self.source_folder.exists())
        self.assertEqual(self.paths.needs_rendering, destination.parent)
        self.assertNotEqual(self.source_data["job_id"], new_data["job_id"])
        self.assertEqual("queued", new_data["status"])
        self.assertEqual(0, new_data["attempt"])
        self.assertEqual([], new_data["blacklisted_workers"])
        self.assertIsNone(new_data["worker"])
        self.assertIsNone(new_data["result"])
        self.assertIsNone(new_data["last_failure"])
        self.assertEqual(
            self.source_data["job_id"],
            new_data["resubmitted_from_job_id"],
        )
        self.assertEqual("X:/show/output", new_data["output_directory"])
        self.assertNotIn("worker_output_directory", new_data)
        self.assertNotIn("worker_uproject", new_data)
        self.assertNotIn("git_sync_status", new_data)
        self.assertNotIn("rendered_git_commit", new_data)
        self.assertEqual(["job.json"], [path.name for path in destination.iterdir()])


if __name__ == "__main__":
    unittest.main()
