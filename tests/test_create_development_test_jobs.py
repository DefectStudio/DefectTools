from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.create_development_test_jobs import (
    create_development_test_jobs,
)
from portable_pipe_tools.render_farm.get_all_render_jobs import (
    get_all_render_jobs,
)
from portable_pipe_tools.render_farm.queue import QUEUE_FOLDER_NAMES


class CreateDevelopmentTestJobsTests(unittest.TestCase):
    def test_creates_completed_development_jobs_and_all_queue_folders(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)

            created = create_development_test_jobs(repository, count=5)
            jobs = get_all_render_jobs(repository)

            self.assertEqual(5, len(created))
            self.assertEqual(5, len(jobs))
            self.assertTrue(all(job.project == "Development" for job in jobs))
            self.assertTrue(all(job.status == "complete" for job in jobs))
            self.assertTrue(
                all(job.job_data.get("deletion_test_job") is True for job in jobs)
            )
            render_farm = repository / "Development" / "renderFarm"
            self.assertEqual(
                set(QUEUE_FOLDER_NAMES),
                {folder.name for folder in render_farm.iterdir() if folder.is_dir()},
            )

    def test_count_must_be_positive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(ValueError):
                create_development_test_jobs(temporary_directory, count=0)


if __name__ == "__main__":
    unittest.main()
