from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from portable_pipe_tools.auto_comp_natron.create_comp import (
    CompAlreadyExistsError,
    CompTemplateNotFoundError,
    create_comp,
)
from portable_pipe_tools.auto_comp_natron.open_comp import (
    CompNotFoundError,
    create_and_open_comp,
    open_comp,
)
from portable_pipe_tools.auto_comp_natron.settings import (
    get_default_settings_path,
    load_saved_browser_selection,
    load_saved_repository_folder,
    save_browser_selection,
    save_repository_folder,
)
from portable_pipe_tools.show_manager.shot_manager_core import (
    ShotRow,
    find_sequence_folders,
    find_shot_folders,
    find_show_folders,
)


WINDOW_BACKGROUND = "#252629"
PANEL_BACKGROUND = "#2d2f32"
PANEL_HEADER = "#3b3d40"
TOOLBAR_BACKGROUND = "#333538"
BORDER_COLOR = "#161719"
TEXT_COLOR = "#d8dadd"
MUTED_TEXT = "#a5a9ae"
SELECTION_COLOR = "#315f7a"

class AutoCompNatronApp:
    """Natron auto-comp GUI shell with a locally saved repository connection."""

    def __init__(
        self,
        settings_path: Path | None = None,
        prompt_on_startup: bool = True,
    ) -> None:
        self.root = tk.Tk()
        self.root.title("Auto Comp - Natron")
        self.root.geometry("1040x680")
        self.root.minsize(780, 520)

        self.settings_path = settings_path or get_default_settings_path()
        self.repository_path: Path | None = None
        self.repository_status_var = tk.StringVar(
            value="Repository Connected: No"
        )
        self.status_var = tk.StringVar(value="Ready")
        self.show_names: list[str] = []
        self.show_paths_by_name: dict[str, Path] = {}
        self.sequence_names: list[str] = []
        self.sequence_paths_by_name: dict[str, Path] = {}
        self.shot_names: list[str] = []
        self.shot_rows_by_name: dict[str, ShotRow] = {}
        self.hero_var = tk.BooleanVar(value=True)
        self.exr_var = tk.BooleanVar(value=True)

        self._configure_styles()
        self._build_menu()
        self._build_ui()
        if prompt_on_startup:
            self.root.after_idle(self._initialize_repository)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.root.configure(background=WINDOW_BACKGROUND)
        self.root.option_add("*Font", ("Segoe UI", 10))

        style.configure("App.TFrame", background=WINDOW_BACKGROUND)
        style.configure("Toolbar.TFrame", background=TOOLBAR_BACKGROUND)
        style.configure("Panel.TFrame", background=PANEL_BACKGROUND)
        style.configure("PanelHeader.TFrame", background=PANEL_HEADER)
        style.configure(
            "ToolbarTitle.TLabel",
            background=TOOLBAR_BACKGROUND,
            foreground="#f0f1f2",
            font=("Segoe UI", 14, "bold"),
        )
        style.configure(
            "ToolbarSubtitle.TLabel",
            background=TOOLBAR_BACKGROUND,
            foreground=MUTED_TEXT,
            font=("Segoe UI", 9),
        )
        style.configure(
            "NatronBadge.TLabel",
            background="#4d7651",
            foreground="#ffffff",
            font=("Segoe UI", 8, "bold"),
            padding=(8, 3),
        )
        style.configure(
            "RepositoryDisconnected.TLabel",
            background=TOOLBAR_BACKGROUND,
            foreground="#b8bbc0",
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "RepositoryConnected.TLabel",
            background=TOOLBAR_BACKGROUND,
            foreground="#74d680",
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "RepositoryUnavailable.TLabel",
            background=TOOLBAR_BACKGROUND,
            foreground="#ffb45f",
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "Toolbar.TButton",
            background="#45484c",
            foreground=TEXT_COLOR,
            bordercolor=BORDER_COLOR,
            lightcolor="#56595d",
            darkcolor=BORDER_COLOR,
            padding=(9, 4),
        )
        style.map(
            "Toolbar.TButton",
            background=[("active", "#55585c"), ("pressed", "#292b2e")],
        )
        style.configure(
            "PanelTitle.TLabel",
            background=PANEL_HEADER,
            foreground=TEXT_COLOR,
            font=("Segoe UI", 13, "bold"),
        )
        style.configure(
            "Option.TCheckbutton",
            background=PANEL_BACKGROUND,
            foreground=TEXT_COLOR,
            indicatorbackground="#202124",
            indicatorforeground="#74d680",
            bordercolor=BORDER_COLOR,
            padding=(2, 5),
            font=("Segoe UI", 10),
        )
        style.map(
            "Option.TCheckbutton",
            background=[("active", PANEL_BACKGROUND)],
            foreground=[("active", "#ffffff")],
        )
        style.configure(
            "Status.TLabel",
            background=TOOLBAR_BACKGROUND,
            foreground=MUTED_TEXT,
            font=("Segoe UI", 9),
        )
        style.configure(
            "StatusSuccess.TLabel",
            background=TOOLBAR_BACKGROUND,
            foreground="#74d680",
            font=("Segoe UI", 9),
        )
        style.configure(
            "StatusWarning.TLabel",
            background=TOOLBAR_BACKGROUND,
            foreground="#ffb45f",
            font=("Segoe UI", 9),
        )
        style.configure(
            "StatusError.TLabel",
            background=TOOLBAR_BACKGROUND,
            foreground="#ff7b72",
            font=("Segoe UI", 9),
        )

    def _build_menu(self) -> None:
        menu_options = {
            "background": "#303236",
            "foreground": TEXT_COLOR,
            "activebackground": SELECTION_COLOR,
            "activeforeground": "#ffffff",
            "borderwidth": 0,
        }
        menu_bar = tk.Menu(self.root, **menu_options)
        file_menu = tk.Menu(menu_bar, tearoff=False, **menu_options)
        file_menu.add_command(
            label="Change Repository Folder...",
            command=self._browse_repository_folder,
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        menu_bar.add_cascade(label="File", menu=file_menu)
        self.root.configure(menu=menu_bar)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, style="App.TFrame")
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        self._build_toolbar(outer)

        workspace = ttk.Frame(outer, style="App.TFrame", padding=(16, 16, 16, 16))
        workspace.grid(row=1, column=0, sticky="nsew")
        for column in range(3):
            workspace.columnconfigure(column, weight=1, uniform="browser-panel")
        workspace.rowconfigure(0, weight=3)
        workspace.rowconfigure(1, weight=1)

        self.show_list = self._create_browser_panel(
            workspace,
            column=0,
            title="Show",
            right_padding=5,
        )
        self.show_list.bind("<<ListboxSelect>>", self._on_show_selected)
        self.sequence_list = self._create_browser_panel(
            workspace,
            column=1,
            title="Sequence",
            left_padding=5,
            right_padding=5,
        )
        self.sequence_list.bind("<<ListboxSelect>>", self._on_sequence_selected)
        self.sequence_list.bind("<Button-3>", self._show_sequence_context_menu)

        self.sequence_context_menu = tk.Menu(
            self.root,
            tearoff=False,
            background="#303236",
            foreground=TEXT_COLOR,
            activebackground=SELECTION_COLOR,
            activeforeground="#ffffff",
            borderwidth=0,
        )
        self.sequence_context_menu.add_command(
            label="Create All Comps",
            command=self._create_all_sequence_comps,
        )

        self.shot_list = self._create_browser_panel(
            workspace,
            column=2,
            title="Shot",
            left_padding=5,
            selectmode=tk.EXTENDED,
        )
        self.shot_list.bind("<<ListboxSelect>>", self._on_shot_selected)
        self.shot_list.bind("<Button-3>", self._show_shot_context_menu)

        self.shot_context_menu = tk.Menu(
            self.root,
            tearoff=False,
            background="#303236",
            foreground=TEXT_COLOR,
            activebackground=SELECTION_COLOR,
            activeforeground="#ffffff",
            borderwidth=0,
        )
        self.shot_context_menu.add_command(
            label="Create Comp",
            command=self._create_selected_comp,
        )
        self.shot_context_menu.add_command(
            label="Create and Open Comp",
            command=self._create_and_open_selected_comp,
        )
        self.shot_context_menu.add_command(
            label="Open Comp",
            command=self._open_selected_comp,
        )

        self._build_options_panel(workspace)
        self._build_status_bar(outer)

    def _build_status_bar(self, parent: ttk.Frame) -> None:
        status_bar = ttk.Frame(
            parent,
            style="Toolbar.TFrame",
            padding=(12, 6),
        )
        status_bar.grid(row=2, column=0, sticky="ew")
        status_bar.columnconfigure(0, weight=1)
        self.status_label = ttk.Label(
            status_bar,
            textvariable=self.status_var,
            style="Status.TLabel",
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, sticky="ew")

    def _build_toolbar(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent, style="Toolbar.TFrame", padding=(16, 10))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(1, weight=1)

        ttk.Label(
            toolbar,
            text="Auto Comp",
            style="ToolbarTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            toolbar,
            text="Browse a show, sequence, and shot to prepare a comp",
            style="ToolbarSubtitle.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(1, 0))

        self.repository_button = ttk.Button(
            toolbar,
            text="Repository...",
            style="Toolbar.TButton",
            command=self._browse_repository_folder,
        )
        self.repository_button.grid(
            row=0,
            column=2,
            rowspan=2,
            sticky="e",
            padx=(8, 12),
        )

        self.repository_status_label = ttk.Label(
            toolbar,
            textvariable=self.repository_status_var,
            style="RepositoryDisconnected.TLabel",
        )
        self.repository_status_label.grid(
            row=0,
            column=3,
            rowspan=2,
            sticky="e",
            padx=(0, 14),
        )

        ttk.Label(
            toolbar,
            text="NATRON",
            style="NatronBadge.TLabel",
        ).grid(row=0, column=4, rowspan=2, sticky="e")

    def _initialize_repository(self) -> None:
        saved_folder = load_saved_repository_folder(self.settings_path)
        if saved_folder:
            saved_path = Path(saved_folder).expanduser()
            if saved_path.is_dir():
                self._set_repository_connected(saved_path)
            else:
                self.repository_path = None
                self.repository_status_var.set("Repository Connected: No")
                self.repository_status_label.configure(
                    style="RepositoryUnavailable.TLabel"
                )
            return

        self._browse_repository_folder(first_startup=True)

    def _browse_repository_folder(self, first_startup: bool = False) -> None:
        title = (
            "First Time Setup - Choose Repository Folder"
            if first_startup
            else "Choose Repository Folder"
        )
        initial_directory = (
            str(self.repository_path)
            if self.repository_path and self.repository_path.is_dir()
            else None
        )
        selected = filedialog.askdirectory(
            title=title,
            initialdir=initial_directory,
            mustexist=True,
            parent=self.root,
        )
        if not selected:
            return

        selected_path = Path(selected).expanduser()
        if not selected_path.is_dir():
            messagebox.showerror(
                "Auto Comp - Natron",
                f"The selected repository folder does not exist:\n{selected_path}",
                parent=self.root,
            )
            return

        try:
            save_repository_folder(selected_path, self.settings_path)
        except Exception as error:
            messagebox.showerror(
                "Auto Comp - Natron",
                f"Could not save the local configuration:\n{error}",
                parent=self.root,
            )
            return

        self._set_repository_connected(selected_path)

    def _set_repository_connected(self, repository_folder: Path) -> None:
        self.repository_path = repository_folder
        self.repository_status_var.set("Repository Connected: Yes")
        self.repository_status_label.configure(style="RepositoryConnected.TLabel")
        self.repository_button.configure(text="Change Repository...")
        self._populate_shows()

    def _populate_shows(self) -> None:
        if self.repository_path is None:
            self._clear_browser()
            return

        try:
            show_folders = find_show_folders(self.repository_path)
        except Exception as error:
            self._clear_browser()
            messagebox.showerror(
                "Auto Comp - Natron",
                f"Could not read the repository:\n{error}",
                parent=self.root,
            )
            return

        saved_show, saved_sequence, saved_shot = load_saved_browser_selection(
            self.settings_path
        )
        self.show_paths_by_name = {
            show_info.name: show_info.show_root for show_info in show_folders
        }
        self.show_names = list(self.show_paths_by_name)
        self._replace_list_values(self.show_list, self.show_names)

        selected_show = self._preferred_value(saved_show, self.show_names)
        if selected_show:
            self._select_list_value(self.show_list, self.show_names, selected_show)
            self._populate_sequences(
                preferred_sequence=saved_sequence,
                preferred_shot=saved_shot,
            )
        else:
            self._clear_sequences_and_shots()
        self._save_current_selection()

    def _populate_sequences(
        self,
        preferred_sequence: str = "",
        preferred_shot: str = "",
    ) -> None:
        show_path = self._selected_show_path()
        if show_path is None:
            self._clear_sequences_and_shots()
            return

        sequence_folders = find_sequence_folders(show_path)
        self.sequence_paths_by_name = {
            sequence_path.name.upper(): sequence_path
            for sequence_path in sequence_folders
        }
        self.sequence_names = list(self.sequence_paths_by_name)
        self._replace_list_values(self.sequence_list, self.sequence_names)

        selected_sequence = self._preferred_value(
            preferred_sequence,
            self.sequence_names,
        )
        if selected_sequence:
            self._select_list_value(
                self.sequence_list,
                self.sequence_names,
                selected_sequence,
            )
            self._populate_shots(preferred_shot)
        else:
            self._clear_shots()

    def _populate_shots(self, preferred_shot: str = "") -> None:
        show_path = self._selected_show_path()
        sequence_name = self._selected_value(
            self.sequence_list,
            self.sequence_names,
        )
        if show_path is None or not sequence_name:
            self._clear_shots()
            return

        try:
            shot_rows = find_shot_folders(show_path, sequence_name)
        except Exception as error:
            self._clear_shots()
            messagebox.showerror(
                "Auto Comp - Natron",
                f"Could not read shots for {sequence_name}:\n{error}",
                parent=self.root,
            )
            return

        self.shot_rows_by_name = {
            shot_row.shot_name: shot_row for shot_row in shot_rows
        }
        self.shot_names = list(self.shot_rows_by_name)
        self._replace_list_values(self.shot_list, self.shot_names)

        selected_shot = self._preferred_value(preferred_shot, self.shot_names)
        if selected_shot:
            self._select_list_value(
                self.shot_list,
                self.shot_names,
                selected_shot,
            )

    def _on_show_selected(self, _event: tk.Event | None) -> None:
        if not self._selected_value(self.show_list, self.show_names):
            return
        self._populate_sequences()
        self._save_current_selection()

    def _on_sequence_selected(self, _event: tk.Event | None) -> None:
        if not self._selected_value(self.sequence_list, self.sequence_names):
            return
        self._populate_shots()
        self._save_current_selection()

    def _on_shot_selected(self, _event: tk.Event | None) -> None:
        if not self._selected_value(self.shot_list, self.shot_names):
            return
        self._save_current_selection()

    def _show_sequence_context_menu(self, event: tk.Event) -> str:
        if not self.sequence_names:
            return "break"
        index = self.sequence_list.nearest(event.y)
        row_bounds = self.sequence_list.bbox(index)
        if row_bounds is None:
            return "break"
        _x, row_y, _width, row_height = row_bounds
        if not row_y <= event.y < row_y + row_height:
            return "break"

        self._select_sequence_for_context_menu(index)
        try:
            self.sequence_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.sequence_context_menu.grab_release()
        return "break"

    def _select_sequence_for_context_menu(self, index: int) -> None:
        self.sequence_list.selection_clear(0, tk.END)
        self.sequence_list.selection_set(index)
        self.sequence_list.activate(index)
        self._on_sequence_selected(None)

    def _show_shot_context_menu(self, event: tk.Event) -> str:
        if not self.shot_names:
            return "break"
        index = self.shot_list.nearest(event.y)
        row_bounds = self.shot_list.bbox(index)
        if row_bounds is None:
            return "break"
        _x, row_y, _width, row_height = row_bounds
        if not row_y <= event.y < row_y + row_height:
            return "break"

        self._select_shot_for_context_menu(index)
        try:
            self.shot_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.shot_context_menu.grab_release()
        return "break"

    def _select_shot_for_context_menu(self, index: int) -> None:
        selected_indexes = set(self.shot_list.curselection())
        if index not in selected_indexes:
            self.shot_list.selection_clear(0, tk.END)
            self.shot_list.selection_set(index)
        self.shot_list.activate(index)
        self._on_shot_selected(None)

    def _create_selected_comp(self) -> None:
        show_path = self._selected_show_path()
        sequence_name = self._selected_value(
            self.sequence_list,
            self.sequence_names,
        )
        shot_names = self._selected_values(self.shot_list, self.shot_names)
        if show_path is None or not sequence_name or not shot_names:
            self._set_status(
                "Select a show, sequence, and at least one shot first.",
                "warning",
            )
            return

        self._create_comps(
            show_path,
            sequence_name,
            shot_names,
            status_action="Create Comps",
        )

    def _create_and_open_selected_comp(self) -> None:
        show_path = self._selected_show_path()
        sequence_name = self._selected_value(
            self.sequence_list,
            self.sequence_names,
        )
        shot_name = self._active_selected_shot_name()
        if show_path is None or not sequence_name or not shot_name:
            self._set_status(
                "Right-click a shot to create and open its comp.",
                "warning",
            )
            return

        try:
            result = create_and_open_comp(
                show_path,
                sequence_name,
                shot_name,
            )
        except Exception as error:
            self._set_status(
                f"Failed to create and open comp for {shot_name}: {error}",
                "error",
            )
            return

        action = "Successfully created and opened" if result.created else "Opened existing"
        self._set_status(
            f"{action} comp: {result.comp_path.name}.",
            "success",
        )

    def _open_selected_comp(self) -> None:
        show_path = self._selected_show_path()
        sequence_name = self._selected_value(
            self.sequence_list,
            self.sequence_names,
        )
        shot_name = self._active_selected_shot_name()
        if show_path is None or not sequence_name or not shot_name:
            self._set_status("Right-click a shot to open its comp.", "warning")
            return

        try:
            result = open_comp(show_path, sequence_name, shot_name)
        except CompNotFoundError as error:
            self._set_status(
                f"Failed to open comp for {shot_name}: {error.comp_path} does not exist.",
                "error",
            )
            return
        except Exception as error:
            self._set_status(
                f"Failed to open comp for {shot_name}: {error}",
                "error",
            )
            return

        self._set_status(
            f"Opened comp: {result.comp_path.name}.",
            "success",
        )

    def _create_all_sequence_comps(self) -> None:
        show_path = self._selected_show_path()
        sequence_name = self._selected_value(
            self.sequence_list,
            self.sequence_names,
        )
        if show_path is None or not sequence_name:
            self._set_status("Select a show and sequence first.", "warning")
            return

        template_shot_name = f"{sequence_name}_000_0000"
        shot_names = [
            shot_name
            for shot_name in self.shot_names
            if shot_name != template_shot_name
        ]
        if not shot_names:
            self._set_status(
                f"No production shots were found in sequence {sequence_name}.",
                "warning",
            )
            return

        self._create_comps(
            show_path,
            sequence_name,
            shot_names,
            status_action=f"Create All Comps for {sequence_name}",
        )

    def _create_comps(
        self,
        show_path: Path,
        sequence_name: str,
        shot_names: list[str],
        *,
        status_action: str,
    ) -> None:

        succeeded = 0
        failed = 0
        last_failure = ""
        for shot_name in shot_names:
            try:
                create_comp(show_path, sequence_name, shot_name)
            except CompAlreadyExistsError:
                failed += 1
                last_failure = f"{shot_name} already has a comp"
            except CompTemplateNotFoundError:
                failed += 1
                last_failure = f"no template was found for {shot_name}"
            except Exception as error:
                failed += 1
                last_failure = f"{shot_name}: {error}"
            else:
                succeeded += 1

        message = f"{status_action} complete — Succeeded: {succeeded}; Failed: {failed}."
        if last_failure:
            message += f" Last failure: {last_failure}."
        level = (
            "success"
            if failed == 0
            else "error"
            if succeeded == 0
            else "warning"
        )
        self._set_status(message, level)

    def _set_status(self, message: str, level: str = "normal") -> None:
        style_by_level = {
            "normal": "Status.TLabel",
            "success": "StatusSuccess.TLabel",
            "warning": "StatusWarning.TLabel",
            "error": "StatusError.TLabel",
        }
        self.status_var.set(message)
        self.status_label.configure(
            style=style_by_level.get(level, "Status.TLabel")
        )

    def _save_current_selection(self) -> None:
        if self.repository_path is None:
            return
        try:
            save_browser_selection(
                self._selected_value(self.show_list, self.show_names),
                self._selected_value(self.sequence_list, self.sequence_names),
                self._selected_value(self.shot_list, self.shot_names),
                self.settings_path,
            )
        except Exception as error:
            messagebox.showerror(
                "Auto Comp - Natron",
                f"Could not save the browser selection:\n{error}",
                parent=self.root,
            )

    def _selected_show_path(self) -> Path | None:
        show_name = self._selected_value(self.show_list, self.show_names)
        return self.show_paths_by_name.get(show_name)

    @staticmethod
    def _preferred_value(preferred: str, values: list[str]) -> str:
        if preferred in values:
            return preferred
        return values[0] if values else ""

    @staticmethod
    def _selected_value(listbox: tk.Listbox, values: list[str]) -> str:
        selection = listbox.curselection()
        if not selection:
            return ""
        index = int(selection[0])
        return values[index] if 0 <= index < len(values) else ""

    @staticmethod
    def _selected_values(listbox: tk.Listbox, values: list[str]) -> list[str]:
        return [
            values[int(index)]
            for index in listbox.curselection()
            if 0 <= int(index) < len(values)
        ]

    def _active_selected_shot_name(self) -> str:
        selected_indexes = {int(index) for index in self.shot_list.curselection()}
        if not selected_indexes:
            return ""
        active_index = int(self.shot_list.index(tk.ACTIVE))
        if active_index in selected_indexes and active_index < len(self.shot_names):
            return self.shot_names[active_index]
        first_selected = min(selected_indexes)
        return self.shot_names[first_selected]

    @staticmethod
    def _replace_list_values(listbox: tk.Listbox, values: list[str]) -> None:
        listbox.delete(0, tk.END)
        for value in values:
            listbox.insert(tk.END, f"  {value}")

    @staticmethod
    def _select_list_value(
        listbox: tk.Listbox,
        values: list[str],
        value: str,
    ) -> None:
        listbox.selection_clear(0, tk.END)
        index = values.index(value)
        listbox.selection_set(index)
        listbox.activate(index)
        listbox.see(index)

    def _clear_browser(self) -> None:
        self.show_names = []
        self.show_paths_by_name = {}
        self._replace_list_values(self.show_list, [])
        self._clear_sequences_and_shots()

    def _clear_sequences_and_shots(self) -> None:
        self.sequence_names = []
        self.sequence_paths_by_name = {}
        self._replace_list_values(self.sequence_list, [])
        self._clear_shots()

    def _clear_shots(self) -> None:
        self.shot_names = []
        self.shot_rows_by_name = {}
        self._replace_list_values(self.shot_list, [])

    def _create_browser_panel(
        self,
        parent: ttk.Frame,
        *,
        column: int,
        title: str,
        left_padding: int = 0,
        right_padding: int = 0,
        selectmode: str = tk.BROWSE,
    ) -> tk.Listbox:
        shell = tk.Frame(
            parent,
            background=BORDER_COLOR,
            highlightthickness=0,
            borderwidth=0,
        )
        shell.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=(left_padding, right_padding),
        )
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)

        header = ttk.Frame(shell, style="PanelHeader.TFrame", padding=(16, 11))
        header.grid(row=0, column=0, sticky="ew", padx=1, pady=(1, 0))

        ttk.Label(
            header,
            text=title,
            style="PanelTitle.TLabel",
        ).pack(anchor="w")

        listbox = tk.Listbox(
            shell,
            background=PANEL_BACKGROUND,
            foreground=TEXT_COLOR,
            selectbackground=SELECTION_COLOR,
            selectforeground="#ffffff",
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            exportselection=False,
            activestyle="none",
            font=("Consolas", 11),
            selectmode=selectmode,
        )
        listbox.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0, 1))

        return listbox

    def _build_options_panel(self, parent: ttk.Frame) -> None:
        shell = tk.Frame(
            parent,
            background=BORDER_COLOR,
            highlightthickness=0,
            borderwidth=0,
        )
        shell.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=(12, 0))
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)

        header = ttk.Frame(shell, style="PanelHeader.TFrame", padding=(16, 9))
        header.grid(row=0, column=0, sticky="ew", padx=1, pady=(1, 0))

        ttk.Label(
            header,
            text="Details / Options",
            style="PanelTitle.TLabel",
        ).pack(anchor="w")

        content = ttk.Frame(shell, style="Panel.TFrame", padding=(14, 8))
        content.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0, 1))

        ttk.Checkbutton(
            content,
            text="Hero",
            variable=self.hero_var,
            style="Option.TCheckbutton",
        ).pack(anchor="w")

        ttk.Checkbutton(
            content,
            text="EXR",
            variable=self.exr_var,
            style="Option.TCheckbutton",
        ).pack(anchor="w")

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = AutoCompNatronApp()
    app.run()


if __name__ == "__main__":
    main()
