from __future__ import annotations

from pathlib import Path
import unittest

from portable_pipe_tools.render_farm.render_job import RenderJob
from portable_pipe_tools.render_farm.sort_render_jobs import (
    default_sort_descending,
    sort_render_jobs,
)


def _job(
    name: str,
    *,
    user: str = "artist",
    status: str = "queued",
    worker: str = "",
    errors: int = 0,
    progress: float = 0,
    submitted: str = "2026-08-04T12:00:00Z",
) -> RenderJob:
    folder = Path("renderFarm") / name
    return RenderJob(
        project="Development",
        submitted_project="Development",
        queue_name="01_NeedsRendering",
        status=status,
        job_folder=folder,
        job_json_path=folder / "job.json",
        result_json_path=folder / "result.json",
        job_id=name,
        job_name=name,
        shot_name=name,
        render_version=1,
        submitted_user=user,
        submitted_by="WORKSTATION",
        submitted_utc=submitted,
        priority=50,
        worker=worker,
        frame_start=1,
        frame_end=2,
        frame_count=1,
        progress=progress,
        error_count=errors,
        render_started_utc="",
        render_finished_utc="",
        output_directory="",
        render_config="",
    )


class SortRenderJobsTests(unittest.TestCase):
    def test_errors_sort_numerically_in_both_directions(self) -> None:
        jobs = [
            _job("no-errors", errors=0),
            _job("two-errors", errors=2),
            _job("one-error", errors=1),
        ]

        descending = sort_render_jobs(jobs, "errors", descending=True)
        ascending = sort_render_jobs(jobs, "errors", descending=False)

        self.assertEqual(
            ["two-errors", "one-error", "no-errors"],
            [job.job_name for job in descending],
        )
        self.assertEqual(
            ["no-errors", "one-error", "two-errors"],
            [job.job_name for job in ascending],
        )

    def test_text_sort_is_case_insensitive(self) -> None:
        jobs = [_job("Zulu"), _job("alpha"), _job("Bravo")]

        sorted_jobs = sort_render_jobs(jobs, "job_name")

        self.assertEqual(
            ["alpha", "Bravo", "Zulu"],
            [job.job_name for job in sorted_jobs],
        )

    def test_worker_sort_uses_only_currently_rendering_jobs(self) -> None:
        jobs = [
            _job("render-b", status="rendering", worker="ZEBRA"),
            _job("queued-old-worker", status="queued", worker="ALPHA"),
            _job("render-a", status="rendering", worker="bravo"),
        ]

        sorted_jobs = sort_render_jobs(jobs, "worker")

        self.assertEqual(
            ["render-a", "render-b", "queued-old-worker"],
            [job.job_name for job in sorted_jobs],
        )

    def test_missing_timestamps_remain_at_end_in_both_directions(self) -> None:
        jobs = [
            _job("missing", submitted=""),
            _job("new", submitted="2026-08-04T13:00:00Z"),
            _job("old", submitted="2026-08-04T11:00:00Z"),
        ]

        newest_first = sort_render_jobs(jobs, "submitted", descending=True)
        oldest_first = sort_render_jobs(jobs, "submitted", descending=False)

        self.assertEqual(
            ["new", "old", "missing"],
            [job.job_name for job in newest_first],
        )
        self.assertEqual(
            ["old", "new", "missing"],
            [job.job_name for job in oldest_first],
        )

    def test_useful_numeric_columns_default_to_highest_first(self) -> None:
        self.assertTrue(default_sort_descending("errors"))
        self.assertTrue(default_sort_descending("progress"))
        self.assertTrue(default_sort_descending("submitted"))
        self.assertFalse(default_sort_descending("job_name"))

    def test_unknown_column_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            sort_render_jobs([_job("job")], "unknown")


if __name__ == "__main__":
    unittest.main()
