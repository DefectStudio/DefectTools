from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, call, patch

from portable_pipe_tools.auto_comp_natron.create_comp import get_comp_path
from portable_pipe_tools.auto_comp_natron.open_comp import (
    CompNotFoundError,
    NATRON_PLUGIN_PATH_ENV,
)
from portable_pipe_tools.auto_comp_natron.render_comp import (
    CompRenderFailedError,
    RENDER_STATUS_ENV,
    RenderCompResult,
    SmartWriteNotFoundError,
    get_natron_renderer_executable,
    get_smart_write_render_script_path,
    pause_render_comp,
    poll_render_comp,
    read_render_comp_progress,
    render_comp,
    resume_render_comp,
    terminate_render_comp,
)
from portable_pipe_tools.auto_comp_natron.source_media import (
    SourceHydrationResult,
)


def _write_comp(comp_path: Path, *, smart_write: bool = True) -> None:
    plugin = (
        "<Plugin_id>com.portablepipetools.SmartWrite</Plugin_id>"
        if smart_write
        else "<Plugin_id>net.sf.openfx.GradePlugin</Plugin_id>"
    )
    comp_path.parent.mkdir(parents=True)
    comp_path.write_text(f"<Project>{plugin}</Project>", encoding="utf-8")


class RenderCompTests(unittest.TestCase):
    def test_natron_renderer_is_derived_from_configured_gui_executable(self) -> None:
        self.assertEqual(
            Path("D:/Apps/Natron/bin/NatronRenderer.exe"),
            get_natron_renderer_executable("D:/Apps/Natron/bin/Natron.exe"),
        )
        self.assertEqual(
            Path("D:/Apps/Natron/bin/NatronRenderer.exe"),
            get_natron_renderer_executable(
                "D:/Apps/Natron/bin/NatronRenderer.exe"
            ),
        )

    @patch(
        "portable_pipe_tools.auto_comp_natron.render_comp.render_comp."
        "hydrate_latest_source_sequence"
    )
    @patch(
        "portable_pipe_tools.auto_comp_natron.render_comp.render_comp."
        "subprocess.Popen"
    )
    def test_render_comp_launches_python_script_without_project_auto_render(
        self,
        popen: Mock,
        hydrate: Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            show_root = temporary_path / "show"
            comp_path = get_comp_path(show_root, "BSH", "BSH_000_0010")
            _write_comp(comp_path)
            status_path = temporary_path / "render_status.json"
            log_path = temporary_path / "render.log"
            process = Mock()
            process.pid = 1234
            popen.return_value = process
            hydrate.return_value = SourceHydrationResult(None, 12, 4)
            diagnostic_messages: list[str] = []

            with (
                patch(
                    "portable_pipe_tools.auto_comp_natron.render_comp."
                    "render_comp._new_status_path",
                    return_value=status_path,
                ),
                patch(
                    "portable_pipe_tools.auto_comp_natron.render_comp."
                    "render_comp._new_log_path",
                    return_value=log_path,
                ),
            ):
                result = render_comp(
                    show_root,
                    "BSH",
                    "BSH_000_0010",
                    natron_executable=temporary_path / "Natron.exe",
                    diagnostic_log=diagnostic_messages.append,
                    output_log_path=log_path,
                )

            command = popen.call_args.args[0]
            options = popen.call_args.kwargs
            self.assertEqual(
                str(temporary_path / "NatronRenderer.exe"),
                command[0],
            )
            self.assertEqual("--cmd", command[1])
            self.assertIn("app.loadProject", command[2])
            self.assertEqual(str(get_smart_write_render_script_path()), command[3])
            self.assertNotIn("--onload", command)
            self.assertEqual(
                str(comp_path),
                options["env"]["PORTABLE_PIPE_SMART_WRITE_PROJECT"],
            )
            self.assertEqual(str(status_path), options["env"][RENDER_STATUS_ENV])
            self.assertEqual(subprocess.STDOUT, options["stderr"])
            self.assertEqual(str(log_path), options["stdout"].name)
            self.assertIn(
                str(get_smart_write_render_script_path().parent),
                options["env"][NATRON_PLUGIN_PATH_ENV].split(os.pathsep),
            )
            self.assertEqual(4, result.hydrated_source_files)
            self.assertIs(process, result.process)
            self.assertEqual(log_path, result.log_path)
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("Starting render", log_text)
            self.assertIn("NatronRenderer PID: 1234", log_text)
            diagnostic_text = "\n".join(diagnostic_messages)
            self.assertIn("SmartWrite inspection passed", diagnostic_text)
            self.assertIn("Natron output log", diagnostic_text)
            self.assertIn("NatronRenderer PID is 1234", diagnostic_text)

    def test_missing_comp_fails_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(CompNotFoundError):
                render_comp(
                    Path(temporary_directory) / "show",
                    "BSH",
                    "BSH_000_0010",
                )

    @patch(
        "portable_pipe_tools.auto_comp_natron.render_comp.render_comp."
        "subprocess.Popen"
    )
    def test_comp_without_smart_write_fails_before_launch(self, popen: Mock) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            comp_path = get_comp_path(show_root, "BSH", "BSH_000_0010")
            _write_comp(comp_path, smart_write=False)

            with self.assertRaises(SmartWriteNotFoundError):
                render_comp(show_root, "BSH", "BSH_000_0010")

            popen.assert_not_called()

    def test_poll_returns_none_while_render_is_running(self) -> None:
        process = Mock()
        process.poll.return_value = None
        result = RenderCompResult(
            comp_path=Path("comp.ntp"),
            process=process,
            status_path=Path("unused.json"),
        )

        self.assertIsNone(poll_render_comp(result))

    def test_terminate_render_comp_stops_a_running_renderer(self) -> None:
        process = Mock()
        process.poll.return_value = None
        result = RenderCompResult(
            comp_path=Path("comp.ntp"),
            process=process,
            status_path=Path("unused.json"),
        )

        self.assertTrue(terminate_render_comp(result))

        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=2.0)
        process.kill.assert_not_called()

    @patch(
        "portable_pipe_tools.auto_comp_natron.render_comp.render_comp."
        "_set_process_suspended"
    )
    def test_pause_and_resume_suspend_the_active_renderer_once(
        self,
        set_process_suspended: Mock,
    ) -> None:
        process = Mock()
        process.pid = 4321
        process.poll.return_value = None
        result = RenderCompResult(
            comp_path=Path("comp.ntp"),
            process=process,
            status_path=Path("unused.json"),
        )

        self.assertTrue(pause_render_comp(result))
        self.assertFalse(pause_render_comp(result))
        self.assertTrue(resume_render_comp(result))
        self.assertFalse(resume_render_comp(result))

        self.assertEqual(
            [call(4321, True), call(4321, False)],
            set_process_suspended.call_args_list,
        )

    @patch(
        "portable_pipe_tools.auto_comp_natron.render_comp.render_comp."
        "_set_process_suspended"
    )
    def test_terminate_resumes_a_paused_renderer_before_stopping_it(
        self,
        set_process_suspended: Mock,
    ) -> None:
        process = Mock()
        process.pid = 4321
        process.poll.return_value = None
        result = RenderCompResult(
            comp_path=Path("comp.ntp"),
            process=process,
            status_path=Path("unused.json"),
        )
        result._paused = True

        self.assertTrue(terminate_render_comp(result))

        set_process_suspended.assert_called_once_with(4321, False)
        process.terminate.assert_called_once_with()
        self.assertFalse(result._paused)

    def test_terminate_render_comp_kills_a_renderer_that_will_not_stop(self) -> None:
        process = Mock()
        process.poll.return_value = None
        process.wait.side_effect = [
            subprocess.TimeoutExpired("NatronRenderer", 2.0),
            0,
        ]
        result = RenderCompResult(
            comp_path=Path("comp.ntp"),
            process=process,
            status_path=Path("unused.json"),
        )

        self.assertTrue(terminate_render_comp(result))

        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()
        self.assertEqual(2, process.wait.call_count)

    def test_reads_live_frame_progress_while_render_is_running(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            status_path = Path(temporary_directory) / "status.json"
            status_path.write_text(
                json.dumps(
                    {
                        "state": "rendering",
                        "completed_frames": 37,
                        "total_frames": 100,
                        "percent": 37,
                        "current_frame": 1037,
                    }
                ),
                encoding="utf-8",
            )
            result = RenderCompResult(
                comp_path=Path("comp.ntp"),
                process=Mock(),
                status_path=status_path,
            )

            progress = read_render_comp_progress(result)

            self.assertIsNotNone(progress)
            self.assertEqual(37, progress.completed_frames)
            self.assertEqual(100, progress.total_frames)
            self.assertEqual(37.0, progress.percent)
            self.assertEqual(1037, progress.current_frame)

    def test_live_progress_prefers_rendered_files_over_unreliable_callbacks(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            status_path = output_directory / "status.json"
            frame_pattern = output_directory / "shot.####.exr"
            for frame in (1001, 1002):
                (output_directory / f"shot.{frame}.exr").write_bytes(b"frame")
            status_path.write_text(
                json.dumps(
                    {
                        "state": "rendering",
                        "completed_frames": 0,
                        "total_frames": 3,
                        "current_frame": None,
                        "outputs": {
                            "SmartWrite.EXRWrite": {
                                "completed": 3,
                                "total": 3,
                                "filename": str(frame_pattern),
                                "first_frame": 1001,
                                "last_frame": 1003,
                                "frame_increment": 1,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = RenderCompResult(
                comp_path=Path("comp.ntp"),
                process=Mock(),
                status_path=status_path,
            )

            progress = read_render_comp_progress(result)

            self.assertIsNotNone(progress)
            self.assertEqual(2, progress.completed_frames)
            self.assertEqual(3, progress.total_frames)
            self.assertAlmostEqual(66.67, progress.percent, places=2)
            self.assertEqual(1002, progress.current_frame)

    def test_live_progress_never_moves_backwards_when_filesystem_observation_drops(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            status_path = output_directory / "status.json"
            frame_pattern = output_directory / "shot.####.exr"
            first_frame = output_directory / "shot.1001.exr"
            second_frame = output_directory / "shot.1002.exr"
            first_frame.write_bytes(b"frame")
            second_frame.write_bytes(b"frame")
            status_path.write_text(
                json.dumps(
                    {
                        "state": "rendering",
                        "outputs": {
                            "SmartWrite.EXRWrite": {
                                "completed": 0,
                                "total": 3,
                                "filename": str(frame_pattern),
                                "first_frame": 1001,
                                "last_frame": 1003,
                                "frame_increment": 1,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = RenderCompResult(
                comp_path=Path("comp.ntp"),
                process=Mock(),
                status_path=status_path,
            )

            first_observation = read_render_comp_progress(result)
            second_frame.unlink()
            second_observation = read_render_comp_progress(result)

            self.assertIsNotNone(first_observation)
            self.assertIsNotNone(second_observation)
            self.assertEqual(2, first_observation.completed_frames)
            self.assertAlmostEqual(66.67, first_observation.percent, places=2)
            self.assertEqual(2, second_observation.completed_frames)
            self.assertAlmostEqual(66.67, second_observation.percent, places=2)

    def test_multi_output_progress_weights_every_enabled_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            status_path = output_directory / "status.json"
            frame_pattern = output_directory / "shot.####.exr"
            for frame in (1001, 1002, 1003):
                (output_directory / f"shot.{frame}.exr").write_bytes(b"frame")
            status_path.write_text(
                json.dumps(
                    {
                        "state": "rendering",
                        "outputs": {
                            "SmartWrite.EXRWrite": {
                                "completed": 3,
                                "total": 3,
                                "filename": str(frame_pattern),
                                "first_frame": 1001,
                                "last_frame": 1003,
                                "frame_increment": 1,
                            },
                            "SmartWrite.MP4Write": {
                                "completed": 0,
                                "total": 3,
                                "filename": str(output_directory / "shot.mp4"),
                                "first_frame": 1001,
                                "last_frame": 1003,
                                "frame_increment": 1,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = RenderCompResult(
                comp_path=Path("comp.ntp"),
                process=Mock(),
                status_path=status_path,
            )

            progress = read_render_comp_progress(result)

            self.assertIsNotNone(progress)
            self.assertEqual(3, progress.completed_frames)
            self.assertEqual(6, progress.total_frames)
            self.assertEqual(50.0, progress.percent)
            self.assertEqual(1, progress.completed_outputs)
            self.assertEqual(2, progress.total_outputs)
            self.assertFalse(progress.finalizing)

    def test_running_render_reserves_100_percent_for_process_completion(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            status_path = output_directory / "status.json"
            frame_path = output_directory / "shot.1001.exr"
            frame_path.write_bytes(b"frame")
            video_path = output_directory / "shot.mp4"
            video_path.write_bytes(b"video" * 300)
            status_path.write_text(
                json.dumps(
                    {
                        "state": "rendering",
                        "outputs": {
                            "SmartWrite.EXRWrite": {
                                "completed": 1,
                                "total": 1,
                                "filename": str(output_directory / "shot.####.exr"),
                                "first_frame": 1001,
                                "last_frame": 1001,
                                "frame_increment": 1,
                            },
                            "SmartWrite.MP4Write": {
                                "completed": 1,
                                "total": 1,
                                "filename": str(video_path),
                                "first_frame": 1001,
                                "last_frame": 1001,
                                "frame_increment": 1,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = RenderCompResult(
                comp_path=Path("comp.ntp"),
                process=Mock(),
                status_path=status_path,
            )

            progress = read_render_comp_progress(result)

            self.assertIsNotNone(progress)
            self.assertEqual(2, progress.completed_frames)
            self.assertEqual(2, progress.total_frames)
            self.assertEqual(99.0, progress.percent)
            self.assertEqual(2, progress.completed_outputs)
            self.assertEqual(2, progress.total_outputs)
            self.assertTrue(progress.finalizing)

    def test_live_progress_ignores_missing_partial_and_completed_statuses(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            status_path = Path(temporary_directory) / "status.json"
            result = RenderCompResult(
                comp_path=Path("comp.ntp"),
                process=Mock(),
                status_path=status_path,
            )

            self.assertIsNone(read_render_comp_progress(result))
            status_path.write_text("{", encoding="utf-8")
            self.assertIsNone(read_render_comp_progress(result))
            status_path.write_text(
                json.dumps({"state": "complete"}),
                encoding="utf-8",
            )
            self.assertIsNone(read_render_comp_progress(result))

    def test_poll_reports_completed_smart_write_render(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            status_path = Path(temporary_directory) / "status.json"
            status_path.write_text(
                json.dumps(
                    {
                        "state": "complete",
                        "rendered_smart_writes": 2,
                    }
                ),
                encoding="utf-8",
            )
            process = Mock()
            process.poll.return_value = 0
            result = RenderCompResult(
                comp_path=Path("comp.ntp"),
                process=process,
                status_path=status_path,
                hydrated_source_files=7,
            )

            completion = poll_render_comp(result)

            self.assertIsNotNone(completion)
            self.assertEqual(2, completion.rendered_smart_writes)
            self.assertEqual(7, completion.hydrated_source_files)
            self.assertFalse(status_path.exists())

    def test_poll_accepts_validated_completion_when_close_project_exits_one(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            status_path = Path(temporary_directory) / "status.json"
            log_path = Path(temporary_directory) / "render.log"
            log_path.write_text("Natron output\n", encoding="utf-8")
            status_path.write_text(
                json.dumps(
                    {
                        "state": "complete",
                        "rendered_smart_writes": 1,
                    }
                ),
                encoding="utf-8",
            )
            process = Mock()
            process.poll.return_value = 1
            result = RenderCompResult(
                comp_path=Path("comp.ntp"),
                process=process,
                status_path=status_path,
                log_path=log_path,
            )

            completion = poll_render_comp(result)

            self.assertIsNotNone(completion)
            self.assertEqual(1, completion.rendered_smart_writes)
            self.assertFalse(status_path.exists())
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("Renderer exited with code 1", log_text)
            self.assertIn('"state": "complete"', log_text)
            self.assertIn("classified as successful", log_text)

    def test_poll_stops_lingering_renderer_after_completed_status_grace(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            status_path = Path(temporary_directory) / "status.json"
            status_path.write_text(
                json.dumps(
                    {
                        "state": "complete",
                        "rendered_smart_writes": 1,
                    }
                ),
                encoding="utf-8",
            )
            completed_at = status_path.stat().st_mtime
            process = Mock()
            process.poll.return_value = None
            result = RenderCompResult(
                comp_path=Path("comp.ntp"),
                process=process,
                status_path=status_path,
            )

            self.assertIsNone(poll_render_comp(result))
            old_timestamp = completed_at - 10.0
            os.utime(status_path, (old_timestamp, old_timestamp))
            completion = poll_render_comp(result)

            self.assertIsNotNone(completion)
            self.assertEqual(1, completion.rendered_smart_writes)
            process.terminate.assert_called_once_with()
            process.wait.assert_called_once_with(timeout=2.0)
            self.assertFalse(status_path.exists())

    def test_poll_surfaces_smart_write_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            status_path = Path(temporary_directory) / "status.json"
            log_path = Path(temporary_directory) / "render.log"
            log_path.write_text("Natron output\n", encoding="utf-8")
            status_path.write_text(
                json.dumps(
                    {
                        "state": "failed",
                        "message": "No enabled SmartWrite outputs were available.",
                    }
                ),
                encoding="utf-8",
            )
            process = Mock()
            process.poll.return_value = 1
            result = RenderCompResult(
                comp_path=Path("comp.ntp"),
                process=process,
                status_path=status_path,
                log_path=log_path,
            )

            with self.assertRaises(CompRenderFailedError) as raised:
                poll_render_comp(result)

            message = str(raised.exception)
            self.assertIn("No enabled SmartWrite outputs", message)
            self.assertIn(str(log_path), message)
            self.assertIn(str(status_path), message)
            self.assertTrue(status_path.exists())
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("Renderer exited with code 1", log_text)
            self.assertIn('"state": "failed"', log_text)
            self.assertIn("Render classified as failed", log_text)


if __name__ == "__main__":
    unittest.main()
