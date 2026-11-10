"""Publisher version/collision tests; all dispatcher traffic is replaced locally."""

from __future__ import annotations

import copy
import importlib
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock


_PLUGIN_PYTHON = (
    Path(__file__).resolve().parents[1]
    / "Unreal/DefectToolsDev/Plugins/QuickWidgetTools/Content/Python"
)
_SHOT = "DEV_000_0010"
_GRAPH = "/Game/Render/beauty.beauty"


class _LiveJob:
    def __init__(self, index: int, name: str = _SHOT) -> None:
        self.job_name = name
        self.path = f"/Engine/Transient.MoviePipelineQueue:Job_{index}"

    def get_path_name(self) -> str:
        return self.path

    def get_editor_property(self, name: str):
        if name == "job_name":
            return self.job_name
        raise AttributeError(name)


class _LiveQueue:
    def __init__(self, jobs: list[_LiveJob]) -> None:
        self.jobs = list(jobs)
        self.deleted: list[_LiveJob] = []

    def get_jobs(self):
        return list(self.jobs)

    def delete_job(self, job: _LiveJob) -> None:
        self.jobs.remove(job)
        self.deleted.append(job)


def _load_publisher():
    fake_unreal = ModuleType("unreal")
    fake_unreal.log = lambda *args: None
    fake_unreal.log_warning = lambda *args: None
    fake_unreal.log_error = lambda *args: None
    fake_unreal.MoviePipelineQueueSubsystem = type("MoviePipelineQueueSubsystem", (), {})
    fake_unreal.get_editor_subsystem = mock.Mock()
    fake_unreal.AppMsgType = SimpleNamespace(YES_NO="YES_NO")
    fake_unreal.AppReturnType = SimpleNamespace(YES="YES")
    fake_unreal.EditorDialog = SimpleNamespace(show_message=mock.Mock(return_value="YES"))
    with mock.patch.dict(sys.modules, {"unreal": fake_unreal}):
        sys.modules.pop("publish_render_queue_to_farm", None)
        with mock.patch.object(sys, "path", [str(_PLUGIN_PYTHON), *sys.path]):
            publisher = importlib.import_module("publish_render_queue_to_farm")
    return publisher, fake_unreal


class UnrealFarmPublisherVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.publisher, cls.unreal = _load_publisher()

    def setUp(self) -> None:
        # The runner points TEMP/TMP at I:\AICache; no project scratch is created.
        temporary_directory = tempfile.TemporaryDirectory(prefix="publisher-versions-")
        self.addCleanup(temporary_directory.cleanup)
        self.show_root = Path(temporary_directory.name) / "show"
        self.output_root = self.show_root / "DEV_000" / _SHOT / "lite/unreal/_output"
        self.project = str(Path(temporary_directory.name) / "Development.uproject")
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(
            self.publisher,
            "urlopen",
            side_effect=AssertionError("A publisher regression test attempted network I/O"),
        ).start()
        mock.patch.object(
            self.publisher, "_project_file_from_document", return_value=self.project
        ).start()
        mock.patch.object(
            self.publisher, "_submitted_git_commit", return_value="a" * 40
        ).start()
        self.unreal.EditorDialog.show_message.reset_mock()

    @staticmethod
    def _variable(name: str, value, value_type: str = "String") -> dict:
        if value_type == "Bool":
            serialized = "true" if value else "false"
        else:
            serialized = str(value)
        return {
            "name": name,
            "enabled": True,
            "serialized_value": serialized,
            "value_type": value_type,
            "container_type": "None",
            "value_type_object": "",
        }

    def _snapshot(
        self,
        version: int,
        index: int,
        *,
        exr: bool = True,
        mp4: bool = True,
        exr_name: str | None = None,
        mp4_name: str | None = None,
        enabled: bool = True,
    ) -> dict:
        stem = f"{_SHOT}_beauty_v{version:03d}"
        variables = [
            self._variable(
                "OutputDirectory",
                f'(Path="{str(self.output_root).replace(chr(92), "/")}")',
                "Struct",
            ),
            self._variable("FileNameFormat", exr_name or f"{stem}/{stem}.{{frame_number}}"),
            self._variable("MP4FileNameFormat", mp4_name or stem),
            self._variable("EXR", exr, "Bool"),
            self._variable("MP4", mp4, "Bool"),
            self._variable("Hero", False, "Bool"),
        ]
        return {
            "queue_index": index,
            "object_path": _LiveJob(index).get_path_name(),
            "job_name": _SHOT,
            "enabled": enabled,
            "consumed": False,
            "map": "/Game/Maps/Test.Test",
            "sequence": f"/Game/Sequences/{_SHOT}.{_SHOT}",
            "graph_preset": _GRAPH,
            "config_mode": "Graph",
            "is_using_graph_configuration": True,
            "sequence_playback_range": {
                "display_start": 1001,
                "display_end_exclusive": 1011,
                "display_frame_count": 10,
                "source": "level_sequence_playback_range",
            },
            "graph_variable_assignments": [{"graph": _GRAPH, "variables": variables}],
            "warnings": [],
            "shots": [],
        }

    def _document(self, *jobs: dict) -> dict:
        return {
            "source": {
                "project_name": "Development",
                "project_file": self.project,
                "computer": "UNIT-TEST",
                "user": "unit-test",
                "engine_version": "5.8",
            },
            "warnings": [],
            "queue": {"jobs": list(jobs)},
        }

    def _validate(self, *jobs: dict) -> list[dict]:
        packages, _, _ = self.publisher._validate_and_build_packages(
            self._document(*jobs), 50, str(self.show_root)
        )
        return packages

    def _connect_live_queue(self, snapshots: list[dict]) -> _LiveQueue:
        queue = _LiveQueue([_LiveJob(job["queue_index"]) for job in snapshots])
        self.unreal.get_editor_subsystem.return_value = SimpleNamespace(
            get_queue=lambda: queue
        )
        return queue

    def test_vram_plus_requires_dispatcher_routing(self) -> None:
        job = self._snapshot(1, 0)
        vram_plus = self._variable("VRAMPlus", True, "Bool")
        job["graph_variable_assignments"][0]["variables"].append(vram_plus)

        with self.assertRaisesRegex(ValueError, "VRAM\\+ farm submission requires Dispatcher GPU routing"):
            self._validate(job)

        vram_plus["serialized_value"] = "false"
        self.assertEqual(1, len(self._validate(job)))

    def _stub_run_dependencies(self, document: dict):
        mock.patch.object(
            self.publisher, "_inspect_current_queue", return_value=document
        ).start()
        mock.patch.object(
            self.publisher, "_load_show_file_server_root", return_value=str(self.show_root)
        ).start()
        mock.patch.object(
            self.publisher,
            "_load_dispatcher_submit_connection",
            return_value=("https://unit-test.invalid", "unit-test-token"),
        ).start()
        mock.patch.object(self.publisher, "_verify_dispatcher_health").start()

    def test_same_shot_name_with_distinct_versions_builds_two_jobs(self) -> None:
        packages = self._validate(self._snapshot(2, 0), self._snapshot(3, 1))
        self.assertEqual([_SHOT, _SHOT], [job["shot_name"] for job in packages])
        self.assertEqual([2, 3], [job["render_version"] for job in packages])
        self.assertEqual(2, len({job["submission_fingerprint"] for job in packages}))
        self.assertEqual(2, len({job["job_id"] for job in packages}))

    def test_true_exr_output_collision_is_rejected_even_with_distinct_mp4_names(self) -> None:
        shared_exr = f"{_SHOT}_beauty_v002/{_SHOT}_beauty_v002.{{frame_number}}"
        with self.assertRaisesRegex(ValueError, "output target"):
            self._validate(
                self._snapshot(2, 0, exr_name=shared_exr),
                self._snapshot(
                    2, 1, exr_name=shared_exr, mp4_name="alternate_review_v002"
                ),
            )

    def test_true_mp4_collision_is_rejected_even_with_distinct_exr_names(self) -> None:
        shared_mp4 = f"{_SHOT}_beauty_v002"
        with self.assertRaisesRegex(ValueError, "output target"):
            self._validate(
                self._snapshot(2, 0, mp4_name=shared_mp4),
                self._snapshot(
                    2,
                    1,
                    mp4_name=shared_mp4,
                    exr_name="alternate_v002/alternate_v002.{frame_number}",
                ),
            )

    def test_disabled_exr_targets_do_not_block_distinct_mp4_jobs(self) -> None:
        shared_exr = f"{_SHOT}_beauty_v001/{_SHOT}_beauty_v001.{{frame_number}}"
        packages = self._validate(
            self._snapshot(2, 0, exr=False, exr_name=shared_exr),
            self._snapshot(3, 1, exr=False, exr_name=shared_exr),
        )
        self.assertEqual(2, len(packages))
        self.assertEqual([2, 3], [package["render_version"] for package in packages])

    def test_disabled_mp4_targets_do_not_block_distinct_exr_jobs(self) -> None:
        shared_mp4 = f"{_SHOT}_beauty_v001"
        packages = self._validate(
            self._snapshot(2, 0, mp4=False, mp4_name=shared_mp4),
            self._snapshot(3, 1, mp4=False, mp4_name=shared_mp4),
        )
        self.assertEqual(2, len(packages))
        self.assertEqual([2, 3], [package["render_version"] for package in packages])

    def test_enabled_outputs_with_different_versions_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "different render versions"):
            self._validate(self._snapshot(3, 0, mp4_name=f"{_SHOT}_beauty_v002"))

    def test_enabled_mp4_requires_its_own_filename_override(self) -> None:
        snapshot = self._snapshot(3, 0, exr=False, mp4=True)
        variables = snapshot["graph_variable_assignments"][0]["variables"]
        variables[:] = [item for item in variables if item["name"] != "MP4FileNameFormat"]
        with self.assertRaisesRegex(ValueError, "MP4FileNameFormat"):
            self._validate(snapshot)

    def test_complementary_formats_at_same_version_are_separate_payloads(self) -> None:
        packages = self._validate(
            self._snapshot(2, 0, exr=True, mp4=False),
            self._snapshot(2, 1, exr=False, mp4=True),
        )
        self.assertEqual(2, len(packages))
        self.assertNotEqual(
            packages[0]["submission_fingerprint"], packages[1]["submission_fingerprint"]
        )

    def test_format_extensions_keep_same_literal_names_in_separate_namespaces(self) -> None:
        directory = str(self.output_root)
        exr_only = {
            "output_directory": directory,
            "output_file_name_format": "same_v002",
            "mp4_file_name_format": "same_v002",
            "outputs": {"exr": True, "mp4": False},
        }
        mp4_only = copy.deepcopy(exr_only)
        mp4_only["outputs"] = {"exr": False, "mp4": True}
        self.assertFalse(
            self.publisher._package_output_keys(exr_only)
            & self.publisher._package_output_keys(mp4_only)
        )

    def test_confirmation_identifies_each_version(self) -> None:
        packages = self._validate(self._snapshot(2, 0), self._snapshot(3, 1))
        self.assertTrue(self.publisher._show_confirmation(packages, "unit-test-farm", True))
        message = self.unreal.EditorDialog.show_message.call_args.args[1]
        self.assertIn("v002", message)
        self.assertIn("v003", message)

    def test_success_removes_both_versions_and_preserves_disabled_jobs(self) -> None:
        snapshots = [self._snapshot(2, 0), self._snapshot(3, 1), self._snapshot(4, 2, enabled=False)]
        queue = self._connect_live_queue(snapshots)
        untouched_job = queue.jobs[2]
        self._stub_run_dependencies(self._document(*snapshots))
        submit = mock.patch.object(
            self.publisher,
            "_submit_job_to_dispatcher",
            side_effect=lambda package, *args: package["job_id"],
        ).start()
        summary = self.publisher.run(require_confirmation=False, use_v2=True)
        self.assertIn("success=1;", summary)
        self.assertIn("jobs_published=2;", summary)
        self.assertEqual(2, submit.call_count)
        self.assertEqual([untouched_job], queue.jobs)
        self.assertEqual(2, len(queue.deleted))

    def test_partial_submission_failure_preserves_all_editor_jobs_for_retry(self) -> None:
        snapshots = [self._snapshot(2, 0), self._snapshot(3, 1)]
        queue = self._connect_live_queue(snapshots)
        original_jobs = list(queue.jobs)
        self._stub_run_dependencies(self._document(*snapshots))
        mock.patch.object(
            self.publisher,
            "_submit_job_to_dispatcher",
            side_effect=["accepted-first-job", RuntimeError("simulated dispatcher failure")],
        ).start()
        summary = self.publisher.run(require_confirmation=False, use_v2=True)
        self.assertIn("success=0;", summary)
        self.assertIn("jobs_published=1;", summary)
        self.assertEqual(original_jobs, queue.jobs)
        self.assertEqual([], queue.deleted)

    def test_queue_index_validation_happens_before_any_cleanup(self) -> None:
        snapshots = [self._snapshot(2, 0), self._snapshot(3, 1)]
        packages = self._validate(*snapshots)
        queue = self._connect_live_queue(snapshots)
        packages[1]["mrq_snapshot"]["queue_index"] = 0
        with self.assertRaises(RuntimeError):
            self.publisher._remove_published_jobs_from_queue(packages, 2)
        self.assertEqual(2, len(queue.jobs))
        self.assertEqual([], queue.deleted)

    def test_equal_name_jobs_swapped_during_submit_are_not_removed(self) -> None:
        snapshots = [self._snapshot(2, 0), self._snapshot(3, 1)]
        packages = self._validate(*snapshots)
        queue = self._connect_live_queue(snapshots)
        queue.jobs.reverse()
        original_jobs = list(queue.jobs)
        with self.assertRaises(RuntimeError):
            self.publisher._remove_published_jobs_from_queue(packages, 2)
        self.assertEqual(original_jobs, queue.jobs)
        self.assertEqual([], queue.deleted)

    def test_missing_snapshot_identity_prevents_cleanup(self) -> None:
        snapshots = [self._snapshot(2, 0), self._snapshot(3, 1)]
        packages = self._validate(*snapshots)
        queue = self._connect_live_queue(snapshots)
        packages[1]["mrq_snapshot"].pop("object_path")
        with self.assertRaises(RuntimeError):
            self.publisher._remove_published_jobs_from_queue(packages, 2)
        self.assertEqual(2, len(queue.jobs))
        self.assertEqual([], queue.deleted)


if __name__ == "__main__":
    unittest.main()
