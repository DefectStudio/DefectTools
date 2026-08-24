from __future__ import annotations

from pathlib import Path
import unittest


class AutoCompNatronLauncherTests(unittest.TestCase):
    def test_launcher_uses_detached_windowed_python(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        launcher = repository_root / "tools" / "auto_comp_natron.bat"

        launcher_text = launcher.read_text(encoding="utf-8").lower()

        self.assertIn("start \"\"", launcher_text)
        self.assertIn("pyw.exe -3 -m", launcher_text)
        self.assertIn("\nexit 0", launcher_text)
        self.assertNotIn("exit /b", launcher_text)
        self.assertNotIn(
            "\npy -3 -m portable_pipe_tools.apps.auto_comp_natron_app",
            launcher_text,
        )


if __name__ == "__main__":
    unittest.main()
