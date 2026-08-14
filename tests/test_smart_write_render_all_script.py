from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "natron_plugins"
    / "SmartWriteRenderAll.py"
)
STATUS_ENV = "PORTABLE_PIPE_SMART_WRITE_RENDER_STATUS"


class _FakeNode:
    def __init__(self, plugin_id: str, children: tuple[object, ...] = ()) -> None:
        self._plugin_id = plugin_id
        self._children = children

    def getPluginID(self) -> str:
        return self._plugin_id

    def getChildren(self) -> tuple[object, ...]:
        return self._children


class SmartWriteRenderAllScriptTests(unittest.TestCase):
    def test_script_renders_all_nested_smart_writes_and_reports_completion(
        self,
    ) -> None:
        smart_write = _FakeNode("com.portablepipetools.SmartWrite")
        app = _FakeNode("app", (_FakeNode("group", (smart_write,)),))
        extension = Mock()
        extension.PLUGIN_ID = "com.portablepipetools.SmartWrite"
        extension.WRITER_SPECS = (
            ("exrOutput", "EXRWrite", "exr_sequence"),
            ("mp4Output", "MP4Write", "mp4_file"),
        )
        extension._render_enabled_outputs.return_value = True

        with tempfile.TemporaryDirectory() as temporary_directory:
            status_path = Path(temporary_directory) / "status.json"
            with (
                patch.dict(sys.modules, {"SmartWriteExt": extension}),
                patch.dict(os.environ, {STATUS_ENV: str(status_path)}),
            ):
                runpy.run_path(str(SCRIPT_PATH), init_globals={"app": app})

            payload = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual("complete", payload["state"])
            self.assertEqual(1, payload["rendered_smart_writes"])
            extension.afterProjectLoaded.assert_called_once_with(app)
            extension._render_enabled_outputs.assert_called_once_with(
                app,
                smart_write,
                ["exrOutput", "mp4Output"],
            )

    def test_script_reports_missing_smart_write_as_failure(self) -> None:
        app = _FakeNode("app")
        extension = Mock()
        extension.PLUGIN_ID = "com.portablepipetools.SmartWrite"
        extension.WRITER_SPECS = ()

        with tempfile.TemporaryDirectory() as temporary_directory:
            status_path = Path(temporary_directory) / "status.json"
            with (
                patch.dict(sys.modules, {"SmartWriteExt": extension}),
                patch.dict(os.environ, {STATUS_ENV: str(status_path)}),
                self.assertRaisesRegex(RuntimeError, "No SmartWrite node"),
            ):
                runpy.run_path(str(SCRIPT_PATH), init_globals={"app": app})

            payload = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual("failed", payload["state"])
            self.assertIn("No SmartWrite node", payload["message"])


if __name__ == "__main__":
    unittest.main()
