from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.get_all_render_jobs import (
    get_all_render_jobs,
)
from portable_pipe_tools.render_farm.get_render_job_details import (
    MISSING_VALUE,
    JobDetailSection,
    get_render_job_details,
)
from portable_pipe_tools.render_farm.queue import (
    create_queue_folders,
    write_json_atomic,
)


def _section_values(section: JobDetailSection) -> dict[str, str]:
    return {detail.property_name: detail.value for detail in section.details}


class GetRenderJobDetailsTests(unittest.TestCase):
    def test_builds_deadline_style_sections_from_job_and_result_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            paths = create_queue_folders(
                repository / "S3Bishop" / "renderFarm"
            )
            job_folder = paths.render_complete / "bishop-shot-010"
            job_folder.mkdir()
            write_json_atomic(
                job_folder / "job.json",
                {
                    "job_id": "bishop-shot-010",
                    "job_type": "unreal_mrq",
                    "batch_id": "bishop-batch-1",
                    "shot_name": "BSH_010_0010",
                    "render_version": 11,
                    "project": "S3Bishop",
                    "submitted_user": "artist",
                    "submitted_by": "WORKSTATION-01",
                    "submitted_utc": "2026-08-04T17:00:00Z",
                    "priority": 75,
                    "attempt": 2,
                    "worker": "RENDER-02",
                    "claimed_utc": "2026-08-04T17:01:00Z",
                    "render_started_utc": "2026-08-04T17:02:00Z",
                    "render_finished_utc": "2026-08-04T17:03:05Z",
                    "frame_start": 1001,
                    "frame_end": 1100,
                    "frame_end_semantics": "exclusive",
                    "frame_count": 99,
                    "render_config": "/Game/Render/Final",
                    "config_mode": "movie_render_graph",
                    "level": "/Game/Maps/Bishop",
                    "sequence": "/Game/Cinematics/Shot010",
                    "engine_version": "5.8",
                    "output_directory": "//server/renders/bishop/shot010",
                    "output_file_name_format": "{shot}_{frame_number}",
                    "mp4_file_name_format": "{shot}_review",
                    "outputs": {"mp4": True, "exr": True, "hero": False},
                    "uproject": "F:/Projects/S3Bishop/S3Bishop.uproject",
                    "submitted_git_commit": "abc123",
                    "rendered_git_commit": "def456",
                    "sync_policy": "submitted_commit",
                },
            )
            write_json_atomic(
                job_folder / "result.json",
                {
                    "status": "complete",
                    "exit_code": 0,
                    "reason": "Render completed successfully.",
                    "simulated": False,
                    "output_file_count": 100,
                },
            )

            job = get_all_render_jobs(repository)[0]
            sections = get_render_job_details(job)
            section_map = {
                section.name: _section_values(section) for section in sections
            }

            self.assertEqual(
                (
                    "General",
                    "Submission",
                    "Render",
                    "Worker & Timing",
                    "Output",
                    "Result",
                    "Advanced",
                ),
                tuple(section.name for section in sections),
            )
            self.assertEqual("bishop-shot-010", section_map["General"]["Job ID"])
            self.assertEqual("Complete", section_map["General"]["Status"])
            self.assertEqual("v011", section_map["Render"]["Render Version"])
            self.assertEqual("1001-1099", section_map["Render"]["Frame Range"])
            self.assertEqual(
                "00:01:05",
                section_map["Worker & Timing"]["Render Duration"],
            )
            self.assertEqual("Yes", section_map["Output"]["MP4 Enabled"])
            self.assertEqual("No", section_map["Output"]["Hero Enabled"])
            self.assertEqual("0", section_map["Result"]["Exit Code"])
            self.assertEqual("No", section_map["Result"]["Simulated"])
            self.assertEqual(
                "Render completed successfully.",
                section_map["Result"]["Reason"],
            )

    def test_missing_optional_values_have_a_consistent_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            paths = create_queue_folders(
                repository / "Development" / "renderFarm"
            )
            job_folder = paths.needs_rendering / "minimal-job"
            job_folder.mkdir()
            write_json_atomic(
                job_folder / "job.json",
                {"job_id": "minimal-job"},
            )

            sections = get_render_job_details(get_all_render_jobs(repository)[0])
            section_map = {
                section.name: _section_values(section) for section in sections
            }

            self.assertEqual(MISSING_VALUE, section_map["Result"]["Reason"])
            self.assertEqual(
                MISSING_VALUE,
                section_map["Worker & Timing"]["Render Duration"],
            )
            self.assertEqual(MISSING_VALUE, section_map["Output"]["MP4 Enabled"])
