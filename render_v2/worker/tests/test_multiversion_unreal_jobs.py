"""Keep same-shot farm versions independent through worker preparation."""

from __future__ import annotations

import ast
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from portable_pipe_tools.render_farm.cloud_queue import materialize_cloud_job_package
from portable_pipe_tools.render_farm.local_paths import prepare_worker_output_mapping
from portable_pipe_tools.render_farm.queue import (
    JOB_FILENAME,
    create_queue_folders,
    read_json_object,
)


RUNTIME_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "unreal/RenderWorkerRuntime/Content/Python/render_worker_runtime_executor.py"
)


def _load_runtime_helpers():
    source = ast.parse(RUNTIME_SOURCE.read_text(encoding="utf-8"))
    helpers = ast.Module(
        body=[
            node for node in source.body
            if isinstance(
                node,
                (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign, ast.FunctionDef),
            )
        ],
        type_ignores=[],
    )
    namespace = {"__file__": str(RUNTIME_SOURCE)}
    exec(compile(helpers, str(RUNTIME_SOURCE), "exec"), namespace)
    return namespace


def _job(version):
    stem = f"ABC_000_0050_beauty_v{version:03d}"
    exr_format = f"{stem}/{stem}.{{frame_number}}"
    serialized = {
        "OutputDirectory": '(Path="K:/defect/devshow/sequences/ABC/ABC_000_0050/lite/unreal/_output")',
        "FileNameFormat": exr_format,
        "MP4FileNameFormat": stem,
        "EXR": "True",
        "MP4": "True",
    }
    return {
        "job_id": f"batch_ABC_000_0050_v{version:03d}",
        "shot_name": "ABC_000_0050",
        "render_version": version,
        "status": "rendering",
        "sequence": "/Game/Test/ABC_000_0050.ABC_000_0050",
        "level": "/Game/Test/Level.Level",
        "render_config": "/Game/_devshow/RenderSettings/beauty_LowHDsRGB.beauty_LowHDsRGB",
        "output_directory": "K:/defect/devshow/sequences/ABC/ABC_000_0050/lite/unreal/_output",
        "output_relative_directory": "sequences/ABC/ABC_000_0050/lite/unreal/_output",
        "output_file_name_format": exr_format,
        "mp4_file_name_format": stem,
        "outputs": {"exr": True, "mp4": True},
        "graph_variable_overrides": {
            name: {"enabled": True, "serialized_value": value}
            for name, value in serialized.items()
        },
    }


class MultiversionWorkerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.farm_root = self.root / "devshow" / "renderFarm"
        self.farm_root.mkdir(parents=True)

    def test_cloud_spool_keeps_same_shot_versions_in_distinct_packages(self):
        paths = create_queue_folders(self.farm_root)
        jobs = [_job(2), _job(3)]
        folders = [materialize_cloud_job_package(paths, job) for job in jobs]

        self.assertNotEqual(folders[0], folders[1])
        for folder, job in zip(folders, jobs):
            self.assertEqual(read_json_object(folder / JOB_FILENAME), job)

    def test_preparing_next_version_preserves_previous_version_outputs(self):
        previous, following = _job(2), _job(3)
        prepare_worker_output_mapping(previous, self.farm_root)
        output = Path(previous["worker_output_directory"])
        previous_exr = output / (
            previous["output_file_name_format"].replace("{frame_number}", "0001") + ".exr"
        )
        previous_exr.parent.mkdir(parents=True)
        previous_exr.write_bytes(b"previous EXR")
        previous_mp4 = output / (previous["mp4_file_name_format"] + ".mp4")
        previous_mp4.write_bytes(b"previous MP4")

        prepare_worker_output_mapping(following, self.farm_root)

        self.assertEqual(previous["worker_output_directory"], following["worker_output_directory"])
        self.assertEqual(previous_exr.read_bytes(), b"previous EXR")
        self.assertEqual(previous_mp4.read_bytes(), b"previous MP4")
        self.assertNotEqual(previous["output_file_name_format"], following["output_file_name_format"])
        self.assertNotEqual(previous["mp4_file_name_format"], following["mp4_file_name_format"])

    def test_runtime_builds_independent_jobs_with_each_versions_graph_overrides(self):
        unreal = types.ModuleType("unreal")
        unreal.log = Mock()
        unreal.MoviePipelineQueue = object()
        unreal.MoviePipelineExecutorJob = object()
        unreal.SoftObjectPath = lambda value: value
        unreal.DirectoryPath = lambda value: types.SimpleNamespace(export_text=lambda: f'(Path="{value}")')
        graph = Mock()
        variables = {}
        for name in _job(2)["graph_variable_overrides"]:
            variables[name] = Mock()
            variables[name].get_member_name.return_value = name
        graph.get_variables.return_value = list(variables.values())
        unreal.load_object = Mock(return_value=graph)
        queues, native_jobs = [], []

        def create_queue(_class, *, outer):
            queue = Mock()
            native = Mock()
            native.get_graph_preset.return_value = graph
            native.get_or_create_variable_overrides.return_value.set_value_serialized_string.return_value = True
            queue.allocate_new_job.return_value = native
            queues.append(queue)
            native_jobs.append(native)
            return queue

        unreal.new_object = create_queue
        with patch.dict(sys.modules, {"unreal": unreal}):
            runtime = _load_runtime_helpers()
            jobs = [_job(2), _job(3)]
            for job in jobs:
                prepare_worker_output_mapping(job, self.farm_root)
                runtime["_build_pipeline_job"](types.SimpleNamespace(), job)

        self.assertIsNot(queues[0], queues[1])
        for native, job in zip(native_jobs, jobs):
            native.set_editor_property.assert_any_call("job_name", "ABC_000_0050")
            native.set_editor_property.assert_any_call("user_data", job["job_id"])
            container = native.get_or_create_variable_overrides.return_value
            for name, payload in job["graph_variable_overrides"].items():
                expected = payload["serialized_value"]
                if name == "OutputDirectory":
                    expected = f'(Path="{job["worker_output_directory"]}")'
                container.set_value_serialized_string.assert_any_call(variables[name], expected)
                container.set_variable_assignment_enable_state.assert_any_call(variables[name], True)

    def test_runtime_collects_both_linear_exr_and_display_mp4_layers(self):
        exr, mp4 = str(self.root / "beauty_v003.0001.exr"), str(self.root / "beauty_v003.mp4")
        results = types.SimpleNamespace(graph_data=[types.SimpleNamespace(render_layer_data={
            "beauty_linear": types.SimpleNamespace(file_paths=[exr]),
            "beauty_srgb": types.SimpleNamespace(file_paths=[mp4]),
        })])
        with patch.dict(sys.modules, {"unreal": types.ModuleType("unreal")}):
            runtime = _load_runtime_helpers()
            self.assertEqual(runtime["_collect_output_files"](results), [exr, mp4])

    def test_previous_version_outputs_cannot_complete_the_next_version(self):
        previous, following = _job(2), _job(3)
        for job in (previous, following):
            prepare_worker_output_mapping(job, self.farm_root)

        def create_outputs(job):
            output = Path(job["worker_output_directory"])
            exr = output / (
                job["output_file_name_format"].replace("{frame_number}", "0001") + ".exr"
            )
            exr.parent.mkdir(parents=True)
            exr.write_bytes(b"EXR")
            mp4 = output / (job["mp4_file_name_format"] + ".mp4")
            mp4.write_bytes(b"MP4")
            return [str(exr), str(mp4)]

        previous_files = create_outputs(previous)
        with patch.dict(sys.modules, {"unreal": types.ModuleType("unreal")}):
            validate = _load_runtime_helpers()["_validate_render_outputs"]
            _, result = validate(following, previous_files)
            self.assertFalse(result["success"])
            self.assertFalse(result["mp4_exists"])
            self.assertEqual(result["exr_file_count"], 0)

            following_files = create_outputs(following)
            validated, result = validate(following, following_files)
            self.assertTrue(result["success"])
            self.assertEqual(set(validated), set(following_files))


if __name__ == "__main__":
    unittest.main()
