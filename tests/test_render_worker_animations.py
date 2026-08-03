from __future__ import annotations

from pathlib import Path
import struct
import tempfile
import unittest

from portable_pipe_tools.render_farm.animations import inspect_sprite_sheet


class RenderWorkerAnimationTests(unittest.TestCase):
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
