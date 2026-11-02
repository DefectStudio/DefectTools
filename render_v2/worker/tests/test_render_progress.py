from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from portable_pipe_tools.render_farm.render_progress import RenderProgressMonitor
from portable_pipe_tools.render_farm.unreal_runner import (
    _stop_unreal_process, _wait_for_unreal_process, _progress_output_paths,
    UnrealProcessTerminationError,
)


class RenderProgressTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.folder = Path(directory.name)
        self.now = 0.0
        self.job = {"job_id": "SHOT-v1", "attempt": 2}
        self.monitor = RenderProgressMonitor(self.folder, self.job, monotonic=lambda: self.now)

    def report(self, **values):
        payload = dict(schema_version=1, job_id="SHOT-v1", attempt=2, progress=0.0,
                       phase="rendering", current_frame=0, total_frames=100,
                       segment_index=0, output_frame_index=0, output_sub_sample_index=0,
                       engine_warm_up_frame_index=0)
        payload.update(values)
        self.monitor.path.write_text(json.dumps(payload), encoding="utf-8")
        return self.monitor.poll()

    def test_advancing_render_can_run_far_longer_than_two_hours(self):
        for frame in range(50):
            self.now = frame * 590.0
            snapshot = self.report(current_frame=frame, output_frame_index=frame, progress=float(frame))
            self.assertIsNone(self.monitor.stalled_reason())
        self.assertGreater(snapshot["elapsed_seconds"], 7 * 3600)

    def test_heartbeats_and_rewritten_timestamps_do_not_hide_a_stall(self):
        self.report(current_frame=12, progress=12)
        for seconds in (60, 120, 300, 600):
            self.now = seconds
            self.report(current_frame=12, progress=12, updated_utc=str(seconds))
        self.assertIn("during rendering", self.monitor.stalled_reason())
        self.assertEqual(600, self.monitor.snapshot()["last_progress_age_seconds"])

    def test_subsamples_and_warmup_keep_a_slow_frame_alive(self):
        self.report(phase="warmup")
        self.now = 590
        self.report(phase="warmup", engine_warm_up_frame_index=5)
        self.now = 1180
        self.report(phase="rendering", output_sub_sample_index=1)
        self.now = 1770
        self.report(phase="rendering", output_sub_sample_index=2)
        self.assertIsNone(self.monitor.stalled_reason())
        self.assertEqual(0, self.monitor.snapshot()["current_frame"])

    def test_wrong_attempt_partial_receipts_and_nonfinite_values_are_ignored(self):
        for value in ({"attempt": 1}, {"job_id": "OTHER"}, {"progress": float("nan")},
                      {"current_frame": True}, {"progress": 101}, {"progress": 10**400},
                      {"schema_version": True}):
            self.report(**value)
            self.assertEqual("startup", self.monitor.snapshot()["phase"])
        self.monitor.path.write_text('{"job_id":', encoding="utf-8")
        self.now = 1801
        self.monitor.poll()
        self.assertIn("during startup", self.monitor.stalled_reason())

    def test_startup_has_separate_allowance(self):
        self.now = 601
        self.monitor.poll()
        self.assertIsNone(self.monitor.stalled_reason())
        self.now = 1800
        self.assertIn("during startup", self.monitor.stalled_reason())

    def test_regressions_and_alternating_old_phases_do_not_reset_deadline(self):
        self.report(phase="warmup", engine_warm_up_frame_index=1)
        self.now = 10
        self.report(current_frame=5, output_frame_index=5)
        for seconds in (100, 200, 300, 400, 610):
            self.now = seconds
            self.report(phase="warmup" if seconds % 200 else "rendering",
                        current_frame=2, output_frame_index=2)
        self.assertIsNotNone(self.monitor.stalled_reason())

    def test_finalization_allows_output_growth_but_not_mtime_changes(self):
        output = self.folder / "movie.mp4"
        output.write_bytes(b"baseline")
        self.monitor = RenderProgressMonitor(self.folder, self.job, output_paths=[output],
                                             monotonic=lambda: self.now)
        self.report(phase="finalizing")
        self.now = 1790
        output.write_bytes(b"baseline-growing")
        self.monitor.poll()
        self.now = 1801
        self.monitor.poll()
        self.assertIsNone(self.monitor.stalled_reason())
        self.now = 3590
        output.touch()
        self.monitor.poll()
        self.assertIn("during finalizing", self.monitor.stalled_reason())

    def test_stale_render_receipt_cannot_restart_finalization(self):
        self.report(phase="finalizing", current_frame=100, progress=100)
        self.now = 500
        self.report(phase="rendering", current_frame=101, progress=100)
        self.assertEqual("finalizing", self.monitor.snapshot()["phase"])
        self.assertEqual(500, self.monitor.snapshot()["last_progress_age_seconds"])

    def test_old_startup_receipt_cannot_abort_a_long_healthy_render(self):
        self.report(current_frame=1, progress=1)
        self.now = 3600
        self.report(current_frame=50, output_frame_index=50, progress=50)
        self.now = 3601
        self.report(phase="startup")
        self.assertEqual("rendering", self.monitor.snapshot()["phase"])
        self.assertEqual(50, self.monitor.snapshot()["current_frame"])
        self.assertIsNone(self.monitor.stalled_reason())

    def test_watchdog_stops_owned_process_after_no_progress(self):
        self.report(current_frame=20, progress=20)
        self.now = 601
        process = Mock(returncode=-15)
        process.wait.return_value = -15
        updates = []
        code, reason = _wait_for_unreal_process(process, None, progress_monitor=self.monitor,
                                               progress_callback=updates.append)
        self.assertEqual((-15, "stalled"), (code, reason))
        process.terminate.assert_called_once_with()
        self.assertEqual(20, updates[-1]["current_frame"])

    def test_unconfirmed_process_stop_cannot_be_treated_as_an_exit(self):
        process = Mock(pid=123)
        process.wait.side_effect = subprocess.TimeoutExpired("Unreal", 30)
        process.poll.return_value = None
        with self.assertRaises(UnrealProcessTerminationError):
            _stop_unreal_process(process)
        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()

    def test_watchdog_confirms_exit_of_a_real_owned_child_process(self):
        self.report(current_frame=2, progress=2)
        self.now = 601
        process = subprocess.Popen(
            [sys.executable, "-B", "-c", "import time; time.sleep(30)"],
            cwd=self.folder, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            code, reason = _wait_for_unreal_process(process, None, progress_monitor=self.monitor)
            self.assertEqual("stalled", reason)
            self.assertIsNotNone(code)
            self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)

    def test_total_deadline_can_be_disabled_for_long_jobs(self):
        process = Mock()
        process.wait.side_effect = [subprocess.TimeoutExpired("Unreal", 0.5), 0]
        code, reason = _wait_for_unreal_process(process, None)
        self.assertEqual((0, None), (code, reason))
        process.terminate.assert_not_called()

    def test_disabled_output_formats_are_not_resolved_or_monitored(self):
        job = dict(outputs={"mp4": True, "exr": False}, mp4_file_name_format="movie",
                   output_file_name_format="../DISABLED/{frame_number}")
        self.assertEqual([self.folder / "movie.mp4"], _progress_output_paths(job, self.folder))
        job.update(outputs={"mp4": False, "exr": False}, mp4_file_name_format="../DISABLED")
        self.assertEqual([], _progress_output_paths(job, self.folder))


if __name__ == "__main__":
    unittest.main()
