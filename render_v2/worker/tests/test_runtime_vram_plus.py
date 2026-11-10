"""Exercise the shipped runtime's adapter gate before Movie Graph setup."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import Mock, patch


RUNTIME_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "unreal/RenderWorkerRuntime/Content/Python/render_worker_runtime_executor.py"
)


def startup_log(
    chosen_index=1, chosen_name="NVIDIA GeForce RTX 4000", chosen_vram=20480,
):
    return (
        "Log file open, 11/09/26 18:04:37\n"
        "[2026.11.10-02.04.39:477][  0]LogD3D12RHI: Found D3D12 adapter 0: "
        "NVIDIA GeForce RTX 5090 (VendorId: 10de, DeviceId: 2b85\n"
        "LogD3D12RHI:   Adapter has 32187MB of dedicated video memory, "
        "0MB of dedicated system memory, and 64194MB of shared system memory\n"
        f"LogD3D12RHI: Found D3D12 adapter 1: {chosen_name} (VendorId: 10de, DeviceId: 2790\n"
        "LogD3D12RHI:   Max supported Feature Level SM6, shader model 6.9\n"
        f"LogD3D12RHI:   Adapter has {chosen_vram}MB of dedicated video memory, "
        "0MB of dedicated system memory, and 64194MB of shared system memory\n"
        f"LogD3D12RHI: Chosen D3D12 Adapter Id = {chosen_index}\n"
        "LogD3D12RHI: Display: Creating D3D12 RHI with Max Feature Level SM6\n"
    )


class RuntimeVRAMPlusTests(unittest.TestCase):
    def setUp(self):
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.job_path = folder / "job.json"
        self.log_path = folder / "unreal.log"
        self.result_path = folder / "unreal_result.json"
        self.parameters = {
            "renderfarmjob": str(self.job_path),
            "abslog": str(self.log_path),
            "graphicsadapter": "1",
            "gpupreference": "0",
            "renderfarmvalidateonly": "true",
        }
        self.job = {
            "schema_version": 1,
            "job_type": "unreal_movie_render_graph",
            "status": "rendering",
            "job_id": "test-job",
            "level": "/Game/Map.Map",
            "sequence": "/Game/Sequence.Sequence",
            "render_config": "/Game/Graph.Graph",
            "graph_variable_overrides": {},
            "requires_vram_plus": True,
            "worker_render_adapter": {
                "index": 1,
                "model": "RTX 4000",
                "dxgi_name": " NVIDIA  GeForce RTX 4000 ",
                "vram_mib": 20480,
            },
        }
        self.unreal = ModuleType("unreal")
        self.unreal.MoviePipelinePythonHostExecutor = object
        self.unreal.MoviePipelineBase = object
        self.unreal.MoviePipelineQueue = object
        self.unreal.MoviePipelineOutputData = object
        self.unreal.uclass = lambda: lambda cls: cls
        self.unreal.ufunction = lambda **_: lambda function: function
        self.unreal.uproperty = lambda _: None
        self.unreal.log = self._append_to_unreal_log
        self.unreal.log_warning = Mock()
        self.unreal.log_error = Mock()
        spec = importlib.util.spec_from_file_location("runtime_adapter_test", RUNTIME_SOURCE)
        self.runtime = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"unreal": self.unreal}):
            spec.loader.exec_module(self.runtime)
        self.runtime.VRAM_LOG_MARKER_WAIT_SECONDS = 0
        self.runtime._command_line_parameters = lambda: self.parameters
        self.build_job = Mock()
        self.runtime._build_pipeline_job = self.build_job
        self.log_path.write_text(startup_log(), encoding="utf-8")

    def _append_to_unreal_log(self, message):
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"LogPython: {message}\n")

    def _run_executor(self):
        self.job_path.write_text(json.dumps(self.job), encoding="utf-8")
        executor = self.runtime.RenderWorkerV2Executor()
        executor._post_init()
        executor.on_executor_finished_impl = Mock()
        executor.execute_delayed(None)
        executor.on_executor_finished_impl.assert_called_once()
        return json.loads(self.result_path.read_text(encoding="utf-8"))

    def _assert_setup_blocked(self):
        result = self._run_executor()
        self.assertFalse(result["success"])
        self.assertEqual(result["stage"], "setup")
        self.assertIn("VRAM+", result["reason"])
        self.build_job.assert_not_called()

    def test_inclusive_threshold_allows_verified_selected_adapter(self):
        result = self._run_executor()
        self.assertTrue(result["success"])
        self.assertEqual(result["stage"], "validation")
        self.build_job.assert_called_once()

    def test_blocks_wrong_ordinal_model_or_memory(self):
        for log in (
            startup_log(chosen_index=0),
            startup_log(chosen_name="Other GPU"),
            startup_log(chosen_vram=20479),
            startup_log(chosen_vram=20481),
        ):
            with self.subTest(log=log):
                self.log_path.write_text(log, encoding="utf-8")
                self._assert_setup_blocked()

    def test_blocks_missing_d3d12_creation(self):
        log, _ = startup_log().split("LogD3D12RHI: Display: Creating")
        self.log_path.write_text(log, encoding="utf-8")
        self._assert_setup_blocked()

    def test_blocks_stale_or_diverted_unreal_log(self):
        self.runtime.unreal.log = Mock()
        self._assert_setup_blocked()

    def test_blocks_missing_unreal_log(self):
        self.log_path.unlink()
        self.runtime.unreal.log = Mock()
        self._assert_setup_blocked()

    def test_blocks_old_selection_from_an_earlier_log_session(self):
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write("Log file open, 11/09/26 19:10:11\n")
        self._assert_setup_blocked()

    def test_blocks_command_line_adapter_mismatch(self):
        self.parameters["graphicsadapter"] = "0"
        self._assert_setup_blocked()

    def test_blocks_command_line_log_mismatch(self):
        self.parameters["abslog"] = str(self.log_path.with_name("other.log"))
        self._assert_setup_blocked()

    def test_blocks_missing_worker_binding(self):
        self.job.pop("worker_render_adapter")
        self._assert_setup_blocked()

    def test_unrestricted_job_needs_no_adapter_or_launch_switches(self):
        self.job.pop("requires_vram_plus")
        self.job.pop("worker_render_adapter")
        self.parameters.pop("abslog")
        self.parameters.pop("graphicsadapter")
        self.parameters.pop("gpupreference")
        self.log_path.unlink()
        self.runtime.unreal.log = Mock()
        self.assertTrue(self._run_executor()["success"])
        self.build_job.assert_called_once()
