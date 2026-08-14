from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

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
    poll_render_comp,
    render_comp,
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
    def test_render_comp_launches_render_all_script_with_portable_plugins(
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
            process = Mock()
            popen.return_value = process
            hydrate.return_value = SourceHydrationResult(None, 12, 4)

            with patch(
                "portable_pipe_tools.auto_comp_natron.render_comp.render_comp."
                "_new_status_path",
                return_value=status_path,
            ):
                result = render_comp(
                    show_root,
                    "BSH",
                    "BSH_000_0010",
                    natron_executable=temporary_path / "Natron.exe",
                )

            command = popen.call_args.args[0]
            options = popen.call_args.kwargs
            self.assertEqual(
                str(temporary_path / "NatronRenderer.exe"),
                command[0],
            )
            self.assertEqual("--onload", command[1])
            self.assertEqual(str(get_smart_write_render_script_path()), command[2])
            self.assertEqual(str(comp_path), command[3])
            self.assertEqual(str(status_path), options["env"][RENDER_STATUS_ENV])
            self.assertIn(
                str(get_smart_write_render_script_path().parent),
                options["env"][NATRON_PLUGIN_PATH_ENV].split(os.pathsep),
            )
            self.assertEqual(4, result.hydrated_source_files)
            self.assertIs(process, result.process)

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

    def test_poll_surfaces_smart_write_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            status_path = Path(temporary_directory) / "status.json"
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
            )

            with self.assertRaisesRegex(
                CompRenderFailedError,
                "No enabled SmartWrite outputs",
            ):
                poll_render_comp(result)

            self.assertFalse(status_path.exists())


if __name__ == "__main__":
    unittest.main()
