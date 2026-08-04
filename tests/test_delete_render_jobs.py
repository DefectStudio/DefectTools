from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.delete_render_jobs import delete_render_jobs
from portable_pipe_tools.render_farm.get_all_render_jobs import (
    get_all_render_jobs,
)
from portable_pipe_tools.render_farm.queue import (
    create_queue_folders,
    write_json_atomic,
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


if __name__ == "__main__":
    unittest.main()
