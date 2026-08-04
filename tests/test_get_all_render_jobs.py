from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.get_all_render_jobs import (
    get_all_render_jobs,
)
from portable_pipe_tools.render_farm.queue import (
    QUEUE_FOLDER_NAMES,
    create_queue_folders,
    write_json_atomic,
)
from portable_pipe_tools.render_farm.render_job import RenderJob


class GetAllRenderJobsTests(unittest.TestCase):
    def test_builds_render_job_objects_from_all_five_queues(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            farm_root = repository / "s3bishop" / "renderFarm"
            create_queue_folders(farm_root)

            for index, queue_name in enumerate(QUEUE_FOLDER_NAMES):
                job_folder = farm_root / queue_name / f"job-{index}"
                job_folder.mkdir()
                write_json_atomic(
                    job_folder / "job.json",
                    {
                        "job_id": f"job-{index}",
                        "shot_name": f"BSH_000_00{index}0",
                        "render_version": index + 1,
                        "project": "s3bishop",
                        "submitted_user": "artist",
                        "submitted_utc": f"2026-08-04T00:00:0{index}.000Z",
                        "frame_start": 1001,
                        "frame_end": 1011,
                        "frame_count": 10,
                    },
                )

            jobs = get_all_render_jobs(repository)

            self.assertEqual(5, len(jobs))
            self.assertTrue(all(isinstance(job, RenderJob) for job in jobs))
            self.assertEqual(
                {"submitting", "queued", "rendering", "complete", "failed"},
                {job.status for job in jobs},
            )
            self.assertTrue(all(job.project == "s3bishop" for job in jobs))
            completed_job = next(job for job in jobs if job.status == "complete")
            self.assertEqual(100, completed_job.progress)

    def test_missing_job_json_still_returns_the_visible_job_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            farm_root = repository / "s3bishop" / "renderFarm"
            paths = create_queue_folders(farm_root)
            missing_payload_folder = paths.is_rendering / "SHOT_v001__WORKER-01"
            missing_payload_folder.mkdir()

            jobs = get_all_render_jobs(repository)

            self.assertEqual(1, len(jobs))
            self.assertEqual("rendering", jobs[0].status)
            self.assertEqual("WORKER-01", jobs[0].worker)
            self.assertIsNotNone(jobs[0].load_error)

    def test_projects_without_render_farm_folders_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            (repository / "not_a_show").mkdir()

            self.assertEqual([], get_all_render_jobs(repository))


if __name__ == "__main__":
    unittest.main()
