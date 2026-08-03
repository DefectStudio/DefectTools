from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.settings import (
    load_saved_animation_sprite_folder,
    load_saved_render_farm_root,
    save_animation_sprite_folder,
    save_render_farm_root,
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

    def test_render_farm_and_sprite_folders_are_both_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "render_worker.json"

            save_render_farm_root("F:/shows/S3Bishop/renderFarm", settings_path)
            save_animation_sprite_folder("D:/pixelAssets/Base", settings_path)

            self.assertEqual(
                "F:/shows/S3Bishop/renderFarm",
                load_saved_render_farm_root(settings_path),
            )
            self.assertEqual(
                "D:/pixelAssets/Base",
                load_saved_animation_sprite_folder(settings_path),
            )

    def test_broken_local_settings_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "render_worker.json"
            settings_path.write_text("{broken", encoding="utf-8")

            self.assertEqual("", load_saved_render_farm_root(settings_path))


if __name__ == "__main__":
    unittest.main()
