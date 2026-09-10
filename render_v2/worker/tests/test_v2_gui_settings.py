import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from portable_pipe_tools.render_farm.v2_gui_settings import (
    load_or_detect_unreal_editor,
    save_unreal_editor_preference,
)


class V2GuiSettingsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.settings = Path(directory.name) / "settings/worker_v2.json"
        self.detect = self.enterContext(patch(
            "portable_pipe_tools.render_farm.v2_gui_settings.find_installed_unreal_editor"
        ))

    def test_first_launch_detects_once_and_next_launch_uses_saved_result(self):
        self.detect.return_value = Path("D:/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe")
        expected = str(self.detect.return_value)
        self.assertEqual(expected, load_or_detect_unreal_editor(self.settings))
        self.detect.return_value = None
        self.assertEqual(expected, load_or_detect_unreal_editor(self.settings))
        self.detect.assert_called_once_with(["5.8"])

    def test_unsuccessful_first_detection_stays_blank_without_retrying(self):
        self.detect.return_value = None
        self.assertEqual("", load_or_detect_unreal_editor(self.settings))
        self.detect.side_effect = AssertionError("Detection must not repeat")
        self.assertEqual("", load_or_detect_unreal_editor(self.settings))

    def test_manual_selection_and_clearing_are_preserved(self):
        self.detect.side_effect = AssertionError("Saved preference must bypass detection")
        save_unreal_editor_preference("D:/Custom/UnrealEditor-Cmd.exe", self.settings)
        self.assertEqual("D:/Custom/UnrealEditor-Cmd.exe", load_or_detect_unreal_editor(self.settings))
        save_unreal_editor_preference("", self.settings)
        self.assertEqual("", load_or_detect_unreal_editor(self.settings))

    def test_engine_updates_preserve_other_v2_settings(self):
        self.settings.parent.mkdir()
        self.settings.write_text(json.dumps({"workspace_root": "F:/Renders", "catalog": "studio.json"}))
        self.detect.return_value = None
        load_or_detect_unreal_editor(self.settings)
        save_unreal_editor_preference("D:/Engine/UnrealEditor-Cmd.exe", self.settings)
        saved = json.loads(self.settings.read_text())
        self.assertEqual("F:/Renders", saved["workspace_root"])
        self.assertEqual("studio.json", saved["catalog"])


if __name__ == "__main__":
    unittest.main()
