from __future__ import annotations

from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from portable_pipe_tools.auto_comp_natron.create_comp import (
    SmartWriteOutputOptions,
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
    open_comp_in_natron,
)
from portable_pipe_tools.auto_comp_natron.open_comp.open_comp import _default_opener
from portable_pipe_tools.auto_comp_natron.source_media import (
    SourceHydrationError,
    SourceHydrationResult,
)


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

    @patch(
        "portable_pipe_tools.auto_comp_natron.open_comp.open_comp.subprocess.Popen"
    )
    def test_interactive_natron_stdout_and_stderr_are_captured(
        self,
        popen: Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            comp_path = temporary_path / "shot.ntp"
            output_log_path = temporary_path / "logs" / "natron.log"
            process = Mock(pid=4321)
            popen.return_value = process

            result = open_comp_in_natron(
                comp_path,
                temporary_path / "Natron.exe",
                output_log_path=output_log_path,
            )

            self.assertIs(process, result)
            options = popen.call_args.kwargs
            self.assertEqual(str(output_log_path), options["stdout"].name)
            self.assertEqual(__import__("subprocess").STDOUT, options["stderr"])
            self.assertIn(
                "Starting Natron for",
                output_log_path.read_text(encoding="utf-8"),
            )

    def test_open_comp_opens_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            comp_path = get_comp_path(show_root, "BSH", "BSH_000_0010")
            comp_path.parent.mkdir(parents=True)
            comp_path.write_bytes(b"comp")
            opener = Mock()
            diagnostic_messages: list[str] = []

            result = open_comp(
                show_root,
                "BSH",
                "BSH_000_0010",
                opener=opener,
                diagnostic_log=diagnostic_messages.append,
            )

            opener.assert_called_once_with(comp_path)
            self.assertEqual(comp_path, result.comp_path)
            self.assertFalse(result.created)
            diagnostic_text = "\n".join(diagnostic_messages)
            self.assertIn("resolved project", diagnostic_text)
            self.assertIn("hydration completed", diagnostic_text)
            self.assertIn("launching through custom opener", diagnostic_text)
            self.assertIn("launch request completed", diagnostic_text)

    @patch(
        "portable_pipe_tools.auto_comp_natron.open_comp.open_comp."
        "hydrate_latest_source_sequence"
    )
    def test_open_comp_hydrates_source_before_launch(self, hydrate: Mock) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            comp_path = get_comp_path(show_root, "BSH", "BSH_000_0010")
            comp_path.parent.mkdir(parents=True)
            comp_path.write_bytes(b"comp")
            hydrate.return_value = SourceHydrationResult(None, 40, 38)
            opener = Mock()

            result = open_comp(
                show_root,
                "BSH",
                "BSH_000_0010",
                opener=opener,
            )

            hydrate.assert_called_once_with(
                show_root,
                "BSH",
                "BSH_000_0010",
                progress=None,
            )
            opener.assert_called_once_with(comp_path)
            self.assertEqual(38, result.hydrated_source_files)

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
            _, fallback_template, _ = get_template_candidates(show_root, "BSH")
            fallback_template.parent.mkdir(parents=True)
            fallback_template.write_text(
                "<Project>"
                "<Name>exrOutput</Name><Type>Bool</Type><item><Value>1</Value></item>"
                "<Name>mp4Output</Name><Type>Bool</Type><item><Value>1</Value></item>"
                "<Name>movOutput</Name><Type>Bool</Type><item><Value>0</Value></item>"
                "<Name>heroOutput</Name><Type>Bool</Type><item><Value>1</Value></item>"
                "</Project>",
                encoding="utf-8",
            )
            opener = Mock()

            result = create_and_open_comp(
                show_root,
                "BSH",
                "BSH_000_0010",
                smart_write_outputs=SmartWriteOutputOptions(
                    exr=False,
                    mp4=True,
                    mov=True,
                    hero=False,
                ),
                opener=opener,
            )

            self.assertTrue(result.created)
            project_text = result.comp_path.read_text(encoding="utf-8")
            expected_values = {
                "exrOutput": 0,
                "mp4Output": 1,
                "movOutput": 1,
                "heroOutput": 0,
            }
            for parameter_name, expected_value in expected_values.items():
                self.assertIn(
                    f"<Name>{parameter_name}</Name><Type>Bool</Type>"
                    f"<item><Value>{expected_value}</Value>",
                    project_text,
                )
            opener.assert_called_once_with(result.comp_path)

    @patch(
        "portable_pipe_tools.auto_comp_natron.open_comp.open_comp."
        "hydrate_latest_source_sequence"
    )
    def test_create_and_open_stops_before_create_when_download_fails(
        self,
        hydrate: Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            comp_path = get_comp_path(show_root, "BSH", "BSH_000_0010")
            source_path = show_root / "frame.1001.exr"
            hydrate.side_effect = SourceHydrationError(
                source_path,
                "Dropbox is offline",
            )
            opener = Mock()

            with self.assertRaises(SourceHydrationError):
                create_and_open_comp(
                    show_root,
                    "BSH",
                    "BSH_000_0010",
                    opener=opener,
                )

            self.assertFalse(comp_path.exists())
            opener.assert_not_called()

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
