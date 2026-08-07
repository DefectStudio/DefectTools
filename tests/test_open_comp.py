from __future__ import annotations

from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from portable_pipe_tools.auto_comp_natron.create_comp import (
    get_comp_path,
    get_template_candidates,
)
from portable_pipe_tools.auto_comp_natron.open_comp import (
    CompNotFoundError,
    NATRON_EXECUTABLE_ENV,
    NATRON_PLUGIN_PATH_ENV,
    build_natron_environment,
    create_and_open_comp,
    get_natron_executable,
    get_portable_natron_plugins_path,
    get_smart_read_onload_script_path,
    open_comp,
)
from portable_pipe_tools.auto_comp_natron.open_comp.open_comp import _default_opener


class OpenCompTests(unittest.TestCase):
    def test_natron_environment_prepends_portable_plugins(self) -> None:
        plugin_path = Path("F:/StandAloneTools/natron_plugins")
        existing_path = str(Path("F:/OtherNatronPlugins"))

        result = build_natron_environment(
            {NATRON_PLUGIN_PATH_ENV: existing_path},
            plugin_path,
        )

        self.assertEqual(
            [str(plugin_path), existing_path],
            result[NATRON_PLUGIN_PATH_ENV].split(os.pathsep),
        )

    def test_natron_environment_does_not_duplicate_portable_plugins(self) -> None:
        plugin_path = Path("F:/StandAloneTools/natron_plugins")

        result = build_natron_environment(
            {NATRON_PLUGIN_PATH_ENV: str(plugin_path)},
            plugin_path,
        )

        self.assertEqual(str(plugin_path), result[NATRON_PLUGIN_PATH_ENV])

    def test_natron_executable_can_be_overridden(self) -> None:
        configured = "D:/Apps/Natron/bin/Natron.exe"

        self.assertEqual(
            Path(configured),
            get_natron_executable({NATRON_EXECUTABLE_ENV: configured}),
        )

    @patch(
        "portable_pipe_tools.auto_comp_natron.open_comp.open_comp.subprocess.Popen"
    )
    def test_default_opener_launches_natron_with_portable_plugins(
        self,
        popen: Mock,
    ) -> None:
        comp_path = Path("F:/repo/show/sequences/BSH/shot/comp/natron/comp.ntp")

        _default_opener(comp_path)

        command = popen.call_args.args[0]
        options = popen.call_args.kwargs
        self.assertEqual(str(get_natron_executable(options["env"])), command[0])
        self.assertEqual("--onload", command[1])
        self.assertEqual(str(get_smart_read_onload_script_path()), command[2])
        self.assertEqual(str(comp_path), command[3])
        self.assertIn(
            str(get_portable_natron_plugins_path()),
            options["env"][NATRON_PLUGIN_PATH_ENV].split(os.pathsep),
        )
        self.assertEqual(
            getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0),
            options["creationflags"],
        )

    def test_open_comp_opens_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            comp_path = get_comp_path(show_root, "BSH", "BSH_000_0010")
            comp_path.parent.mkdir(parents=True)
            comp_path.write_bytes(b"comp")
            opener = Mock()

            result = open_comp(
                show_root,
                "BSH",
                "BSH_000_0010",
                opener=opener,
            )

            opener.assert_called_once_with(comp_path)
            self.assertEqual(comp_path, result.comp_path)
            self.assertFalse(result.created)

    def test_open_comp_rejects_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            opener = Mock()

            with self.assertRaises(CompNotFoundError):
                open_comp(
                    show_root,
                    "BSH",
                    "BSH_000_0010",
                    opener=opener,
                )

            opener.assert_not_called()

    def test_create_and_open_creates_missing_comp_then_opens_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            _, fallback_template = get_template_candidates(show_root, "BSH")
            fallback_template.parent.mkdir(parents=True)
            fallback_template.write_bytes(b"template")
            opener = Mock()

            result = create_and_open_comp(
                show_root,
                "BSH",
                "BSH_000_0010",
                opener=opener,
            )

            self.assertTrue(result.created)
            self.assertEqual(b"template", result.comp_path.read_bytes())
            opener.assert_called_once_with(result.comp_path)

    def test_create_and_open_opens_existing_comp_without_changing_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            comp_path = get_comp_path(show_root, "BSH", "BSH_000_0010")
            comp_path.parent.mkdir(parents=True)
            comp_path.write_bytes(b"artist work")
            opener = Mock()

            result = create_and_open_comp(
                show_root,
                "BSH",
                "BSH_000_0010",
                opener=opener,
            )

            self.assertFalse(result.created)
            self.assertEqual(b"artist work", comp_path.read_bytes())
            opener.assert_called_once_with(comp_path)


if __name__ == "__main__":
    unittest.main()
