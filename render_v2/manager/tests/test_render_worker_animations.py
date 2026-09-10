from __future__ import annotations

from pathlib import Path
import struct
import tempfile
import unittest

from portable_pipe_tools.render_farm.animations import (
    DEFAULT_ANIMATION_SPRITE_FOLDER,
    STAGE_SPRITE_FILENAMES,
    get_stage_sprite_paths,
    inspect_sprite_sheet,
)
from portable_pipe_tools.render_farm.worker import WorkerStage


class RenderWorkerAnimationTests(unittest.TestCase):
    def test_project_sprite_sheets_are_present_and_valid(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        self.assertEqual(
            repository_root / "spriteImages",
            DEFAULT_ANIMATION_SPRITE_FOLDER,
        )

        sprite_paths = get_stage_sprite_paths(DEFAULT_ANIMATION_SPRITE_FOLDER)
        self.assertEqual(len(STAGE_SPRITE_FILENAMES), len(sprite_paths))
        for sprite_path in sprite_paths.values():
            self.assertTrue(sprite_path.is_file(), sprite_path)
            self.assertGreater(inspect_sprite_sheet(sprite_path).frame_count, 0)

        stopped_sprite = sprite_paths[WorkerStage.STOPPED]
        self.assertEqual("Base_Death.png", stopped_sprite.name)
        self.assertEqual(5, inspect_sprite_sheet(stopped_sprite).frame_count)

    def test_valid_transparent_sprite_sheet_reports_frame_count(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            sprite_path = Path(temporary_directory) / "sprite.png"
            self._write_png_header(sprite_path, width=384, height=48, color_type=6)

            info = inspect_sprite_sheet(sprite_path)

            self.assertEqual(8, info.frame_count)
            self.assertTrue(info.has_alpha)

    def test_sprite_sheet_rejects_non_48_pixel_height(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            sprite_path = Path(temporary_directory) / "sprite.png"
            self._write_png_header(sprite_path, width=384, height=64, color_type=6)

            with self.assertRaisesRegex(ValueError, "48px high"):
                inspect_sprite_sheet(sprite_path)

    def test_sprite_sheet_requires_alpha_channel(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            sprite_path = Path(temporary_directory) / "sprite.png"
            self._write_png_header(sprite_path, width=384, height=48, color_type=2)

            with self.assertRaisesRegex(ValueError, "alpha channel"):
                inspect_sprite_sheet(sprite_path)

    @staticmethod
    def _write_png_header(
        path: Path,
        width: int,
        height: int,
        color_type: int,
    ) -> None:
        header = (
            b"\x89PNG\r\n\x1a\n"
            + struct.pack(">I", 13)
            + b"IHDR"
            + struct.pack(">II", width, height)
            + bytes((8, color_type))
        )
        path.write_bytes(header)


if __name__ == "__main__":
    unittest.main()
