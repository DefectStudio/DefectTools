from __future__ import annotations

import unittest

from portable_pipe_tools.apps.farm_render_manager_icon import (
    ICON_ICO_PATH,
    ICON_PNG_PATH,
)


class FarmRenderManagerIconTests(unittest.TestCase):
    def test_png_and_windows_icon_assets_are_present(self) -> None:
        self.assertTrue(ICON_PNG_PATH.is_file())
        self.assertTrue(ICON_ICO_PATH.is_file())
        self.assertEqual(b"\x89PNG\r\n\x1a\n", ICON_PNG_PATH.read_bytes()[:8])
        self.assertEqual(b"\x00\x00\x01\x00", ICON_ICO_PATH.read_bytes()[:4])


if __name__ == "__main__":
    unittest.main()
