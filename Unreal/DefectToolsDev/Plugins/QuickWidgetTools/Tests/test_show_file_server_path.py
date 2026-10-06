from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
import unittest


PYTHON_DIR = Path(__file__).resolve().parents[1] / "Content" / "Python"
SETTER_PATH = PYTHON_DIR / "show_file_server_path.py"
GETTER_PATH = PYTHON_DIR / "get_file_server_path.py"
SETTINGS_RELATIVE_PATH = (
    Path("Saved") / "Config" / "WindowsEditor" / "QuickWidgetToolsSettings.ini"
)


class UnrealBoundary(ModuleType):
    def __init__(self, project_dir: str) -> None:
        super().__init__("unreal")
        self.Paths = SimpleNamespace(project_dir=lambda: project_dir)

    @staticmethod
    def log(_message: str) -> None:
        pass

    @staticmethod
    def log_warning(_message: str) -> None:
        pass

    @staticmethod
    def log_error(_message: str) -> None:
        pass


def load_script(script_path: Path, module_name: str, project_dir: str):
    sys.modules["unreal"] = UnrealBoundary(project_dir)
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ShowFileServerPathTests(unittest.TestCase):
    def test_setter_canonicalizes_doubled_and_mixed_separators(self) -> None:
        with TemporaryDirectory() as project_dir, TemporaryDirectory() as show_root:
            canonical_path = show_root.replace("\\", "/")
            doubled_backslash_path = canonical_path.replace("/", "\\\\")
            setter = load_script(
                SETTER_PATH, "show_file_server_path_under_test", project_dir
            )

            result = setter.run(doubled_backslash_path)

            settings_text = (Path(project_dir) / SETTINGS_RELATIVE_PATH).read_text(
                encoding="utf-8"
            )

        self.assertEqual("true", result)
        self.assertIn(f"ShowFileServerPath={canonical_path}\n", settings_text)

    def test_getter_canonicalizes_legacy_backslash_value(self) -> None:
        with TemporaryDirectory() as project_dir, TemporaryDirectory() as show_root:
            canonical_path = show_root.replace("\\", "/")
            legacy_path = canonical_path.replace("/", "\\")
            settings_path = Path(project_dir) / SETTINGS_RELATIVE_PATH
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text(
                "[/Script/QuickWidgetTools.RenderToolSettings]\n"
                f"ShowFileServerPath={legacy_path}\n",
                encoding="utf-8",
            )
            getter = load_script(
                GETTER_PATH, "get_file_server_path_under_test", project_dir
            )

            result = getter.run()

        self.assertEqual(canonical_path, result)


if __name__ == "__main__":
    unittest.main()
