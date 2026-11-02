from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from portable_pipe_tools.apps.farm_render_manager_app import FarmRenderManagerApp
from portable_pipe_tools.render_farm.cloud_manager import (
    get_cloud_render_jobs,
    hydrate_cloud_render_job,
)
from portable_pipe_tools.render_farm.manage_render_jobs import (
    resubmit_failed_render_job,
)


class VersionedJobDispatcher:
    """Keep two versions of one shot entirely in memory."""

    def __init__(self, *, status: str = "queued") -> None:
        self.payloads: dict[str, dict] = {}
        self.requested_ids: list[str] = []
        self.replacements: list[tuple[str, dict]] = []
        for version in (10, 11):
            job_id = f"ABC_000_0050_v{version:03d}_unique"
            file_format = f"ABC_000_0050/ABC_000_0050_v{version:03d}.{{frame_number}}"
            self.payloads[job_id] = {
                "schema_version": 1,
                "publisher_schema_version": 4,
                "job_id": job_id,
                "project": "devshow",
                "job_type": "unreal_movie_render_graph",
                "shot_name": "ABC_000_0050",
                "render_version": version,
                "status": status,
                "priority": 50,
                "submitted_utc": "2026-11-01T00:00:00Z",
                "output_relative_directory": "renders",
                "output_file_name_format": file_format,
                "submitted_output_directory": "K:/devshow/renders",
                "output_directory": "I:/worker/renders",
                "render_config": "/Game/_devshow/RenderSettings/beauty_LowHDsRGB",
                "graph_variable_overrides": [
                    {"name": "FileNameFormat", "value": file_format},
                    {
                        "name": "MP4FileNameFormat",
                        "value": f"ABC_000_0050/ABC_000_0050_v{version:03d}",
                    },
                    {"name": "EXR", "value": True},
                    {"name": "MP4", "value": True},
                ],
            }

    def list_jobs(self, *, limit: int, offset: int) -> list[dict]:
        return [deepcopy(payload) for payload in self.payloads.values()][
            offset : offset + limit
        ]

    def get_job(self, job_id: str) -> dict:
        self.requested_ids.append(job_id)
        return {"ok": True, "job": deepcopy(self.payloads[job_id])}

    def replace_job(self, source_job_id: str, replacement_job: dict) -> dict:
        self.replacements.append((source_job_id, deepcopy(replacement_job)))
        return {"ok": True, "created": True, "source_deleted": True}


class SameShotRenderVersionTests(unittest.TestCase):
    # Listing and actions must not need to touch a real render-farm directory.
    repository = Path(tempfile.gettempdir()) / "same-shot-render-version-test-farm"

    def test_listing_retains_both_versions_with_separate_names_and_paths(self) -> None:
        dispatcher = VersionedJobDispatcher()

        jobs = get_cloud_render_jobs(dispatcher, self.repository)

        self.assertEqual([10, 11], [job.render_version for job in jobs])
        self.assertEqual(
            ["ABC_000_0050_v010", "ABC_000_0050_v011"],
            [job.job_name for job in jobs],
        )
        self.assertNotEqual(jobs[0].job_folder, jobs[1].job_folder)
        self.assertEqual(
            [job.job_id for job in jobs],
            [job.job_folder.name for job in jobs],
        )

    def test_details_load_the_selected_version_by_job_id(self) -> None:
        dispatcher = VersionedJobDispatcher()
        selected = get_cloud_render_jobs(dispatcher, self.repository)[1]

        hydrated = hydrate_cloud_render_job(selected, dispatcher, self.repository)

        self.assertEqual([selected.job_id], dispatcher.requested_ids)
        self.assertEqual(11, hydrated.render_version)
        self.assertEqual(
            dispatcher.payloads[selected.job_id]["graph_variable_overrides"],
            hydrated.job_data["graph_variable_overrides"],
        )

    def test_rows_and_restored_selection_keep_versions_independent(self) -> None:
        jobs = get_cloud_render_jobs(VersionedJobDispatcher(), self.repository)
        app = FarmRenderManagerApp.__new__(FarmRenderManagerApp)
        app.job_tree = Mock()
        app.job_tree.get_children.return_value = ()
        app.job_tree.insert.side_effect = ("row-v010", "row-v011")
        app._jobs_by_item = {}
        app.details_title_var = Mock()
        app.set_job_details = Mock()
        app.log_text = Mock()
        app.log_source_var = Mock()
        app._update_summary = Mock()
        app._on_job_selected = Mock()

        app.set_jobs(jobs, (("devshow", jobs[1].job_id),))

        self.assertEqual(
            ["ABC_000_0050_v010", "ABC_000_0050_v011"],
            [call.kwargs["values"][0] for call in app.job_tree.insert.call_args_list],
        )
        app.job_tree.selection_set.assert_called_once_with(["row-v011"])
        app.job_tree.selection.return_value = ("row-v011",)
        self.assertEqual([jobs[1]], app._selected_jobs())
        self.assertEqual(jobs[0], app._jobs_by_item["row-v010"])

    def test_retry_replaces_only_selected_version_and_preserves_output_settings(self) -> None:
        dispatcher = VersionedJobDispatcher(status="failed")
        jobs = get_cloud_render_jobs(dispatcher, self.repository)
        original_payloads = deepcopy(dispatcher.payloads)
        selected = jobs[1]

        replacement_id = resubmit_failed_render_job(selected, dispatcher)

        self.assertEqual([selected.job_id], dispatcher.requested_ids)
        self.assertEqual(1, len(dispatcher.replacements))
        source_id, replacement = dispatcher.replacements[0]
        self.assertEqual(selected.job_id, source_id)
        self.assertNotEqual(selected.job_id, replacement_id)
        self.assertTrue(replacement_id.startswith("ABC_000_0050_v011_"))
        self.assertEqual(11, replacement["render_version"])
        for key in (
            "output_relative_directory",
            "output_file_name_format",
            "render_config",
            "graph_variable_overrides",
        ):
            self.assertEqual(original_payloads[selected.job_id][key], replacement[key])
        self.assertEqual("K:/devshow/renders", replacement["output_directory"])
        self.assertEqual(original_payloads, dispatcher.payloads)


if __name__ == "__main__":
    unittest.main()
