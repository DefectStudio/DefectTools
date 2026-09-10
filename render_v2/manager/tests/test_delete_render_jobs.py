from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.cloud_dispatch import DispatcherError
from portable_pipe_tools.render_farm.delete_render_jobs import (
    delete_render_jobs,
    delete_render_jobs_with_dispatcher,
)
from portable_pipe_tools.render_farm.get_all_render_jobs import (
    get_all_render_jobs,
)
from portable_pipe_tools.render_farm.queue import (
    CLOUD_DISPATCHER_COORDINATION,
    DISPATCHER_COORDINATION_FIELD,
    create_queue_folders,
    write_json_atomic,
)


class RecordingDeleteDispatcher:
    def __init__(self, expected_folder: Path | None = None) -> None:
        self.expected_folder = expected_folder
        self.deleted: list[str] = []

    def delete_job(self, job_id: str) -> dict:
        if self.expected_folder is not None and not self.expected_folder.is_dir():
            raise AssertionError("Dropbox package was deleted before D1 confirmation")
        self.deleted.append(job_id)
        return {
            "ok": True,
            "deleted": True,
            "deletion_confirmed": True,
        }


class FailingDeleteDispatcher:
    def delete_job(self, job_id: str) -> dict:
        raise DispatcherError(
            f"Could not delete {job_id}",
            status=503,
            code="dispatcher_unavailable",
        )


class DeleteRenderJobsTests(unittest.TestCase):
    def test_deletes_valid_job_package_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            paths = create_queue_folders(repository / "show" / "renderFarm")
            job_folder = paths.needs_rendering / "job-1"
            job_folder.mkdir()
            write_json_atomic(job_folder / "job.json", {"job_id": "job-1"})
            job = get_all_render_jobs(repository)[0]

            result = delete_render_jobs([job])

            self.assertFalse(job_folder.exists())
            self.assertEqual((job_folder.absolute(),), result.deleted_folders)
            self.assertEqual((), result.errors)

    def test_refuses_folder_outside_a_render_farm_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            paths = create_queue_folders(repository / "show" / "renderFarm")
            job_folder = paths.needs_rendering / "job-1"
            job_folder.mkdir()
            write_json_atomic(job_folder / "job.json", {"job_id": "job-1"})
            job = get_all_render_jobs(repository)[0]
            unsafe_folder = repository / "unrelated-folder"
            unsafe_folder.mkdir()
            unsafe_job = replace(job, job_folder=unsafe_folder)

            result = delete_render_jobs([unsafe_job])

            self.assertTrue(unsafe_folder.exists())
            self.assertEqual((), result.deleted_folders)
            self.assertIn("Refused unsafe delete target", result.errors[0])

    def test_cloud_delete_is_confirmed_before_dropbox_package_removal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            paths = create_queue_folders(repository / "show" / "renderFarm")
            job_folder = paths.render_complete / "cloud-job"
            job_folder.mkdir()
            write_json_atomic(
                job_folder / "job.json",
                {
                    "job_id": "cloud-job",
                    DISPATCHER_COORDINATION_FIELD: CLOUD_DISPATCHER_COORDINATION,
                },
            )
            job = get_all_render_jobs(repository)[0]
            dispatcher = RecordingDeleteDispatcher(job_folder)

            result = delete_render_jobs_with_dispatcher([job], dispatcher)

            self.assertEqual([job.job_id], dispatcher.deleted)
            self.assertFalse(job_folder.exists())
            self.assertEqual((job_folder.absolute(),), result.deleted_folders)
            self.assertEqual((job.job_id,), result.deleted_job_ids)
            self.assertEqual((), result.errors)

    def test_d1_authoritative_delete_needs_no_dropbox_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            paths = create_queue_folders(repository / "show" / "renderFarm")
            legacy_folder = paths.render_complete / "cloud-job"
            legacy_folder.mkdir()
            write_json_atomic(legacy_folder / "job.json", {"job_id": "cloud-job"})
            legacy_job = get_all_render_jobs(repository)[0]
            missing_folder = paths.render_complete / "not-on-dropbox"
            cloud_job = replace(
                legacy_job,
                job_folder=missing_folder,
                job_json_path=missing_folder / "job.json",
                result_json_path=missing_folder / "result.json",
                control_source="cloud",
            )
            dispatcher = RecordingDeleteDispatcher()

            result = delete_render_jobs_with_dispatcher([cloud_job], dispatcher)

            self.assertEqual(["cloud-job"], dispatcher.deleted)
            self.assertEqual((), result.deleted_folders)
            self.assertEqual(("cloud-job",), result.deleted_job_ids)
            self.assertEqual((), result.errors)

    def test_cloud_delete_failure_preserves_dropbox_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            paths = create_queue_folders(repository / "show" / "renderFarm")
            job_folder = paths.render_complete / "cloud-job"
            job_folder.mkdir()
            write_json_atomic(
                job_folder / "job.json",
                {
                    "job_id": "cloud-job",
                    DISPATCHER_COORDINATION_FIELD: CLOUD_DISPATCHER_COORDINATION,
                },
            )
            job = get_all_render_jobs(repository)[0]

            result = delete_render_jobs_with_dispatcher(
                [job],
                FailingDeleteDispatcher(),
            )

            self.assertTrue(job_folder.is_dir())
            self.assertEqual((), result.deleted_folders)
            self.assertIn("Cloud Dispatcher", result.errors[0])

    def test_cloud_job_without_manager_connection_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            paths = create_queue_folders(repository / "show" / "renderFarm")
            job_folder = paths.render_complete / "cloud-job"
            job_folder.mkdir()
            write_json_atomic(
                job_folder / "job.json",
                {
                    "job_id": "cloud-job",
                    DISPATCHER_COORDINATION_FIELD: CLOUD_DISPATCHER_COORDINATION,
                },
            )
            job = get_all_render_jobs(repository)[0]

            result = delete_render_jobs_with_dispatcher([job], None)

            self.assertTrue(job_folder.is_dir())
            self.assertEqual((), result.deleted_folders)
            self.assertIn("cloud connection is not configured", result.errors[0])


if __name__ == "__main__":
    unittest.main()
