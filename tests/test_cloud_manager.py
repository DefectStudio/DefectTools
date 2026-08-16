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
        self.replacements: list[tuple[str, dict]] = []

    def clear_blacklist(self, job_id: str) -> dict:
        self.cleared.append(job_id)
        return {"ok": True, "cleared": 2}

    def replace_job(self, source_job_id: str, replacement_job: dict) -> dict:
        self.replacements.append((source_job_id, dict(replacement_job)))
        return {
            "ok": True,
            "created": True,
            "idempotent_replay": False,
            "source_deleted": True,
        }


class FailingReplaceDispatcher(FakeManagerDispatcher):
    def replace_job(self, source_job_id: str, replacement_job: dict) -> dict:
        raise DispatcherError(
            f"Could not replace {source_job_id}",
            status=503,
            code="dispatcher_unavailable",
        )


class UnconfirmedReplaceDispatcher(FakeManagerDispatcher):
    def replace_job(self, source_job_id: str, replacement_job: dict) -> dict:
        return {
            "ok": True,
            "created": True,
            "idempotent_replay": False,
            "source_deleted": False,
        }


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

    def test_resubmit_replaces_d1_job_and_deletes_old_dropbox_package(self) -> None:
        dispatcher = FakeManagerDispatcher()
        source_job_id = self._job().job_id

        destination = resubmit_failed_render_job(self._job(), dispatcher)
        data = read_json_object(destination / "job.json")

        self.assertEqual(
            CLOUD_DISPATCHER_COORDINATION,
            data[DISPATCHER_COORDINATION_FIELD],
        )
        self.assertEqual(source_job_id, dispatcher.replacements[0][0])
        self.assertEqual(data["job_id"], dispatcher.replacements[0][1]["job_id"])
        self.assertFalse(self.source_folder.exists())
        receipt = read_json_object(
            destination / DISPATCHER_SUBMISSION_RECEIPT_FILENAME
        )
        self.assertEqual(data["job_id"], receipt["job_id"])
        self.assertEqual(source_job_id, receipt["replaced_job_id"])
        self.assertTrue(receipt["created"])
        self.assertTrue(receipt["source_deleted"])

    def test_resubmit_failure_preserves_old_failed_package(self) -> None:
        with self.assertRaises(DispatcherError):
            resubmit_failed_render_job(self._job(), FailingReplaceDispatcher())

        self.assertTrue(self.source_folder.is_dir())
        self.assertEqual(1, len(list(self.paths.needs_rendering.iterdir())))

    def test_unconfirmed_cloud_delete_preserves_old_failed_package(self) -> None:
        with self.assertRaises(DispatcherError) as caught:
            resubmit_failed_render_job(
                self._job(),
                UnconfirmedReplaceDispatcher(),
            )

        self.assertEqual("replacement_not_confirmed", caught.exception.code)
        self.assertTrue(self.source_folder.is_dir())
        self.assertEqual(1, len(list(self.paths.needs_rendering.iterdir())))

    def test_legacy_job_blacklist_still_clears_when_d1_has_no_row(self) -> None:
        job = self._job()

        changed = clear_render_job_blacklist(job, LegacyAwareDispatcher())

        self.assertTrue(changed)
        self.assertEqual([], read_json_object(job.job_json_path)["blacklisted_workers"])


if __name__ == "__main__":
    unittest.main()
