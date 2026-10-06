from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "Content"
    / "Python"
    / "create_sequence.py"
)


class UnrealBoundary(ModuleType):
    def __init__(self, project_dir: str) -> None:
        super().__init__("unreal")
        self.dialogs: list[tuple[str, str, object]] = []
        self.Paths = SimpleNamespace(project_dir=lambda: project_dir)
        self.EditorDialog = SimpleNamespace(show_message=self._show_message)
        self.AppMsgType = SimpleNamespace(OK="OK")
        self.EditorAssetLibrary = SimpleNamespace(
            does_directory_exist=lambda _path: False,
            make_directory=lambda _path: False,
            does_asset_exist=lambda _path: False,
        )

    def _show_message(self, title: str, message: str, message_type: object) -> None:
        self.dialogs.append((title, message, message_type))

    @staticmethod
    def log(_message: str) -> None:
        pass

    @staticmethod
    def log_warning(_message: str) -> None:
        pass

    @staticmethod
    def log_error(_message: str) -> None:
        pass


def load_create_sequence(unreal_boundary: UnrealBoundary):
    sys.modules["unreal"] = unreal_boundary
    spec = importlib.util.spec_from_file_location(
        "create_sequence_under_test", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CreateSequenceTests(unittest.TestCase):
    def test_missing_show_folder_setting_explains_how_to_configure_it(self) -> None:
        with TemporaryDirectory() as project_dir:
            unreal_boundary = UnrealBoundary(project_dir)
            create_sequence = load_create_sequence(unreal_boundary)

            result = create_sequence.run("ironwidow", "MEW")

        self.assertEqual("", result)
        self.assertEqual(1, len(unreal_boundary.dialogs))
        title, message, message_type = unreal_boundary.dialogs[0]
        self.assertEqual("Unable to Create Sequence", title)
        self.assertIn("Initialize Project", message)
        self.assertIn("show folder", message.lower())
        self.assertEqual("OK", message_type)

    def test_unreal_folder_creation_failure_displays_an_error(self) -> None:
        with TemporaryDirectory() as project_dir, TemporaryDirectory() as show_root:
            settings_path = (
                Path(project_dir)
                / "Saved"
                / "Config"
                / "WindowsEditor"
                / "QuickWidgetToolsSettings.ini"
            )
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text(
                "[/Script/QuickWidgetTools.RenderToolSettings]\n"
                f"ShowFileServerPath={show_root}\n",
                encoding="utf-8",
            )
            unreal_boundary = UnrealBoundary(project_dir)
            create_sequence = load_create_sequence(unreal_boundary)

            result = create_sequence.run("ironwidow", "MEW")

        self.assertEqual("", result)
        self.assertEqual(1, len(unreal_boundary.dialogs))
        title, message, message_type = unreal_boundary.dialogs[0]
        self.assertEqual("Unable to Create Sequence", title)
        self.assertIn("could not be created", message.lower())
        self.assertEqual("OK", message_type)


if __name__ == "__main__":
    unittest.main()
