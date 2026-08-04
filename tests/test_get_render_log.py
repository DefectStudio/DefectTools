from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.get_all_render_jobs import (
    get_all_render_jobs,
)
from portable_pipe_tools.render_farm.get_render_log import get_render_log
from portable_pipe_tools.render_farm.queue import (
    create_queue_folders,
    write_json_atomic,
)


class GetRenderLogTests(unittest.TestCase):
    def test_primary_unreal_log_is_returned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            paths = create_queue_folders(repository / "show" / "renderFarm")
            job_folder = paths.render_complete / "job-1"
            job_folder.mkdir()
            write_json_atomic(
                job_folder / "job.json",
                {"job_id": "job-1", "shot_name": "SHOT_010", "status": "complete"},
            )
            (job_folder / "unreal.log").write_text(
                "Primary Unreal log\nFinished",
                encoding="utf-8",
            )
            (job_folder / "unreal_stdout.log").write_text(
                "Console fallback",
                encoding="utf-8",
            )

            job = get_all_render_jobs(repository)[0]

            self.assertEqual("Primary Unreal log\nFinished", get_render_log(job))

    def test_stdout_is_used_when_primary_log_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            paths = create_queue_folders(repository / "show" / "renderFarm")
            job_folder = paths.is_rendering / "job-2__WORKER"
            job_folder.mkdir()
            write_json_atomic(job_folder / "job.json", {"job_id": "job-2"})
            (job_folder / "unreal_stdout.log").write_text(
                "Live stdout",
                encoding="utf-8",
            )

            job = get_all_render_jobs(repository)[0]

            self.assertEqual("Live stdout", get_render_log(job))

    def test_failure_reason_is_shown_when_unreal_never_created_a_log(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            paths = create_queue_folders(repository / "show" / "renderFarm")
            job_folder = paths.render_failed / "job-3__WORKER"
            job_folder.mkdir()
            write_json_atomic(job_folder / "job.json", {"job_id": "job-3"})
            write_json_atomic(
                job_folder / "result.json",
                {"status": "failed", "reason": "Unreal executable was missing"},
            )

            job = get_all_render_jobs(repository)[0]
            log_text = get_render_log(job)

            self.assertIn("No Unreal render log is available", log_text)
            self.assertIn("Unreal executable was missing", log_text)


if __name__ == "__main__":
    unittest.main()
