from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.get_all_render_jobs import get_all_render_jobs
from portable_pipe_tools.render_farm.cloud_dispatch import DispatcherError
from portable_pipe_tools.render_farm.manage_render_jobs import (
    DISPATCHER_SUBMISSION_RECEIPT_FILENAME,
    clear_render_job_blacklist,
    resubmit_failed_render_job,
)
from portable_pipe_tools.render_farm.queue import (
    CLOUD_DISPATCHER_COORDINATION,
    DISPATCHER_COORDINATION_FIELD,
    create_queue_folders,
    read_json_object,
    write_json_atomic,
)


class FakeManagerDispatcher:
    def __init__(self) -> None:
        self.cleared: list[str] = []
        self.submitted: list[dict] = []

    def clear_blacklist(self, job_id: str) -> dict:
        self.cleared.append(job_id)
        return {"ok": True, "cleared": 2}

    def submit_job(self, job: dict) -> dict:
        self.submitted.append(dict(job))
        return {"ok": True, "created": True, "idempotent_replay": False}


class LegacyAwareDispatcher(FakeManagerDispatcher):
    def clear_blacklist(self, job_id: str) -> dict:
        raise DispatcherError(
            f"{job_id} is a legacy filesystem job",
            status=404,
            code="job_not_found",
        )


class CloudManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.repository = Path(self.temporary_directory.name)
        self.paths = create_queue_folders(self.repository / "show" / "renderFarm")
        self.source_folder = self.paths.render_failed / "failed__WORKER-A"
        self.source_folder.mkdir()
        write_json_atomic(
            self.source_folder / "job.json",
            {
                "schema_version": 1,
                "job_id": "SHOT_010_v001_original",
                "batch_id": "batch",
                "project": "show",
                "job_type": "unreal_movie_render_graph",
                "shot_name": "SHOT_010",
                "render_version": 1,
                "priority": 50,
                "submitted_utc": "2026-08-16T00:00:00Z",
                "status": "failed",
                "attempt": 2,
                "blacklisted_workers": ["WORKER-A", "WORKER-B"],
                "submitted_output_directory": "X:/show/output",
            },
        )

    def _job(self):
        jobs = get_all_render_jobs(self.repository)
        self.assertEqual(1, len(jobs))
        return jobs[0]

    def test_clear_blacklist_updates_d1_and_dropbox(self) -> None:
        dispatcher = FakeManagerDispatcher()
        job = self._job()

        changed = clear_render_job_blacklist(job, dispatcher)

        self.assertTrue(changed)
        self.assertEqual([job.job_id], dispatcher.cleared)
        self.assertEqual([], read_json_object(job.job_json_path)["blacklisted_workers"])

    def test_resubmit_registers_new_package_with_d1(self) -> None:
        dispatcher = FakeManagerDispatcher()

        destination = resubmit_failed_render_job(self._job(), dispatcher)
        data = read_json_object(destination / "job.json")

        self.assertEqual(
            CLOUD_DISPATCHER_COORDINATION,
            data[DISPATCHER_COORDINATION_FIELD],
        )
        self.assertEqual(data["job_id"], dispatcher.submitted[0]["job_id"])
        receipt = read_json_object(
            destination / DISPATCHER_SUBMISSION_RECEIPT_FILENAME
        )
        self.assertEqual(data["job_id"], receipt["job_id"])
        self.assertTrue(receipt["created"])

    def test_legacy_job_blacklist_still_clears_when_d1_has_no_row(self) -> None:
        job = self._job()

        changed = clear_render_job_blacklist(job, LegacyAwareDispatcher())

        self.assertTrue(changed)
        self.assertEqual([], read_json_object(job.job_json_path)["blacklisted_workers"])


if __name__ == "__main__":
    unittest.main()
