from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.queue import JOB_FILENAME
from portable_pipe_tools.render_farm.unreal_runner import (
    COMMAND_LINE_PIPELINE_CLASS,
    HOST_EXECUTOR_CLASS,
    PYTHON_EXECUTOR_CLASS,
    _interpret_unreal_result,
    build_unreal_command,
    resolve_unreal_project,
    resolve_unreal_editor_cmd,
)


class UnrealRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.uproject = self.root / "s3bishop.uproject"
        self.uproject.write_text(
            json.dumps({"EngineAssociation": "5.8"}),
            encoding="utf-8",
        )
        self.executable = self.root / "UnrealEditor-Cmd.exe"
        self.executable.write_bytes(b"test")
        self.claimed_folder = self.root / "claimed"
        self.claimed_folder.mkdir()
        (self.claimed_folder / JOB_FILENAME).write_text("{}", encoding="utf-8")
        self.job = {
            "job_type": "unreal_movie_render_graph",
            "job_id": "BSH_000_0020_v011_test",
            "status": "rendering",
            "test_job": False,
            "uproject": str(self.uproject),
            "engine_version": "5.8.0",
            "level": "/Game/Maps/TestMap.TestMap",
            "sequence": "/Game/Sequences/TestSequence.TestSequence",
            "render_config": "/Game/Render/Graph.Graph",
            "output_directory": str(self.root / "output"),
            "graph_variable_overrides": {
                "MP4": {
                    "enabled": True,
                    "serialized_value": "True",
                }
            },
        }

    def test_explicit_unreal_executable_is_used(self) -> None:
        resolved = resolve_unreal_editor_cmd(self.job, self.executable)
        self.assertEqual(self.executable.resolve(), resolved.resolve())

    def test_command_contains_farm_executor_and_exact_job_path(self) -> None:
        command = build_unreal_command(
            self.claimed_folder,
            self.job,
            self.executable,
            validate_only=True,
        )

        self.assertEqual(str(self.executable.resolve()), command[0])
        self.assertIn("/Game/Maps/TestMap", command)
        self.assertIn(
            f"-MoviePipelineLocalExecutorClass={HOST_EXECUTOR_CLASS}",
            command,
        )
        self.assertIn(f"-ExecutorPythonClass={PYTHON_EXECUTOR_CLASS}", command)
        self.assertIn(
            f"-MoviePipelineClass={COMMAND_LINE_PIPELINE_CLASS}",
            command,
        )
        self.assertIn(
            f"-RenderFarmJob={self.claimed_folder / JOB_FILENAME}",
            command,
        )
        self.assertIn("-RenderFarmValidateOnly=true", command)

    def test_local_uproject_overrides_missing_submitting_computer_path(self) -> None:
        self.job["project"] = "s3bishop"
        self.job["uproject"] = str(
            self.root / "missing-main-computer" / "s3bishop.uproject"
        )
        worker_project_folder = self.root / "worker-checkout"
        worker_project_folder.mkdir()
        worker_uproject = worker_project_folder / "s3bishop.uproject"
        worker_uproject.write_text(
            json.dumps({"EngineAssociation": "5.8"}),
            encoding="utf-8",
        )

        command = build_unreal_command(
            self.claimed_folder,
            self.job,
            self.executable,
            local_uproject=worker_uproject,
        )

        self.assertEqual(str(worker_uproject.resolve()), command[1])

    def test_local_uproject_must_match_submitted_project_name(self) -> None:
        self.job["project"] = "s3bishop"
        wrong_project = self.root / "spectrum.uproject"
        wrong_project.write_text("{}", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "does not match the farm job"):
            resolve_unreal_project(self.job, wrong_project)

    def test_exit_zero_without_unreal_result_is_failure(self) -> None:
        result = _interpret_unreal_result(self.job, 0, None)
        self.assertFalse(result.success)
        self.assertIn("did not write unreal_result.json", result.reason)

    def test_unreal_success_result_is_accepted(self) -> None:
        result = _interpret_unreal_result(
            self.job,
            0,
            {
                "job_id": self.job["job_id"],
                "success": True,
                "output_file_count": 100,
            },
        )
        self.assertTrue(result.success)
        self.assertIn("100 output file", result.reason)


if __name__ == "__main__":
    unittest.main()
