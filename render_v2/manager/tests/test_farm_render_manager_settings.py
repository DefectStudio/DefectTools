from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.manager_settings import (
    SETTINGS_SCHEMA_VERSION,
    load_manager_settings,
    load_saved_auto_refresh_enabled,
    load_saved_auto_refresh_interval_minutes,
    load_saved_dropbox_folder,
    save_auto_refresh_enabled,
    save_auto_refresh_interval_minutes,
    save_dropbox_folder,
)


class FarmRenderManagerSettingsTests(unittest.TestCase):
    def test_dropbox_folder_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "manager.json"
            dropbox_folder = Path(temporary_directory) / "Dropbox"
            dropbox_folder.mkdir()

            saved_path = save_dropbox_folder(dropbox_folder, settings_path)

            self.assertEqual(settings_path, saved_path)
            self.assertEqual(
                str(dropbox_folder),
                load_saved_dropbox_folder(settings_path),
            )
            self.assertEqual(
                SETTINGS_SCHEMA_VERSION,
                load_manager_settings(settings_path)["schema_version"],
            )

    def test_missing_config_is_first_startup_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "missing.json"

            self.assertFalse(settings_path.exists())
            self.assertEqual("", load_saved_dropbox_folder(settings_path))

    def test_broken_config_is_read_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "manager.json"
            settings_path.write_text("{broken", encoding="utf-8")

            self.assertEqual({}, load_manager_settings(settings_path))

    def test_auto_refresh_defaults_to_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "missing.json"

            self.assertTrue(load_saved_auto_refresh_enabled(settings_path))

    def test_auto_refresh_interval_defaults_to_one_minute(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "missing.json"

            self.assertEqual(
                1,
                load_saved_auto_refresh_interval_minutes(settings_path),
            )

    def test_auto_refresh_round_trip_preserves_dropbox_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "manager.json"
            save_dropbox_folder("F:/Dropbox/Shows", settings_path)

            save_auto_refresh_enabled(False, settings_path)

            self.assertFalse(load_saved_auto_refresh_enabled(settings_path))
            self.assertEqual(
                "F:/Dropbox/Shows",
                load_saved_dropbox_folder(settings_path),
            )
            self.assertIs(
                False,
                load_manager_settings(settings_path)["auto_refresh_enabled"],
            )

    def test_auto_refresh_interval_round_trip_preserves_other_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "manager.json"
            save_dropbox_folder("F:/Dropbox/Shows", settings_path)
            save_auto_refresh_enabled(False, settings_path)

            for minutes in (1, 2, 5, 10):
                with self.subTest(minutes=minutes):
                    save_auto_refresh_interval_minutes(minutes, settings_path)
                    self.assertEqual(
                        minutes,
                        load_saved_auto_refresh_interval_minutes(settings_path),
                    )

            self.assertEqual(
                "F:/Dropbox/Shows",
                load_saved_dropbox_folder(settings_path),
            )
            self.assertFalse(load_saved_auto_refresh_enabled(settings_path))

    def test_invalid_saved_auto_refresh_interval_uses_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_path = Path(temporary_directory) / "manager.json"
            settings_path.write_text(
                '{"auto_refresh_interval_minutes": 3}',
                encoding="utf-8",
            )

            self.assertEqual(
                1,
                load_saved_auto_refresh_interval_minutes(settings_path),
            )
            with self.assertRaises(ValueError):
                save_auto_refresh_interval_minutes(3, settings_path)


if __name__ == "__main__":
    unittest.main()
