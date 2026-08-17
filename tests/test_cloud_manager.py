from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.get_all_render_jobs import get_all_render_jobs
from portable_pipe_tools.render_farm.cloud_dispatch import DispatcherError
from portable_pipe_tools.render_farm.manage_render_jobs import (
    DISPATCHER_SUBMISSION_RECEIPT_FILENAME,
    clear_render_job_blacklist,
    recover_stalled_render_job,
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


class RecoveryDispatcher(FakeManagerDispatcher):
    def __init__(
        self,
        cloud_job: dict,
        *,
        status: str = "queued",
        worker: str | None = None,
        lease_expires_at: int | None = None,
    ) -> None:
        super().__init__()
        self.cloud_job = dict(cloud_job)
        self.status = status
        self.worker = worker
        self.lease_expires_at = lease_expires_at

    def get_job(self, job_id: str) -> dict:
        return {
            "ok": True,
            "summary": {
                "job_id": job_id,
                "status": self.status,
                "worker": self.worker,
                "lease_expires_at": self.lease_expires_at,
            },
            "job": {
                **self.cloud_job,
                "job_id": job_id,
                "status": self.status,
                "worker": self.worker,
            },
        }


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

    def _stalled_cloud_job(self):
        source_data = read_json_object(self.source_folder / "job.json")
        source_data.update(
            {
                DISPATCHER_COORDINATION_FIELD: CLOUD_DISPATCHER_COORDINATION,
                "status": "rendering",
                "worker": "CRASHED-WORKER",
                "attempt": 2,
            }
        )
        write_json_atomic(self.source_folder / "job.json", source_data)
        stalled_folder = (
            self.paths.is_rendering
            / f"{source_data['job_id']}__CRASHED-WORKER"
        )
        self.source_folder.rename(stalled_folder)
        job = self._job()
        cloud_job = {
            **source_data,
            "status": "queued",
            "worker": None,
            "attempt": 3,
            "blacklisted_workers": ["CRASHED-WORKER"],
        }
        return job, stalled_folder, cloud_job

    def test_recover_stalled_job_preserves_id_and_returns_package_to_queue(self) -> None:
        job, stalled_folder, cloud_job = self._stalled_cloud_job()

        destination = recover_stalled_render_job(
            job,
            RecoveryDispatcher(cloud_job),
        )

        self.assertEqual(self.paths.needs_rendering / job.job_id, destination)
        self.assertFalse(stalled_folder.exists())
        recovered = read_json_object(destination / "job.json")
        self.assertEqual(job.job_id, recovered["job_id"])
        self.assertEqual("queued", recovered["status"])
        self.assertEqual(3, recovered["attempt"])
        self.assertEqual(["CRASHED-WORKER"], recovered["blacklisted_workers"])

    def test_recover_stalled_job_refuses_an_active_cloud_lease(self) -> None:
        job, stalled_folder, cloud_job = self._stalled_cloud_job()

        with self.assertRaises(DispatcherError) as caught:
            recover_stalled_render_job(
                job,
                RecoveryDispatcher(
                    cloud_job,
                    status="rendering",
                    worker="LIVE-WORKER",
                    lease_expires_at=1_786_000_000,
                ),
            )

        self.assertEqual("job_has_active_lease", caught.exception.code)
        self.assertTrue(stalled_folder.is_dir())


if __name__ == "__main__":
    unittest.main()
