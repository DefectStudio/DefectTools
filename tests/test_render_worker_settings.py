from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.settings import (
    load_saved_local_uproject,
    load_saved_poll_interval_seconds,
    load_saved_render_farm_root,
    load_saved_unreal_editor_cmd,
    save_local_uproject,
    save_poll_interval_seconds,
    save_render_farm_root,
    save_unreal_editor_cmd,
)


class RenderWorkerSettingsTests(unittest.TestCase):
    def test_render_farm_root_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "render_worker.json"

            save_render_farm_root("//server/shows/S3Bishop/RenderFarm", settings_path)

            self.assertEqual(
                "//server/shows/S3Bishop/RenderFarm",
                load_saved_render_farm_root(settings_path),
            )

    def test_broken_local_settings_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "render_worker.json"
            settings_path.write_text("{broken", encoding="utf-8")

            self.assertEqual("", load_saved_render_farm_root(settings_path))

    def test_unreal_editor_cmd_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "render_worker.json"
            executable = "C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe"

            save_unreal_editor_cmd(executable, settings_path)

            self.assertEqual(
                executable,
                load_saved_unreal_editor_cmd(settings_path),
            )

    def test_local_uproject_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "render_worker.json"
            local_project = "K:/UnrealProjects/s3bishop/s3bishop.uproject"

            save_local_uproject(local_project, settings_path)

            self.assertEqual(
                local_project,
                load_saved_local_uproject(settings_path),
            )

    def test_poll_interval_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "render_worker.json"

            save_poll_interval_seconds(15, settings_path)

            self.assertEqual("15", load_saved_poll_interval_seconds(settings_path))


if __name__ == "__main__":
    unittest.main()
