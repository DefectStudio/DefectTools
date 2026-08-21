from __future__ import annotations

from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import Mock, patch


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "natron_plugins"
    / "SmartWriteRenderAll.py"
)
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
        app.closeProject = Mock()
        extension = Mock()
        extension.PLUGIN_ID = "com.portablepipetools.SmartWrite"
        extension.WRITER_SPECS = (
            ("exrOutput", "EXRWrite", "exr_sequence"),
            ("mp4Output", "MP4Write", "mp4_file"),
        )
        tasks = [(Mock(), 1001, 1010, 1)]
        extension._enabled_render_tasks.return_value = tasks
        progress = Mock()

        with patch.dict(
            sys.modules,
            {
                "SmartWriteExt": extension,
                "SmartWriteRenderProgress": progress,
            },
        ):
            runpy.run_path(str(SCRIPT_PATH), init_globals={"app": app})

        extension.afterProjectLoaded.assert_called_once_with(app)
        extension._enabled_render_tasks.assert_called_once_with(
            app,
            smart_write,
            ["exrOutput", "mp4Output"],
        )
        progress.configure.assert_called_once_with(tasks)
        extension._submit_render_tasks.assert_called_once_with(app, tasks)
        progress.validate_outputs.assert_called_once_with()
        progress.complete.assert_called_once_with(1)
        app.closeProject.assert_called_once_with()

    def test_script_reports_missing_smart_write_as_failure(self) -> None:
        app = _FakeNode("app")
        app.closeProject = Mock()
        extension = Mock()
        extension.PLUGIN_ID = "com.portablepipetools.SmartWrite"
        extension.WRITER_SPECS = ()
        progress = Mock()

        with (
            patch.dict(
                sys.modules,
                {
                    "SmartWriteExt": extension,
                    "SmartWriteRenderProgress": progress,
                },
            ),
            self.assertRaisesRegex(RuntimeError, "No SmartWrite node"),
        ):
            runpy.run_path(str(SCRIPT_PATH), init_globals={"app": app})

        progress.failed.assert_called_once()
        self.assertIn("No SmartWrite node", progress.failed.call_args.args[0])
        app.closeProject.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
