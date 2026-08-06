from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from portable_pipe_tools.apps.auto_comp_natron_app import AutoCompNatronApp
from portable_pipe_tools.auto_comp_natron.settings import (
    load_saved_browser_selection,
    load_saved_repository_folder,
    save_repository_folder,
)


def _create_test_repository(repository: Path) -> None:
    for relative_folder in (
        "alpha/sequences/AAA/AAA_000_0010",
        "alpha/sequences/AAA/AAA_000_0020",
        "beta/sequences/BBB/BBB_000_0010",
        "beta/sequences/CCC/CCC_000_0030",
        "beta/sequences/CCC/CCC_000_0040",
    ):
        (repository / relative_folder).mkdir(parents=True)


class AutoCompNatronAppTests(unittest.TestCase):
    def test_window_starts_disconnected_with_empty_browser(self) -> None:
        app = AutoCompNatronApp(prompt_on_startup=False)
        app.root.withdraw()

        try:
            self.assertEqual("Auto Comp - Natron", app.root.title())
            self.assertEqual("Repository Connected: No", app.repository_status_var.get())
            self.assertEqual([], app.show_names)
            self.assertEqual([], app.sequence_names)
            self.assertEqual([], app.shot_names)
            self.assertTrue(app.hero_var.get())
            self.assertTrue(app.exr_var.get())
        finally:
            app.root.destroy()

    def test_connecting_selects_first_show_sequence_and_shot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            settings_path = temporary_path / "settings.json"
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            app = AutoCompNatronApp(
                settings_path=settings_path,
                prompt_on_startup=False,
            )
            app.root.withdraw()

            try:
                app._set_repository_connected(repository)

                self.assertEqual(["alpha", "beta"], app.show_names)
                self.assertEqual("alpha", app._selected_value(app.show_list, app.show_names))
                self.assertEqual(["AAA"], app.sequence_names)
                self.assertEqual("AAA", app._selected_value(app.sequence_list, app.sequence_names))
                self.assertEqual(
                    ["AAA_000_0010", "AAA_000_0020"],
                    app.shot_names,
                )
                self.assertEqual(
                    "AAA_000_0010",
                    app._selected_value(app.shot_list, app.shot_names),
                )
            finally:
                app.root.destroy()

    def test_show_and_sequence_selections_cascade(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()

            try:
                app._set_repository_connected(repository)
                app.show_list.selection_clear(0, "end")
                app.show_list.selection_set(1)
                app._on_show_selected(None)

                self.assertEqual(["BBB", "CCC"], app.sequence_names)
                self.assertEqual(["BBB_000_0010"], app.shot_names)

                app.sequence_list.selection_clear(0, "end")
                app.sequence_list.selection_set(1)
                app._on_sequence_selected(None)

                self.assertEqual(
                    ["CCC_000_0030", "CCC_000_0040"],
                    app.shot_names,
                )
                self.assertEqual(
                    "CCC_000_0030",
                    app._selected_value(app.shot_list, app.shot_names),
                )
            finally:
                app.root.destroy()

    def test_last_browser_selection_is_restored_on_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            settings_path = temporary_path / "settings.json"
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            save_repository_folder(repository, settings_path)

            first_app = AutoCompNatronApp(
                settings_path=settings_path,
                prompt_on_startup=False,
            )
            first_app.root.withdraw()
            try:
                first_app._initialize_repository()
                first_app.show_list.selection_clear(0, "end")
                first_app.show_list.selection_set(1)
                first_app._on_show_selected(None)
                first_app.sequence_list.selection_clear(0, "end")
                first_app.sequence_list.selection_set(1)
                first_app._on_sequence_selected(None)
                first_app.shot_list.selection_clear(0, "end")
                first_app.shot_list.selection_set(1)
                first_app._on_shot_selected(None)
            finally:
                first_app.root.destroy()

            second_app = AutoCompNatronApp(
                settings_path=settings_path,
                prompt_on_startup=False,
            )
            second_app.root.withdraw()
            try:
                second_app._initialize_repository()
                self.assertEqual(
                    ("beta", "CCC", "CCC_000_0040"),
                    load_saved_browser_selection(settings_path),
                )
                self.assertEqual(
                    "beta",
                    second_app._selected_value(second_app.show_list, second_app.show_names),
                )
                self.assertEqual(
                    "CCC",
                    second_app._selected_value(
                        second_app.sequence_list,
                        second_app.sequence_names,
                    ),
                )
                self.assertEqual(
                    "CCC_000_0040",
                    second_app._selected_value(second_app.shot_list, second_app.shot_names),
                )
            finally:
                second_app.root.destroy()

    def test_repository_picker_saves_connects_and_populates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            settings_path = temporary_path / "settings.json"
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            app = AutoCompNatronApp(
                settings_path=settings_path,
                prompt_on_startup=False,
            )
            app.root.withdraw()

            try:
                with patch(
                    "portable_pipe_tools.apps.auto_comp_natron_app."
                    "filedialog.askdirectory",
                    return_value=str(repository),
                ):
                    app._browse_repository_folder()

                self.assertEqual(repository, app.repository_path)
                self.assertEqual(
                    str(repository),
                    load_saved_repository_folder(settings_path),
                )
                self.assertEqual(["alpha", "beta"], app.show_names)
                self.assertEqual(
                    "RepositoryConnected.TLabel",
                    app.repository_status_label.cget("style"),
                )
            finally:
                app.root.destroy()


if __name__ == "__main__":
    unittest.main()
