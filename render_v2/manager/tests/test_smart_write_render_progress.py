from __future__ import annotations

import importlib.util
import io
import inspect
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


PLUGIN_PATH = (
    Path(__file__).resolve().parents[1]
    / "natron_plugins"
    / "SmartWriteRenderProgress.py"
)
STATUS_ENV = "PORTABLE_PIPE_SMART_WRITE_RENDER_STATUS"


class _FakeParam:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def set(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value


class _FakeWriter:
    def __init__(self, name: str, filename: str = "") -> None:
        self.name = name
        self.after_frame_render = _FakeParam()
        self.filename = _FakeParam(filename)

    def getFullyQualifiedName(self) -> str:
        return self.name

    def getParam(self, name: str) -> _FakeParam | None:
        if name == "afterFrameRender":
            return self.after_frame_render
        if name == "filename":
            return self.filename
        return None


def _load_progress_module():
    spec = importlib.util.spec_from_file_location(
        "SmartWriteRenderProgress_under_test",
        PLUGIN_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load SmartWriteRenderProgress")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SmartWriteRenderProgressTests(unittest.TestCase):
    def test_callback_uses_natrons_required_argument_names(self) -> None:
        progress = _load_progress_module()

        self.assertEqual(
            ["frame", "thisNode", "app"],
            list(inspect.signature(progress.afterFrameRender).parameters),
        )

    def test_verbose_log_records_configuration_and_each_completed_frame(
        self,
    ) -> None:
        progress = _load_progress_module()
        writer = _FakeWriter("SmartWrite.EXRWrite", "shot.####.exr")

        with tempfile.TemporaryDirectory() as temporary_directory:
            status_path = Path(temporary_directory) / "status.json"
            captured_output = io.StringIO()
            with (
                patch.dict(os.environ, {STATUS_ENV: str(status_path)}),
                patch.object(progress.sys, "stdout", captured_output),
            ):
                progress.configure([(writer, 1001, 1002, 1)])
                progress.WRITE_INTERVAL_SECONDS = 0
                progress.afterFrameRender(1001, writer, None)

        events = [
            json.loads(line.removeprefix("[SmartWriteRender] "))
            for line in captured_output.getvalue().splitlines()
        ]
        event_names = [event["event"] for event in events]
        self.assertIn("progress_configured", event_names)
        self.assertIn("status_written", event_names)
        frame_event = next(
            event for event in events if event["event"] == "frame_completed"
        )
        self.assertEqual("SmartWrite.EXRWrite", frame_event["writer"])
        self.assertEqual(1001, frame_event["frame"])
        self.assertEqual(1, frame_event["completed_frames"])
        self.assertEqual(2, frame_event["total_frames"])

    def test_tracks_unique_completed_writer_frames_and_reports_completion(
        self,
    ) -> None:
        progress = _load_progress_module()
        exr_writer = _FakeWriter("SmartWrite.EXRWrite")
        mp4_writer = _FakeWriter("SmartWrite.MP4Write")

        with tempfile.TemporaryDirectory() as temporary_directory:
            status_path = Path(temporary_directory) / "status.json"
            with patch.dict(os.environ, {STATUS_ENV: str(status_path)}):
                progress.configure(
                    [
                        (exr_writer, 1001, 1003, 1),
                        (mp4_writer, 1001, 1005, 2),
                    ]
                )
                progress.WRITE_INTERVAL_SECONDS = 0
                progress.afterFrameRender(1001, exr_writer, None)
                progress.afterFrameRender(1001, exr_writer, None)
                progress.afterFrameRender(1003, mp4_writer, None)

                payload = json.loads(status_path.read_text(encoding="utf-8"))
                self.assertEqual("rendering", payload["state"])
                self.assertEqual(2, payload["completed_frames"])
                self.assertEqual(6, payload["total_frames"])
                self.assertAlmostEqual(33.33, payload["percent"], places=2)
                self.assertEqual(
                    1,
                    payload["outputs"]["SmartWrite.EXRWrite"]["completed"],
                )
                self.assertEqual(
                    3,
                    payload["outputs"]["SmartWrite.EXRWrite"]["total"],
                )
                self.assertEqual(
                    1,
                    payload["outputs"]["SmartWrite.MP4Write"]["completed"],
                )
                self.assertEqual(
                    3,
                    payload["outputs"]["SmartWrite.MP4Write"]["total"],
                )
                self.assertEqual(
                    progress.CALLBACK_NAME,
                    exr_writer.after_frame_render.value,
                )
                self.assertEqual(
                    progress.CALLBACK_NAME,
                    mp4_writer.after_frame_render.value,
                )

                for frame in (1002, 1003):
                    progress.afterFrameRender(frame, exr_writer, None)
                for frame in (1001, 1003, 1005):
                    progress.afterFrameRender(frame, mp4_writer, None)

                payload = json.loads(status_path.read_text(encoding="utf-8"))
                self.assertEqual("rendering", payload["state"])
                self.assertEqual(99.0, payload["percent"])
                progress.complete(1)
                progress.afterFrameRender(42, exr_writer, None)

            payload = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual("complete", payload["state"])
            self.assertEqual(6, payload["completed_frames"])
            self.assertEqual(100.0, payload["percent"])
            self.assertEqual(1, payload["rendered_smart_writes"])
            self.assertEqual(
                3,
                payload["outputs"]["SmartWrite.EXRWrite"]["completed"],
            )
            self.assertFalse(status_path.with_suffix(".json.tmp").exists())

    def test_runtime_writer_is_matched_by_filename_when_node_name_changes(
        self,
    ) -> None:
        progress = _load_progress_module()
        configured_writer = _FakeWriter(
            "SmartWrite1.EXRWrite",
            "C:/renders/shot/shot.####.exr",
        )
        runtime_writer = _FakeWriter(
            "SmartWrite1.Write14",
            "C:/renders/shot/shot.####.exr",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            status_path = Path(temporary_directory) / "status.json"
            with patch.dict(os.environ, {STATUS_ENV: str(status_path)}):
                progress.configure([(configured_writer, 1001, 1003, 1)])
                progress.WRITE_INTERVAL_SECONDS = 0
                progress.afterFrameRender(1, runtime_writer, None)
                progress.afterFrameRender(1001, runtime_writer, None)

            payload = json.loads(status_path.read_text(encoding="utf-8"))
            output = payload["outputs"]["SmartWrite1.EXRWrite"]
            self.assertEqual(1, output["completed"])
            self.assertEqual("C:/renders/shot/shot.####.exr", output["filename"])
            self.assertEqual(1001, output["first_frame"])
            self.assertEqual(1003, output["last_frame"])
            self.assertEqual(1, output["frame_increment"])

    def test_validation_rejects_missing_frames_and_tiny_video(self) -> None:
        progress = _load_progress_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            exr_pattern = output_directory / "shot.####.exr"
            (output_directory / "shot.1001.exr").write_bytes(b"frame")
            mp4_path = output_directory / "shot.mp4"
            mp4_path.write_bytes(b"tiny")
            exr_writer = _FakeWriter("SmartWrite.EXRWrite", str(exr_pattern))
            mp4_writer = _FakeWriter("SmartWrite.MP4Write", str(mp4_path))
            status_path = output_directory / "status.json"

            with patch.dict(os.environ, {STATUS_ENV: str(status_path)}):
                progress.configure(
                    [
                        (exr_writer, 1001, 1002, 1),
                        (mp4_writer, 1001, 1002, 1),
                    ]
                )
                for frame in (1001, 1002):
                    progress.afterFrameRender(frame, exr_writer, None)
                    progress.afterFrameRender(frame, mp4_writer, None)
                with self.assertRaisesRegex(
                    RuntimeError,
                    "missing 1 of 2 frame files.*smaller than 1024 bytes",
                ):
                    progress.validate_outputs()

    def test_validation_reconciles_silent_callbacks_from_rendered_files(
        self,
    ) -> None:
        progress = _load_progress_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            exr_pattern = output_directory / "shot.####.exr"
            for frame in (1001, 1002):
                (output_directory / f"shot.{frame}.exr").write_bytes(b"frame")
            writer = _FakeWriter("SmartWrite.EXRWrite", str(exr_pattern))
            status_path = output_directory / "status.json"

            with patch.dict(os.environ, {STATUS_ENV: str(status_path)}):
                progress.configure([(writer, 1001, 1002, 1)])
                progress.validate_outputs()
                progress.complete(1)

            payload = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual("complete", payload["state"])
            self.assertEqual(2, payload["completed_frames"])
            self.assertEqual(2, payload["total_frames"])

    def test_failure_before_configuration_still_writes_status(self) -> None:
        progress = _load_progress_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            status_path = Path(temporary_directory) / "status.json"
            with patch.dict(os.environ, {STATUS_ENV: str(status_path)}):
                progress.failed("No SmartWrite node was found.")

            payload = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual("failed", payload["state"])
            self.assertEqual("No SmartWrite node was found.", payload["message"])


if __name__ == "__main__":
    unittest.main()
