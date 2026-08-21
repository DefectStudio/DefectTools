from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, call, patch

from portable_pipe_tools.apps.auto_comp_natron_app import (
    AutoCompNatronApp,
    COMP_MISSING_COLOR,
    COMP_PRESENT_COLOR,
    RenderQueueJob,
)
from portable_pipe_tools.auto_comp_natron.create_comp import (
    CompAlreadyExistsError,
    CompTemplateNotFoundError,
    CreateCompResult,
    SmartWriteOutputOptions,
    get_comp_path,
)
from portable_pipe_tools.auto_comp_natron.open_comp import (
    CompNotFoundError,
    OpenCompResult,
)
from portable_pipe_tools.auto_comp_natron.render_comp import (
    RenderCompCompletion,
    RenderCompProgress,
    RenderCompResult,
    SmartWriteNotFoundError,
)
from portable_pipe_tools.auto_comp_natron.settings import (
    load_saved_browser_selection,
    load_saved_natron_executable,
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
    def test_missing_natron_executable_is_prompted_for_and_saved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            settings_path = temporary_path / "settings.json"
            executable = temporary_path / "Natron.exe"
            executable.touch()
            app = AutoCompNatronApp(
                settings_path=settings_path,
                prompt_on_startup=False,
            )
            app.root.withdraw()

            try:
                with patch(
                    "portable_pipe_tools.apps.auto_comp_natron_app."
                    "filedialog.askopenfilename",
                    return_value=str(executable),
                ) as picker:
                    app._initialize_natron_executable()

                picker.assert_called_once()
                self.assertEqual(executable, app.natron_executable_path)
                self.assertEqual(
                    str(executable),
                    load_saved_natron_executable(settings_path),
                )
            finally:
                app.root.destroy()

    def test_window_starts_disconnected_with_empty_browser(self) -> None:
        app = AutoCompNatronApp(prompt_on_startup=False)
        app.root.withdraw()

        try:
            self.assertEqual("Auto Comp - Natron", app.root.title())
            self.assertEqual("Repository Connected: No", app.repository_status_var.get())
            self.assertEqual("Ready", app.status_var.get())
            self.assertEqual([], app.show_names)
            self.assertEqual([], app.sequence_names)
            self.assertEqual([], app.shot_names)
            self.assertTrue(app.exr_var.get())
            self.assertTrue(app.mp4_var.get())
            self.assertFalse(app.mov_var.get())
            self.assertTrue(app.hero_var.get())
            widgets = [app.root]
            checkbox_labels: set[str] = set()
            while widgets:
                widget = widgets.pop()
                widgets.extend(widget.winfo_children())
                if widget.winfo_class() == "TCheckbutton":
                    checkbox_labels.add(str(widget.cget("text")))
            self.assertTrue(
                {"EXR", "MP4", "MOV", "Hero"}.issubset(checkbox_labels)
            )
            self.assertEqual("Job", app.queue_tree.heading("job", "text"))
            self.assertEqual("Status", app.queue_tree.heading("status", "text"))
            self.assertEqual((), app.queue_tree.get_children())
            self.assertEqual("Pause Queue", app.pause_queue_button.cget("text"))
            self.assertEqual("Resume Queue", app.resume_queue_button.cget("text"))
            self.assertEqual("Clear Queue", app.clear_queue_button.cget("text"))
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

    def test_shots_are_sorted_numerically_instead_of_by_manifest_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            sequence_folder = repository / "alpha" / "sequences" / "AAA"
            (sequence_folder / "AAA_000_0100").mkdir()
            (sequence_folder / "aaa_sequence_shots_manifest.json").write_text(
                """{
    "sequence_name": "AAA",
    "shots": [
        {"shot_name": "AAA_000_0100", "order": 1},
        {"shot_name": "AAA_000_0020", "order": 2},
        {"shot_name": "AAA_000_0010", "order": 3}
    ]
}
""",
                encoding="utf-8",
            )
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()

            try:
                app._set_repository_connected(repository)

                self.assertEqual(
                    ["AAA_000_0010", "AAA_000_0020", "AAA_000_0100"],
                    app.shot_names,
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

    def test_context_menus_contain_open_in_explorer(self) -> None:
        app = AutoCompNatronApp(prompt_on_startup=False)
        app.root.withdraw()
        try:
            self.assertEqual(
                "Open in Explorer",
                app.show_context_menu.entrycget(0, "label"),
            )
            self.assertEqual(
                "Create Comp",
                app.shot_context_menu.entrycget(0, "label"),
            )
            self.assertEqual(
                "Create and Open Comp",
                app.shot_context_menu.entrycget(1, "label"),
            )
            self.assertEqual(
                "Open Comp",
                app.shot_context_menu.entrycget(2, "label"),
            )
            self.assertEqual(
                "Render Comp",
                app.shot_context_menu.entrycget(3, "label"),
            )
            self.assertEqual(
                "Add to Render Queue",
                app.shot_context_menu.entrycget(4, "label"),
            )
            self.assertEqual(
                "Open in Explorer",
                app.shot_context_menu.entrycget(6, "label"),
            )
            self.assertEqual(
                "Create All Comps",
                app.sequence_context_menu.entrycget(0, "label"),
            )
            self.assertEqual(
                "Open in Explorer",
                app.sequence_context_menu.entrycget(2, "label"),
            )
            self.assertEqual(
                "Remove from Queue",
                app.queue_context_menu.entrycget(0, "label"),
            )
            self.assertTrue(app.queue_tree.bind("<Button-3>"))
        finally:
            app.root.destroy()

    def test_open_in_explorer_uses_selected_show_sequence_and_shot_folders(
        self,
    ) -> None:
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
                app._select_show_for_context_menu(1)
                show_folder = repository / "beta"

                app._select_sequence_for_context_menu(1)
                sequence_folder = show_folder / "sequences" / "CCC"

                app._select_shot_for_context_menu(1)
                shot_folder = sequence_folder / "CCC_000_0040"

                with patch(
                    "portable_pipe_tools.apps.auto_comp_natron_app."
                    "open_folder_in_file_browser"
                ) as open_folder_mock:
                    app._open_selected_show_in_explorer()
                    app._open_selected_sequence_in_explorer()
                    app._open_selected_shot_in_explorer()

                self.assertEqual(
                    [call(show_folder), call(sequence_folder), call(shot_folder)],
                    open_folder_mock.call_args_list,
                )
                self.assertEqual(
                    "Opened shot folder: CCC_000_0040.",
                    app.status_var.get(),
                )
                self.assertEqual(
                    "StatusSuccess.TLabel",
                    app.status_label.cget("style"),
                )
            finally:
                app.root.destroy()

    def test_open_in_explorer_reports_a_missing_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            missing_folder = temporary_path / "missing-shot"

            try:
                with patch(
                    "portable_pipe_tools.apps.auto_comp_natron_app."
                    "open_folder_in_file_browser"
                ) as open_folder_mock:
                    app._open_folder_in_explorer(missing_folder, "shot")

                open_folder_mock.assert_not_called()
                self.assertEqual(
                    "Could not open shot folder because it does not exist: "
                    f"{missing_folder}",
                    app.status_var.get(),
                )
                self.assertEqual(
                    "StatusError.TLabel",
                    app.status_label.cget("style"),
                )
            finally:
                app.root.destroy()

    def test_create_comp_action_uses_current_show_sequence_and_shot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            target_path = (
                repository
                / "alpha"
                / "sequences"
                / "AAA"
                / "AAA_000_0010"
                / "comp"
                / "natron"
                / "AAA_000_0010_comp_v001.ntp"
            )
            result = CreateCompResult(
                target_path=target_path,
                template_path=Path("AAA template.ntp"),
                used_fallback_template=False,
            )

            try:
                app._set_repository_connected(repository)
                app.exr_var.set(False)
                app.mp4_var.set(True)
                app.mov_var.set(True)
                app.hero_var.set(False)
                with patch(
                    "portable_pipe_tools.apps.auto_comp_natron_app.create_comp",
                    return_value=result,
                ) as create_mock:
                    app._create_selected_comp()

                create_mock.assert_called_once_with(
                    repository / "alpha",
                    "AAA",
                    "AAA_000_0010",
                    smart_write_outputs=SmartWriteOutputOptions(
                        exr=False,
                        mp4=True,
                        mov=True,
                        hero=False,
                    ),
                )
                self.assertEqual(
                    "Create Comps complete — Succeeded: 1; Failed: 0.",
                    app.status_var.get(),
                )
                self.assertEqual(
                    "StatusSuccess.TLabel",
                    app.status_label.cget("style"),
                )
            finally:
                app.root.destroy()

    def test_existing_comp_action_reports_no_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            existing_path = Path("existing_comp.ntp")

            try:
                app._set_repository_connected(repository)
                with patch(
                    "portable_pipe_tools.apps.auto_comp_natron_app.create_comp",
                    side_effect=CompAlreadyExistsError(existing_path),
                ):
                    app._create_selected_comp()

                self.assertEqual(
                    "Create Comps complete — Succeeded: 0; Failed: 1. "
                    "Last failure: AAA_000_0010 already has a comp.",
                    app.status_var.get(),
                )
                self.assertEqual(
                    "StatusError.TLabel",
                    app.status_label.cget("style"),
                )
            finally:
                app.root.destroy()

    def test_create_comp_failure_uses_status_bar_without_popup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            missing_templates = (Path("AAA template.ntp"), Path("ZZZ template.ntp"))

            try:
                app._set_repository_connected(repository)
                with (
                    patch(
                        "portable_pipe_tools.apps.auto_comp_natron_app.create_comp",
                        side_effect=CompTemplateNotFoundError(missing_templates),
                    ),
                    patch(
                        "portable_pipe_tools.apps.auto_comp_natron_app.messagebox"
                    ) as messagebox_mock,
                ):
                    app._create_selected_comp()

                messagebox_mock.assert_not_called()
                self.assertEqual(
                    "Create Comps complete — Succeeded: 0; Failed: 1. "
                    "Last failure: no template was found for AAA_000_0010.",
                    app.status_var.get(),
                )
                self.assertEqual(
                    "StatusError.TLabel",
                    app.status_label.cget("style"),
                )
            finally:
                app.root.destroy()

    def test_multiple_selected_shots_are_processed_in_display_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            success_result = CreateCompResult(
                target_path=Path("AAA_000_0010_comp_v001.ntp"),
                template_path=Path("AAA template.ntp"),
                used_fallback_template=False,
            )

            try:
                app._set_repository_connected(repository)
                app.shot_list.selection_clear(0, "end")
                app.shot_list.selection_set(0, 1)
                with patch(
                    "portable_pipe_tools.apps.auto_comp_natron_app.create_comp",
                    side_effect=[
                        success_result,
                        CompAlreadyExistsError(Path("existing.ntp")),
                    ],
                ) as create_mock:
                    app._create_selected_comp()

                self.assertEqual(
                    [
                        call(
                            repository / "alpha",
                            "AAA",
                            "AAA_000_0010",
                            smart_write_outputs=SmartWriteOutputOptions(),
                        ),
                        call(
                            repository / "alpha",
                            "AAA",
                            "AAA_000_0020",
                            smart_write_outputs=SmartWriteOutputOptions(),
                        ),
                    ],
                    create_mock.call_args_list,
                )
                self.assertEqual(
                    "Create Comps complete — Succeeded: 1; Failed: 1. "
                    "Last failure: AAA_000_0020 already has a comp.",
                    app.status_var.get(),
                )
                self.assertEqual(
                    "StatusWarning.TLabel",
                    app.status_label.cget("style"),
                )
            finally:
                app.root.destroy()

    def test_context_click_on_selected_shot_preserves_multi_selection(self) -> None:
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
                app.shot_list.selection_clear(0, "end")
                app.shot_list.selection_set(0, 1)

                app._select_shot_for_context_menu(1)

                self.assertEqual((0, 1), app.shot_list.curselection())
            finally:
                app.root.destroy()

    def test_create_all_sequence_comps_processes_every_production_shot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            template_shot = (
                repository / "alpha" / "sequences" / "AAA" / "AAA_000_0000"
            )
            template_shot.mkdir()
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            success_result = CreateCompResult(
                target_path=Path("created.ntp"),
                template_path=Path("AAA template.ntp"),
                used_fallback_template=False,
            )

            try:
                app._set_repository_connected(repository)
                self.assertIn("AAA_000_0000", app.shot_names)
                with patch(
                    "portable_pipe_tools.apps.auto_comp_natron_app.create_comp",
                    return_value=success_result,
                ) as create_mock:
                    app._create_all_sequence_comps()

                self.assertEqual(
                    [
                        call(
                            repository / "alpha",
                            "AAA",
                            "AAA_000_0010",
                            smart_write_outputs=SmartWriteOutputOptions(),
                        ),
                        call(
                            repository / "alpha",
                            "AAA",
                            "AAA_000_0020",
                            smart_write_outputs=SmartWriteOutputOptions(),
                        ),
                    ],
                    create_mock.call_args_list,
                )
                self.assertEqual(
                    "Create All Comps for AAA complete — Succeeded: 2; Failed: 0.",
                    app.status_var.get(),
                )
                self.assertEqual(
                    "StatusSuccess.TLabel",
                    app.status_label.cget("style"),
                )
            finally:
                app.root.destroy()

    def test_create_and_open_targets_the_right_clicked_shot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            comp_path = Path("AAA_000_0020_comp_v001.ntp")
            executable = temporary_path / "Natron.exe"
            executable.touch()

            try:
                app._set_repository_connected(repository)
                app.natron_executable_path = executable
                app.shot_list.selection_clear(0, "end")
                app.shot_list.selection_set(0, 1)
                app._select_shot_for_context_menu(1)
                with patch(
                    "portable_pipe_tools.apps.auto_comp_natron_app."
                    "create_and_open_comp",
                    return_value=OpenCompResult(
                        comp_path=comp_path,
                        created=True,
                        hydrated_source_files=38,
                    ),
                ) as create_open_mock:
                    app._create_and_open_selected_comp()

                create_open_mock.assert_called_once_with(
                    repository / "alpha",
                    "AAA",
                    "AAA_000_0020",
                    smart_write_outputs=SmartWriteOutputOptions(),
                    natron_executable=executable,
                    hydration_progress=app._update_source_hydration_progress,
                )
                self.assertEqual(
                    "Downloaded 38 source frames. Successfully created and opened comp: "
                    "AAA_000_0020_comp_v001.ntp.",
                    app.status_var.get(),
                )
                self.assertEqual(
                    "StatusSuccess.TLabel",
                    app.status_label.cget("style"),
                )
            finally:
                app.root.destroy()

    def test_create_and_open_opens_existing_comp_without_create_message(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            executable = temporary_path / "Natron.exe"
            executable.touch()

            try:
                app._set_repository_connected(repository)
                app.natron_executable_path = executable
                with patch(
                    "portable_pipe_tools.apps.auto_comp_natron_app."
                    "create_and_open_comp",
                    return_value=OpenCompResult(
                        comp_path=Path("AAA_000_0010_comp_v001.ntp"),
                        created=False,
                    ),
                ):
                    app._create_and_open_selected_comp()

                self.assertEqual(
                    "Opened existing comp: AAA_000_0010_comp_v001.ntp.",
                    app.status_var.get(),
                )
            finally:
                app.root.destroy()

    def test_shot_names_show_whether_the_comp_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            comp_path = get_comp_path(
                repository / "alpha",
                "AAA",
                "AAA_000_0020",
            )
            comp_path.parent.mkdir(parents=True)
            comp_path.touch()
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()

            try:
                app._set_repository_connected(repository)

                self.assertEqual(
                    COMP_MISSING_COLOR,
                    str(app.shot_list.itemcget(0, "foreground")),
                )
                self.assertEqual(
                    COMP_PRESENT_COLOR,
                    str(app.shot_list.itemcget(1, "foreground")),
                )

                first_comp_path = get_comp_path(
                    repository / "alpha",
                    "AAA",
                    "AAA_000_0010",
                )
                first_comp_path.parent.mkdir(parents=True)
                first_comp_path.touch()
                selected_indexes = app.shot_list.curselection()

                app._refresh_shot_comp_colors()

                self.assertEqual(
                    COMP_PRESENT_COLOR,
                    str(app.shot_list.itemcget(0, "foreground")),
                )
                self.assertEqual(selected_indexes, app.shot_list.curselection())
            finally:
                app.root.destroy()

    def test_missing_comp_context_menu_only_offers_creation_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            comp_path = get_comp_path(
                repository / "alpha",
                "AAA",
                "AAA_000_0020",
            )
            comp_path.parent.mkdir(parents=True)
            comp_path.touch()
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            event = Mock(y=10, x_root=100, y_root=100)

            try:
                app._set_repository_connected(repository)
                with (
                    patch.object(app.shot_list, "nearest", return_value=0),
                    patch.object(
                        app.shot_list,
                        "bbox",
                        return_value=(0, 0, 100, 20),
                    ),
                    patch.object(app.shot_context_menu, "tk_popup"),
                ):
                    app._show_shot_context_menu(event)

                self.assertEqual(1, app.shot_context_menu.index("end"))
                self.assertEqual(
                    "Create Comp",
                    app.shot_context_menu.entrycget(0, "label"),
                )
                self.assertEqual(
                    "Create and Open Comp",
                    app.shot_context_menu.entrycget(1, "label"),
                )

                with (
                    patch.object(app.shot_list, "nearest", return_value=1),
                    patch.object(
                        app.shot_list,
                        "bbox",
                        return_value=(0, 0, 100, 20),
                    ),
                    patch.object(app.shot_context_menu, "tk_popup"),
                ):
                    app._show_shot_context_menu(event)

                self.assertEqual(6, app.shot_context_menu.index("end"))
                self.assertEqual(
                    "Open Comp",
                    app.shot_context_menu.entrycget(2, "label"),
                )
                self.assertEqual(
                    "Render Comp",
                    app.shot_context_menu.entrycget(3, "label"),
                )
                self.assertEqual(
                    "Add to Render Queue",
                    app.shot_context_menu.entrycget(4, "label"),
                )
            finally:
                app.root.destroy()

    def test_render_comp_targets_right_clicked_shot_and_reports_completion(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            executable = temporary_path / "Natron.exe"
            executable.touch()
            comp_path = Path("AAA_000_0020_comp_v001.ntp")
            render_result = RenderCompResult(
                comp_path=comp_path,
                process=Mock(),
                status_path=temporary_path / "status.json",
                hydrated_source_files=38,
            )
            completion = RenderCompCompletion(
                comp_path=comp_path,
                rendered_smart_writes=1,
                hydrated_source_files=38,
            )

            try:
                app._set_repository_connected(repository)
                app.natron_executable_path = executable
                app.shot_list.selection_clear(0, "end")
                app.shot_list.selection_set(0)
                app._select_shot_for_context_menu(1)
                with (
                    patch(
                        "portable_pipe_tools.apps.auto_comp_natron_app."
                        "render_comp",
                        return_value=render_result,
                    ) as render_mock,
                    patch(
                        "portable_pipe_tools.apps.auto_comp_natron_app."
                        "poll_render_comp",
                        return_value=completion,
                    ) as poll_mock,
                ):
                    app._render_selected_comp()

                render_mock.assert_called_once_with(
                    repository / "alpha",
                    "AAA",
                    "AAA_000_0020",
                    natron_executable=executable,
                    hydration_progress=app._update_source_hydration_progress,
                )
                poll_mock.assert_called_once_with(render_result)
                self.assertEqual(
                    "Downloaded 38 source frames. Successfully rendered comp: "
                    "AAA_000_0020_comp_v001.ntp.",
                    app.status_var.get(),
                )
                self.assertEqual(
                    "StatusSuccess.TLabel",
                    app.status_label.cget("style"),
                )
                queue_item = app.queue_tree.get_children()[0]
                self.assertEqual(
                    ("AAA / AAA_000_0020", "Complete"),
                    app.queue_tree.item(queue_item, "values"),
                )
                self.assertIsNone(app._active_render_job)
                self.assertIsNone(app._active_render_result)
            finally:
                app.root.destroy()

    def test_add_to_render_queue_adds_selected_shots_without_starting(self) -> None:
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
                app.shot_list.selection_clear(0, "end")
                app.shot_list.selection_set(0, 1)
                with (
                    patch.object(app, "_start_next_queued_render") as start_next,
                    patch(
                        "portable_pipe_tools.apps.auto_comp_natron_app."
                        "render_comp"
                    ) as render_mock,
                ):
                    app.shot_context_menu.invoke(4)

                start_next.assert_not_called()
                render_mock.assert_not_called()
                self.assertIsNone(app._active_render_job)
                self.assertEqual(
                    ["AAA_000_0010", "AAA_000_0020"],
                    [job.shot_name for job in app._pending_render_jobs],
                )
                self.assertEqual(
                    [
                        ("AAA / AAA_000_0010", "Queued"),
                        ("AAA / AAA_000_0020", "Queued"),
                    ],
                    [
                        app.queue_tree.item(item, "values")
                        for item in app.queue_tree.get_children()
                    ],
                )
                self.assertEqual("normal", str(app.resume_queue_button["state"]))
                self.assertEqual(
                    "Added 2 comps to the render queue.",
                    app.status_var.get(),
                )
                original_items = app.queue_tree.get_children()
                app.shot_context_menu.invoke(4)
                self.assertEqual(original_items, app.queue_tree.get_children())
                self.assertEqual(2, len(app._pending_render_jobs))
                self.assertEqual(
                    "The selected comps are already in the render queue.",
                    app.status_var.get(),
                )

                with (
                    patch.object(
                        app,
                        "_ensure_natron_executable",
                        return_value=True,
                    ) as ensure_natron,
                    patch.object(app, "_start_next_queued_render") as start_next,
                ):
                    app.resume_queue_button.invoke()

                ensure_natron.assert_called_once_with()
                start_next.assert_called_once_with()
            finally:
                app.root.destroy()

    def test_render_queue_mixed_selection_skips_only_duplicate_shots(self) -> None:
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
                app.shot_list.selection_clear(0, "end")
                app.shot_list.selection_set(0)
                app._add_selected_comps_to_render_queue()
                app.shot_list.selection_set(1)
                app._add_selected_comps_to_render_queue()

                self.assertEqual(
                    ["AAA_000_0010", "AAA_000_0020"],
                    [job.shot_name for job in app._pending_render_jobs],
                )
                self.assertEqual(2, len(app.queue_tree.get_children()))
                self.assertEqual(
                    "Added 1 comp to the render queue. Skipped 1 duplicate.",
                    app.status_var.get(),
                )
            finally:
                app.root.destroy()

    def test_closing_app_terminates_the_active_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            result = RenderCompResult(
                comp_path=Path("comp.ntp"),
                process=Mock(),
                status_path=temporary_path / "status.json",
            )
            app._active_render_result = result

            with (
                patch(
                    "portable_pipe_tools.apps.auto_comp_natron_app."
                    "terminate_render_comp"
                ) as terminate,
                patch.object(app.root, "destroy") as destroy,
            ):
                app._close()

            terminate.assert_called_once_with(result)
            self.assertIsNone(app._active_render_result)
            destroy.assert_called_once_with()
            app.root.destroy()

    def test_render_comp_queues_multiple_selected_shots_in_display_order(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            executable = temporary_path / "Natron.exe"
            executable.touch()
            first_path = Path("AAA_000_0010_comp_v001.ntp")
            second_path = Path("AAA_000_0020_comp_v001.ntp")
            render_results = [
                RenderCompResult(
                    comp_path=path,
                    process=Mock(),
                    status_path=temporary_path / f"status-{index}.json",
                )
                for index, path in enumerate((first_path, second_path), start=1)
            ]
            completions = [
                RenderCompCompletion(
                    comp_path=path,
                    rendered_smart_writes=1,
                )
                for path in (first_path, second_path)
            ]

            try:
                app._set_repository_connected(repository)
                app.natron_executable_path = executable
                app.shot_list.selection_clear(0, "end")
                app.shot_list.selection_set(0, 1)
                with (
                    patch(
                        "portable_pipe_tools.apps.auto_comp_natron_app."
                        "render_comp",
                        side_effect=render_results,
                    ) as render_mock,
                    patch(
                        "portable_pipe_tools.apps.auto_comp_natron_app."
                        "poll_render_comp",
                        side_effect=completions,
                    ) as poll_mock,
                ):
                    app._render_selected_comp()

                self.assertEqual(
                    [
                        call(
                            repository / "alpha",
                            "AAA",
                            "AAA_000_0010",
                            natron_executable=executable,
                            hydration_progress=app._update_source_hydration_progress,
                        ),
                        call(
                            repository / "alpha",
                            "AAA",
                            "AAA_000_0020",
                            natron_executable=executable,
                            hydration_progress=app._update_source_hydration_progress,
                        ),
                    ],
                    render_mock.call_args_list,
                )
                self.assertEqual(
                    [call(render_results[0]), call(render_results[1])],
                    poll_mock.call_args_list,
                )
                self.assertEqual(
                    [
                        ("AAA / AAA_000_0010", "Complete"),
                        ("AAA / AAA_000_0020", "Complete"),
                    ],
                    [
                        app.queue_tree.item(item, "values")
                        for item in app.queue_tree.get_children()
                    ],
                )
                self.assertEqual([], app._pending_render_jobs)
                self.assertIsNone(app._active_render_job)

                app.clear_queue_button.invoke()

                self.assertEqual((), app.queue_tree.get_children())
                self.assertEqual("Cleared 2 queue entries.", app.status_var.get())
            finally:
                app.root.destroy()

    def test_clear_queue_cancels_active_render_and_removes_every_job(self) -> None:
        app = AutoCompNatronApp(prompt_on_startup=False)
        app.root.withdraw()

        try:
            active_item_id = app.queue_tree.insert(
                "",
                "end",
                values=("AAA / AAA_000_0010", "Rendering"),
                tags=("rendering",),
            )
            waiting_item_id = app.queue_tree.insert(
                "",
                "end",
                values=("AAA / AAA_000_0020", "Queued"),
                tags=("queued",),
            )
            active_job = RenderQueueJob(
                show_path=Path("alpha"),
                sequence_name="AAA",
                shot_name="AAA_000_0010",
                tree_item_id=active_item_id,
            )
            waiting_job = RenderQueueJob(
                show_path=Path("alpha"),
                sequence_name="AAA",
                shot_name="AAA_000_0020",
                tree_item_id=waiting_item_id,
            )
            render_result = RenderCompResult(
                comp_path=Path("AAA_000_0010_comp_v001.ntp"),
                process=Mock(),
                status_path=Path("status.json"),
            )
            app._active_render_job = active_job
            app._active_render_result = render_result
            app._pending_render_jobs.append(waiting_job)
            app._queue_paused = True
            app._update_queue_pause_controls()

            with patch(
                "portable_pipe_tools.apps.auto_comp_natron_app."
                "terminate_render_comp",
                return_value=True,
            ) as terminate_mock:
                app.clear_queue_button.invoke()

            terminate_mock.assert_called_once_with(render_result)
            self.assertEqual((), app.queue_tree.get_children())
            self.assertEqual([], app._pending_render_jobs)
            self.assertIsNone(app._active_render_job)
            self.assertIsNone(app._active_render_result)
            self.assertFalse(app._queue_paused)
            self.assertIsNone(app._render_progress_job)
            self.assertEqual("normal", str(app.pause_queue_button["state"]))
            self.assertEqual("disabled", str(app.resume_queue_button["state"]))
            self.assertEqual(
                "Cancelled the active render and cleared 2 queue entries.",
                app.status_var.get(),
            )

            with (
                patch(
                    "portable_pipe_tools.apps.auto_comp_natron_app."
                    "read_render_comp_progress"
                ) as read_progress,
                patch(
                    "portable_pipe_tools.apps.auto_comp_natron_app."
                    "poll_render_comp"
                ) as poll_render,
            ):
                app._poll_render_result(render_result, active_job)

            read_progress.assert_not_called()
            poll_render.assert_not_called()
        finally:
            app.root.destroy()

    def test_render_queue_waits_for_active_job_before_starting_next(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            executable = temporary_path / "Natron.exe"
            executable.touch()
            paths = [
                Path("AAA_000_0010_comp_v001.ntp"),
                Path("AAA_000_0020_comp_v001.ntp"),
            ]
            render_results = [
                RenderCompResult(
                    comp_path=path,
                    process=Mock(),
                    status_path=temporary_path / f"status-{index}.json",
                )
                for index, path in enumerate(paths, start=1)
            ]
            completions = [
                RenderCompCompletion(
                    comp_path=path,
                    rendered_smart_writes=1,
                )
                for path in paths
            ]

            try:
                app._set_repository_connected(repository)
                app.natron_executable_path = executable
                app.shot_list.selection_clear(0, "end")
                app.shot_list.selection_set(0, 1)
                with (
                    patch(
                        "portable_pipe_tools.apps.auto_comp_natron_app."
                        "render_comp",
                        side_effect=render_results,
                    ) as render_mock,
                    patch(
                        "portable_pipe_tools.apps.auto_comp_natron_app."
                        "poll_render_comp",
                        side_effect=[None, *completions],
                    ),
                    patch.object(app.root, "after") as after_mock,
                ):
                    app._render_selected_comp()

                    self.assertEqual(1, render_mock.call_count)
                    self.assertEqual(
                        ["Rendering", "Queued"],
                        [
                            app.queue_tree.item(item, "values")[1]
                            for item in app.queue_tree.get_children()
                        ],
                    )
                    after_mock.assert_called_once()
                    self.assertEqual(250, after_mock.call_args.args[0])

                    poll_again = after_mock.call_args.args[1]
                    poll_again()

                self.assertEqual(2, render_mock.call_count)
                self.assertEqual(
                    ["Complete", "Complete"],
                    [
                        app.queue_tree.item(item, "values")[1]
                        for item in app.queue_tree.get_children()
                    ],
                )
            finally:
                app.root.destroy()

    def test_live_progress_bar_belongs_only_to_the_active_queue_job(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            executable = temporary_path / "Natron.exe"
            executable.touch()
            render_result = RenderCompResult(
                comp_path=Path("AAA_000_0010_comp_v001.ntp"),
                process=Mock(),
                status_path=temporary_path / "status.json",
            )
            progress = RenderCompProgress(
                completed_frames=37,
                total_frames=100,
                percent=37.0,
                current_frame=1037,
            )

            try:
                app._set_repository_connected(repository)
                app.natron_executable_path = executable
                app.shot_list.selection_clear(0, "end")
                app.shot_list.selection_set(0, 1)
                with (
                    patch(
                        "portable_pipe_tools.apps.auto_comp_natron_app."
                        "render_comp",
                        return_value=render_result,
                    ),
                    patch(
                        "portable_pipe_tools.apps.auto_comp_natron_app."
                        "read_render_comp_progress",
                        return_value=progress,
                    ),
                    patch(
                        "portable_pipe_tools.apps.auto_comp_natron_app."
                        "poll_render_comp",
                        return_value=None,
                    ),
                    patch.object(app.root, "after"),
                ):
                    app._render_selected_comp()

                items = app.queue_tree.get_children()
                self.assertEqual(2, len(items))
                self.assertEqual(
                    "Rendering — 37%",
                    app.queue_tree.item(items[0], "values")[1],
                )
                self.assertEqual(
                    "Queued",
                    app.queue_tree.item(items[1], "values")[1],
                )
                self.assertIsNotNone(app._render_progress_job)
                self.assertEqual(
                    items[0],
                    app._render_progress_job.tree_item_id,
                )
                self.assertEqual(37.0, app._render_progress_percent)
                regressed = RenderCompProgress(
                    completed_frames=12,
                    total_frames=100,
                    percent=12.0,
                    current_frame=1012,
                )
                app._update_render_progress(app._active_render_job, regressed)
                self.assertEqual(
                    "Rendering — 37%",
                    app.queue_tree.item(items[0], "values")[1],
                )
                self.assertEqual(37.0, app._render_progress_percent)
                self.assertIn("37/100 writer-frames", app.status_var.get())
                finalizing = RenderCompProgress(
                    completed_frames=100,
                    total_frames=100,
                    percent=99.0,
                    current_frame=1100,
                    completed_outputs=3,
                    total_outputs=3,
                    finalizing=True,
                )
                app._update_render_progress(app._active_render_job, finalizing)
                self.assertEqual(
                    "Finalizing — 99%",
                    app.queue_tree.item(items[0], "values")[1],
                )
                self.assertEqual(
                    1,
                    sum(
                        child.winfo_class() == "Canvas"
                        for child in app.queue_tree.winfo_children()
                    ),
                )
            finally:
                app.root.destroy()

    def test_pause_and_resume_buttons_control_the_active_natron_renderer(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            item_id = app.queue_tree.insert(
                "",
                "end",
                values=("AAA / AAA_000_0010", "Rendering — 42%"),
            )
            job = RenderQueueJob(
                show_path=temporary_path,
                sequence_name="AAA",
                shot_name="AAA_000_0010",
                tree_item_id=item_id,
            )
            result = RenderCompResult(
                comp_path=Path("AAA_000_0010_comp_v001.ntp"),
                process=Mock(),
                status_path=temporary_path / "status.json",
            )
            app._active_render_job = job
            app._active_render_result = result
            app._show_render_progress(job, 42.0)

            try:
                with (
                    patch(
                        "portable_pipe_tools.apps.auto_comp_natron_app."
                        "pause_render_comp",
                        return_value=True,
                    ) as pause_mock,
                    patch(
                        "portable_pipe_tools.apps.auto_comp_natron_app."
                        "resume_render_comp",
                        return_value=True,
                    ) as resume_mock,
                ):
                    app.pause_queue_button.invoke()
                    self.assertTrue(app._queue_paused)
                    pause_mock.assert_called_once_with(result)
                    self.assertEqual(
                        "Paused — 42%",
                        app.queue_tree.item(item_id, "values")[1],
                    )
                    self.assertEqual(
                        "disabled",
                        str(app.pause_queue_button["state"]),
                    )
                    self.assertEqual(
                        "normal",
                        str(app.resume_queue_button["state"]),
                    )

                    app.resume_queue_button.invoke()
                    self.assertFalse(app._queue_paused)
                    resume_mock.assert_called_once_with(result)
                    self.assertEqual(
                        "Rendering — 42%",
                        app.queue_tree.item(item_id, "values")[1],
                    )
                    self.assertEqual(
                        "normal",
                        str(app.pause_queue_button["state"]),
                    )
                    self.assertEqual(
                        "disabled",
                        str(app.resume_queue_button["state"]),
                    )
            finally:
                app.root.destroy()

    def test_paused_queue_does_not_start_its_next_pending_render(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            item_id = app.queue_tree.insert(
                "",
                "end",
                values=("AAA / AAA_000_0010", "Queued"),
            )
            job = RenderQueueJob(
                show_path=temporary_path,
                sequence_name="AAA",
                shot_name="AAA_000_0010",
                tree_item_id=item_id,
            )
            app._pending_render_jobs.append(job)
            app._queue_paused = True

            try:
                with patch(
                    "portable_pipe_tools.apps.auto_comp_natron_app.render_comp"
                ) as render_mock:
                    app._start_next_queued_render()

                render_mock.assert_not_called()
                self.assertEqual([job], app._pending_render_jobs)
                self.assertIsNone(app._active_render_job)
            finally:
                app.root.destroy()

    def test_queue_context_menu_removes_the_right_clicked_pending_job(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            first_item = app.queue_tree.insert(
                "",
                "end",
                values=("AAA / AAA_000_0010", "Queued"),
            )
            second_item = app.queue_tree.insert(
                "",
                "end",
                values=("AAA / AAA_000_0020", "Queued"),
            )
            first_job = RenderQueueJob(
                show_path=temporary_path,
                sequence_name="AAA",
                shot_name="AAA_000_0010",
                tree_item_id=first_item,
            )
            second_job = RenderQueueJob(
                show_path=temporary_path,
                sequence_name="AAA",
                shot_name="AAA_000_0020",
                tree_item_id=second_item,
            )
            app._pending_render_jobs.extend([first_job, second_job])
            event = Mock(y=10, x_root=100, y_root=100)

            try:
                with (
                    patch.object(
                        app.queue_tree,
                        "identify_row",
                        return_value=first_item,
                    ),
                    patch.object(app.queue_context_menu, "tk_popup") as popup,
                ):
                    self.assertEqual(
                        "break",
                        app._show_render_queue_context_menu(event),
                    )

                self.assertEqual((first_item,), app.queue_tree.selection())
                popup.assert_called_once_with(100, 100)
                app.queue_context_menu.invoke(0)
                self.assertFalse(app.queue_tree.exists(first_item))
                self.assertTrue(app.queue_tree.exists(second_item))
                self.assertEqual([second_job], app._pending_render_jobs)
                self.assertEqual(
                    "Removed AAA / AAA_000_0010 from the render queue.",
                    app.status_var.get(),
                )
            finally:
                app.root.destroy()

    def test_active_render_context_action_cancels_and_keeps_a_red_row(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            item_id = app.queue_tree.insert(
                "",
                "end",
                values=("AAA / AAA_000_0010", "Rendering"),
            )
            job = RenderQueueJob(
                show_path=temporary_path,
                sequence_name="AAA",
                shot_name="AAA_000_0010",
                tree_item_id=item_id,
            )
            result = RenderCompResult(
                comp_path=Path("AAA_000_0010_comp_v001.ntp"),
                process=Mock(),
                status_path=temporary_path / "status.json",
            )
            app._active_render_job = job
            app._active_render_result = result
            app._show_render_progress(job, 42.0)
            event = Mock(y=10, x_root=100, y_root=100)

            try:
                with (
                    patch.object(
                        app.queue_tree,
                        "identify_row",
                        return_value=item_id,
                    ),
                    patch.object(app.queue_context_menu, "tk_popup"),
                ):
                    app._show_render_queue_context_menu(event)

                self.assertEqual(
                    "Cancel Render",
                    app.queue_context_menu.entrycget(0, "label"),
                )
                self.assertEqual(
                    "normal",
                    str(app.queue_context_menu.entrycget(0, "state")),
                )
                with (
                    patch(
                        "portable_pipe_tools.apps.auto_comp_natron_app."
                        "terminate_render_comp",
                        return_value=True,
                    ) as terminate_mock,
                    patch.object(app, "_start_next_queued_render") as start_next,
                ):
                    app.queue_context_menu.invoke(0)

                terminate_mock.assert_called_once_with(result)
                start_next.assert_called_once_with()
                self.assertTrue(app.queue_tree.exists(item_id))
                self.assertEqual(
                    ("AAA / AAA_000_0010", "Canceled"),
                    app.queue_tree.item(item_id, "values"),
                )
                self.assertEqual(
                    ("canceled",),
                    app.queue_tree.item(item_id, "tags"),
                )
                self.assertEqual(
                    "#ff7b72",
                    str(
                        app.queue_tree.tag_configure(
                            "canceled",
                            "foreground",
                        )
                    ),
                )
                self.assertIsNone(app._active_render_job)
                self.assertIsNone(app._active_render_result)
                self.assertIsNone(app._render_progress_job)
                self.assertEqual(
                    "Canceled render: AAA_000_0010.",
                    app.status_var.get(),
                )
            finally:
                app.root.destroy()

    def test_render_comp_reports_missing_smart_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            executable = temporary_path / "Natron.exe"
            executable.touch()
            comp_path = Path("AAA_000_0010_comp_v001.ntp")

            try:
                app._set_repository_connected(repository)
                app.natron_executable_path = executable
                with patch(
                    "portable_pipe_tools.apps.auto_comp_natron_app.render_comp",
                    side_effect=SmartWriteNotFoundError(comp_path),
                ):
                    app._render_selected_comp()

                self.assertIn(
                    "Failed to render comp for AAA_000_0010: No SmartWrite node",
                    app.status_var.get(),
                )
                self.assertEqual(
                    "StatusError.TLabel",
                    app.status_label.cget("style"),
                )
                queue_item = app.queue_tree.get_children()[0]
                self.assertEqual(
                    ("AAA / AAA_000_0010", "Failed"),
                    app.queue_tree.item(queue_item, "values"),
                )
            finally:
                app.root.destroy()

    def test_open_comp_uses_active_shot_and_reports_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "repository"
            _create_test_repository(repository)
            app = AutoCompNatronApp(
                settings_path=temporary_path / "settings.json",
                prompt_on_startup=False,
            )
            app.root.withdraw()
            missing_path = Path("AAA_000_0010_comp_v001.ntp")
            executable = temporary_path / "Natron.exe"
            executable.touch()

            try:
                app._set_repository_connected(repository)
                app.natron_executable_path = executable
                with patch(
                    "portable_pipe_tools.apps.auto_comp_natron_app.open_comp",
                    side_effect=CompNotFoundError(missing_path),
                ) as open_mock:
                    app._open_selected_comp()

                open_mock.assert_called_once_with(
                    repository / "alpha",
                    "AAA",
                    "AAA_000_0010",
                    natron_executable=executable,
                    hydration_progress=app._update_source_hydration_progress,
                )
                self.assertIn("does not exist", app.status_var.get())
                self.assertEqual(
                    "StatusError.TLabel",
                    app.status_label.cget("style"),
                )
            finally:
                app.root.destroy()


if __name__ == "__main__":
    unittest.main()
