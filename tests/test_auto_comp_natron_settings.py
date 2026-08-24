from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.auto_comp_natron.settings import (
    SETTINGS_SCHEMA_VERSION,
    load_log_username,
    load_saved_browser_selection,
    load_saved_natron_executable,
    load_saved_repository_folder,
    load_settings,
    load_verbose_logging_enabled,
    save_browser_selection,
    save_log_username,
    save_natron_executable,
    save_repository_folder,
    save_verbose_logging_enabled,
)


class AutoCompNatronSettingsTests(unittest.TestCase):
    def test_repository_folder_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.json"
            repository = Path(temporary_directory) / "repository"
            repository.mkdir()

            saved_path = save_repository_folder(repository, settings_path)

            self.assertEqual(settings_path, saved_path)
            self.assertEqual(
                str(repository),
                load_saved_repository_folder(settings_path),
            )
            self.assertEqual(
                SETTINGS_SCHEMA_VERSION,
                load_settings(settings_path)["schema_version"],
            )

    def test_missing_or_broken_settings_are_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.json"
            self.assertEqual("", load_saved_repository_folder(settings_path))
            self.assertEqual("", load_saved_natron_executable(settings_path))

            settings_path.write_text("{broken", encoding="utf-8")
            self.assertEqual({}, load_settings(settings_path))

    def test_non_object_json_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.json"
            settings_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
            self.assertEqual({}, load_settings(settings_path))

    def test_browser_selection_round_trip_preserves_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.json"
            save_repository_folder("F:/Shows", settings_path)

            save_browser_selection(
                "s3bishop",
                "BSH",
                "BSH_000_0030",
                settings_path,
            )

            self.assertEqual(
                ("s3bishop", "BSH", "BSH_000_0030"),
                load_saved_browser_selection(settings_path),
            )
            self.assertEqual(
                "F:/Shows",
                load_saved_repository_folder(settings_path),
            )

    def test_natron_executable_round_trip_preserves_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.json"
            save_repository_folder("F:/Shows", settings_path)
            executable = Path(temporary_directory) / "Natron.exe"

            save_natron_executable(executable, settings_path)

            self.assertEqual(
                str(executable),
                load_saved_natron_executable(settings_path),
            )
            self.assertEqual("F:/Shows", load_saved_repository_folder(settings_path))

    def test_verbose_logging_setting_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.json"

            self.assertTrue(load_verbose_logging_enabled(settings_path))
            save_verbose_logging_enabled(True, settings_path)
            self.assertTrue(load_verbose_logging_enabled(settings_path))
            save_verbose_logging_enabled(False, settings_path)
            self.assertFalse(load_verbose_logging_enabled(settings_path))

    def test_log_username_round_trip_preserves_other_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.json"
            save_repository_folder("F:/Shows", settings_path)

            save_log_username("  Kat Francis  ", settings_path)

            self.assertEqual("Kat Francis", load_log_username(settings_path))
            self.assertEqual(
                "F:/Shows",
                load_saved_repository_folder(settings_path),
            )

    def test_empty_log_username_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "settings.json"

            with self.assertRaisesRegex(ValueError, "cannot be empty"):
                save_log_username("   ", settings_path)


if __name__ == "__main__":
    unittest.main()
