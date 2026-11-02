"""Verify real executor progress code with Unreal's public graph API mocked."""

import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from portable_pipe_tools.render_farm.render_progress import validate_progress


RUNTIME_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "unreal/RenderWorkerRuntime/Content/Python/render_worker_runtime_executor.py"
)


class FakeHostExecutor:
    def on_begin_frame(self):
        self.super_tick_count += 1

    def on_executor_finished_impl(self):
        self.finished = True


class RuntimeProgressTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.warnings = []
        self.unreal = types.ModuleType("unreal")
        self.unreal.log = Mock()
        self.unreal.log_warning = self.warnings.append
        self.unreal.log_error = Mock()
        self.unreal.uclass = lambda **kwargs: lambda cls: cls
        self.unreal.ufunction = lambda **kwargs: lambda function: function
        self.unreal.uproperty = lambda value: None
        self.unreal.MoviePipelinePythonHostExecutor = FakeHostExecutor
        self.unreal.MoviePipelineBase = object
        self.unreal.MoviePipelineQueue = object
        self.unreal.MoviePipelineOutputData = object
        self.enterContext(patch.dict(sys.modules, {"unreal": self.unreal}))
        self.runtime = {"__file__": str(RUNTIME_SOURCE)}
        exec(compile(RUNTIME_SOURCE.read_text(encoding="utf-8"), str(RUNTIME_SOURCE), "exec"), self.runtime)
        self.clock = self.enterContext(patch.object(self.runtime["time"], "monotonic", return_value=100.0))
        self.executor = self.runtime["RenderWorkerV2Executor"]()
        self.executor._post_init()
        self.executor.super_tick_count = 0
        self.executor.job_json_path = str(self.root / "job.json")
        self.executor.job_identifier = "job-progress"
        self.executor._configure_progress({"attempt": 3, "frame_count": 120})
        self.path = self.root / "unreal_progress.json"
        self.library = types.SimpleNamespace(
            get_pipeline_state=Mock(return_value="MovieRenderPipelineState.PRODUCING_FRAMES"),
            get_current_segment_state=Mock(return_value="MovieRenderShotState.RENDERING"),
            get_overall_output_frames=Mock(return_value=(43, 120)),
            get_overall_segment_counts=Mock(return_value=(0, 1)),
            get_current_segment_work_metrics=Mock(return_value=types.SimpleNamespace(
                output_frame_index=43, output_sub_sample_index=2, engine_warm_up_frame_index=5
            )),
            get_root_frame_number=Mock(return_value=types.SimpleNamespace(value=1043)),
        )
        self.unreal.MovieGraphLibrary = self.library
        self.executor.active_pipeline = types.SimpleNamespace(
            get_time_step_instance=Mock(return_value=object())
        )

    def snapshot(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def tick(self, now):
        self.clock.return_value = now
        self.executor.on_begin_frame()

    def test_startup_identifies_attempt_without_calling_pipeline_api(self):
        snapshot = self.snapshot()
        self.assertEqual(1, snapshot["schema_version"])
        self.assertEqual("job-progress", snapshot["job_id"])
        self.assertEqual(3, snapshot["attempt"])
        self.assertEqual("startup", snapshot["phase"])
        self.assertEqual((0, 120, 0.0), (snapshot["current_frame"], snapshot["total_frames"], snapshot["progress"]))
        self.assertTrue(all(snapshot[field] == 0 for field in (
            "output_frame_index", "output_sub_sample_index", "engine_warm_up_frame_index"
        )))
        self.assertIn("updated_utc", snapshot)

    def test_tick_reports_ordinal_separately_from_sequence_frame_and_scales_percent(self):
        self.tick(101.0)
        snapshot = self.snapshot()
        self.assertEqual(1, self.executor.super_tick_count)
        self.assertEqual("rendering", snapshot["phase"])
        self.assertEqual(43, snapshot["current_frame"])
        self.assertEqual(1043, snapshot["sequence_frame"])
        self.assertAlmostEqual(100 * 43 / 120, snapshot["progress"])
        self.assertEqual((43, 2, 5), tuple(snapshot[field] for field in (
            "output_frame_index", "output_sub_sample_index", "engine_warm_up_frame_index"
        )))

    def test_normal_ticks_are_throttled_and_unchanged_ticks_do_not_rewrite(self):
        write = self.runtime["_write_progress_atomic"]
        with patch.dict(self.runtime, {"_write_progress_atomic": Mock(wraps=write)}):
            self.tick(100.2)
            self.assertEqual("startup", self.snapshot()["phase"])
            self.tick(101.0)
            first = self.path.read_bytes()
            self.tick(102.5)
            self.assertEqual(first, self.path.read_bytes())
            self.runtime["_write_progress_atomic"].assert_called_once()
            self.library.get_overall_output_frames.return_value = (44, 120)
            self.tick(102.6)
            self.assertEqual(44, self.snapshot()["current_frame"])

    def test_warmup_advancement_is_reported_before_output_frames(self):
        self.library.get_current_segment_state.return_value = "MovieRenderShotState.WARMING_UP"
        self.library.get_overall_output_frames.return_value = (0, 120)
        self.tick(101.0)
        self.assertEqual("warmup", self.snapshot()["phase"])
        self.assertEqual(5, self.snapshot()["engine_warm_up_frame_index"])
        self.library.get_current_segment_work_metrics.return_value.engine_warm_up_frame_index = 6
        self.tick(102.0)
        self.assertEqual(6, self.snapshot()["engine_warm_up_frame_index"])

    def test_subsample_advancement_is_not_lost_when_output_frame_is_unchanged(self):
        self.tick(101.0)
        self.library.get_current_segment_work_metrics.return_value.output_sub_sample_index = 3
        self.tick(102.0)
        self.assertEqual(43, self.snapshot()["current_frame"])
        self.assertEqual(3, self.snapshot()["output_sub_sample_index"])

    def test_unavailable_or_negative_work_metrics_normalize_to_zero(self):
        self.library.get_current_segment_work_metrics.return_value = types.SimpleNamespace(
            output_frame_index=-1, output_sub_sample_index=None
        )
        self.tick(101.0)
        self.assertEqual([0, 0, 0], [self.snapshot()[field] for field in (
            "output_frame_index", "output_sub_sample_index", "engine_warm_up_frame_index"
        )])

    def test_actual_runtime_receipts_satisfy_worker_reader_contract(self):
        job = {"job_id": "job-progress", "attempt": 3}
        self.assertIsNotNone(validate_progress(self.snapshot(), job))
        self.library.get_current_segment_state.return_value = "MovieRenderShotState.WARMING_UP"
        self.library.get_current_segment_work_metrics.return_value = types.SimpleNamespace(
            output_frame_index=-1, output_sub_sample_index=-1, engine_warm_up_frame_index=3
        )
        self.tick(101.0)
        self.assertIsNotNone(validate_progress(self.snapshot(), job))
        self.library.get_current_segment_state.return_value = "MovieRenderShotState.RENDERING"
        self.tick(102.0)
        self.assertIsNotNone(validate_progress(self.snapshot(), job))
        self.executor._publish_progress("finalizing", force=True)
        self.assertIsNotNone(validate_progress(self.snapshot(), job))
        self.executor._publish_progress("complete", force=True)
        self.assertIsNotNone(validate_progress(self.snapshot(), job))

    def test_finalization_avoids_native_getters_that_require_a_live_timestep(self):
        self.tick(101.0)
        self.library.get_pipeline_state.return_value = "MovieRenderPipelineState.FINALIZE"
        self.library.get_root_frame_number.side_effect = AssertionError("Timestep was destroyed")
        self.tick(102.0)
        self.assertEqual("finalizing", self.snapshot()["phase"])
        self.assertEqual(1, self.library.get_root_frame_number.call_count)

    def test_first_producing_tick_waits_for_timestep_before_native_getters(self):
        self.executor.active_pipeline.get_time_step_instance.return_value = None
        self.tick(101.0)
        self.assertEqual("startup", self.snapshot()["phase"])
        self.library.get_overall_output_frames.assert_not_called()
        self.library.get_root_frame_number.assert_not_called()

    def test_legacy_python_library_alias_is_supported(self):
        del self.unreal.MovieGraphLibrary
        self.unreal.MovieGraphBlueprintLibrary = self.library
        self.tick(101.0)
        self.assertEqual(43, self.snapshot()["current_frame"])

    def test_write_failure_warns_once_does_not_abort_render_and_retries_are_throttled(self):
        write = Mock(side_effect=PermissionError("locked"))
        with patch.dict(self.runtime, {"_write_progress_atomic": write}):
            self.tick(101.0)
            self.tick(101.5)
            self.tick(102.0)
        self.assertEqual(2, write.call_count)
        self.assertEqual(1, len(self.warnings))
        self.assertEqual(3, self.executor.super_tick_count)
        self.assertEqual("startup", self.snapshot()["phase"])

    def test_completion_becomes_one_hundred_only_after_result_writes_and_validation_passes(self):
        self.tick(101.0)
        observations = []
        self.executor._write_result = Mock(side_effect=lambda **kwargs: observations.append(self.snapshot()["phase"]))
        with patch.dict(self.runtime, {
            "_read_json_object": Mock(return_value={}),
            "_collect_output_files": Mock(return_value=[]),
            "_validate_render_outputs": Mock(return_value=([], {"success": True})),
        }):
            self.executor.on_movie_pipeline_finished(types.SimpleNamespace(success=True))
        self.assertEqual(["finalizing"], observations)
        self.assertEqual("complete", self.snapshot()["phase"])
        self.assertEqual((120, 100.0), (self.snapshot()["current_frame"], self.snapshot()["progress"]))
        self.assertTrue(self.executor.finished)

    def test_failed_output_validation_does_not_publish_complete(self):
        self.executor._write_result = Mock()
        with patch.dict(self.runtime, {
            "_read_json_object": Mock(return_value={}),
            "_collect_output_files": Mock(return_value=[]),
            "_validate_render_outputs": Mock(return_value=([], {"success": False, "errors": ["missing frame"]})),
        }):
            self.executor.on_movie_pipeline_finished(types.SimpleNamespace(success=True))
        self.assertEqual("finalizing", self.snapshot()["phase"])
        self.assertFalse(self.executor._write_result.call_args.kwargs["success"])

    def test_atomic_publish_removes_temporary_file_on_replace_failure(self):
        with patch.object(self.runtime["os"], "replace", side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                self.runtime["_write_progress_atomic"](str(self.path), {"current_frame": 44})
        self.assertEqual("startup", self.snapshot()["phase"])
        self.assertEqual([], list(self.root.glob(".*.tmp")))


if __name__ == "__main__":
    unittest.main()
