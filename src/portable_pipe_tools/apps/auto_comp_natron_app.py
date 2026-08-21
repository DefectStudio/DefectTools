from __future__ import annotations

import tkinter as tk
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from portable_pipe_tools.auto_comp_natron.create_comp import (
    CompAlreadyExistsError,
    CompTemplateNotFoundError,
    SmartWriteOutputOptions,
    create_comp,
    get_comp_path,
)
from portable_pipe_tools.auto_comp_natron.open_comp import (
    CompNotFoundError,
    create_and_open_comp,
    open_comp,
)
from portable_pipe_tools.auto_comp_natron.render_comp import (
    RenderCompProgress,
    RenderCompResult,
    pause_render_comp,
    poll_render_comp,
    read_render_comp_progress,
    render_comp,
    resume_render_comp,
    terminate_render_comp,
)
from portable_pipe_tools.auto_comp_natron.settings import (
    get_default_settings_path,
    load_saved_browser_selection,
    load_saved_natron_executable,
    load_saved_repository_folder,
    save_browser_selection,
    save_natron_executable,
    save_repository_folder,
)
from portable_pipe_tools.show_manager.shot_manager_core import (
    ShotRow,
    find_sequence_folders,
    find_shot_folders,
    find_show_folders,
    open_folder_in_file_browser,
)


WINDOW_BACKGROUND = "#252629"
PANEL_BACKGROUND = "#2d2f32"
PANEL_HEADER = "#3b3d40"
TOOLBAR_BACKGROUND = "#333538"
BORDER_COLOR = "#161719"
TEXT_COLOR = "#d8dadd"
MUTED_TEXT = "#a5a9ae"
SELECTION_COLOR = "#315f7a"
COMP_PRESENT_COLOR = "#74d680"
COMP_MISSING_COLOR = "#ffcf70"


@dataclass(frozen=True)
class RenderQueueJob:
    show_path: Path
    sequence_name: str
    shot_name: str
    tree_item_id: str


class AutoCompNatronApp:
    """Natron auto-comp GUI shell with a locally saved repository connection."""

    def __init__(
        self,
        settings_path: Path | None = None,
        prompt_on_startup: bool = True,
    ) -> None:
        self.root = tk.Tk()
        self.root.title("Auto Comp - Natron")
        self.root.geometry("1040x940")
        self.root.minsize(780, 640)

        self.settings_path = settings_path or get_default_settings_path()
        self.repository_path: Path | None = None
        self.natron_executable_path: Path | None = None
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
        self._pending_render_jobs: list[RenderQueueJob] = []
        self._render_job_keys_by_item_id: dict[str, tuple[str, str, str]] = {}
        self._queue_paused = False
        self._active_render_job: RenderQueueJob | None = None
        self._active_render_result: RenderCompResult | None = None
        self._render_progress_job: RenderQueueJob | None = None
        self._render_progress_percent = 0.0
        self._render_progress_completed_frames = 0
        self._render_progress_total_frames = 0
        self._render_progress_finalizing = False
        self.exr_var = tk.BooleanVar(value=True)
        self.mp4_var = tk.BooleanVar(value=True)
        self.mov_var = tk.BooleanVar(value=False)
        self.hero_var = tk.BooleanVar(value=True)

        self._configure_styles()
        self._build_menu()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        if prompt_on_startup:
            self.root.after_idle(self._initialize_startup_settings)

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
            "Queue.Treeview",
            background=PANEL_BACKGROUND,
            fieldbackground=PANEL_BACKGROUND,
            foreground=TEXT_COLOR,
            borderwidth=0,
            relief="flat",
            rowheight=27,
            font=("Consolas", 10),
        )
        style.map(
            "Queue.Treeview",
            background=[("selected", SELECTION_COLOR)],
            foreground=[("selected", "#ffffff")],
        )
        style.configure(
            "Queue.Treeview.Heading",
            background=PANEL_HEADER,
            foreground=TEXT_COLOR,
            borderwidth=0,
            relief="flat",
            padding=(8, 6),
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "Queue.Treeview.Heading",
            background=[("active", "#484b4f")],
            foreground=[("active", "#ffffff")],
        )
        style.configure(
            "QueueControl.TButton",
            background="#45484c",
            foreground=TEXT_COLOR,
            bordercolor=BORDER_COLOR,
            lightcolor="#56595d",
            darkcolor=BORDER_COLOR,
            padding=(12, 7),
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "QueueControl.TButton",
            background=[("active", "#55585c"), ("pressed", "#292b2e")],
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
        file_menu.add_command(
            label="Change Natron Executable...",
            command=self._browse_natron_executable,
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
        workspace.rowconfigure(2, weight=2)

        self.show_list = self._create_browser_panel(
            workspace,
            column=0,
            title="Show",
            right_padding=5,
        )
        self.show_list.bind("<<ListboxSelect>>", self._on_show_selected)
        self.show_list.bind("<Button-3>", self._show_show_context_menu)

        self.show_context_menu = tk.Menu(
            self.root,
            tearoff=False,
            background="#303236",
            foreground=TEXT_COLOR,
            activebackground=SELECTION_COLOR,
            activeforeground="#ffffff",
            borderwidth=0,
        )
        self.show_context_menu.add_command(
            label="Open in Explorer",
            command=self._open_selected_show_in_explorer,
        )

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
        self.sequence_context_menu.add_separator()
        self.sequence_context_menu.add_command(
            label="Open in Explorer",
            command=self._open_selected_sequence_in_explorer,
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
        self._configure_shot_context_menu(comp_exists=True)

        self._build_options_panel(workspace)
        self._build_queue_panel(workspace)
        self._build_status_bar(outer)

    def _configure_shot_context_menu(self, *, comp_exists: bool) -> None:
        self.shot_context_menu.delete(0, tk.END)
        self.shot_context_menu.add_command(
            label="Create Comp",
            command=self._create_selected_comp,
        )
        self.shot_context_menu.add_command(
            label="Create and Open Comp",
            command=self._create_and_open_selected_comp,
        )
        if not comp_exists:
            return

        self.shot_context_menu.add_command(
            label="Open Comp",
            command=self._open_selected_comp,
        )
        self.shot_context_menu.add_command(
            label="Render Comp",
            command=self._render_selected_comp,
        )
        self.shot_context_menu.add_command(
            label="Add to Render Queue",
            command=self._add_selected_comps_to_render_queue,
        )
        self.shot_context_menu.add_separator()
        self.shot_context_menu.add_command(
            label="Open in Explorer",
            command=self._open_selected_shot_in_explorer,
        )

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

    def _initialize_startup_settings(self) -> None:
        self._initialize_natron_executable()
        self._initialize_repository()

    def _initialize_natron_executable(self) -> None:
        saved_executable = load_saved_natron_executable(self.settings_path)
        if saved_executable:
            saved_path = Path(saved_executable).expanduser()
            if saved_path.is_file():
                self.natron_executable_path = saved_path
                return
        self.natron_executable_path = None
        self._browse_natron_executable(first_startup=True)

    def _browse_natron_executable(self, first_startup: bool = False) -> bool:
        title = (
            "First Time Setup - Choose Natron Executable"
            if first_startup
            else "Choose Natron Executable"
        )
        current = self.natron_executable_path
        initial_directory = (
            str(current.parent)
            if current and current.parent.is_dir()
            else None
        )
        selected = filedialog.askopenfilename(
            title=title,
            initialdir=initial_directory,
            filetypes=(
                ("Natron", "Natron.exe"),
                ("Executables", "*.exe"),
                ("All files", "*.*"),
            ),
            parent=self.root,
        )
        if not selected:
            return False

        selected_path = Path(selected).expanduser()
        if not selected_path.is_file():
            messagebox.showerror(
                "Auto Comp - Natron",
                f"The selected Natron executable does not exist:\n{selected_path}",
                parent=self.root,
            )
            return False

        try:
            save_natron_executable(selected_path, self.settings_path)
        except Exception as error:
            messagebox.showerror(
                "Auto Comp - Natron",
                f"Could not save the local configuration:\n{error}",
                parent=self.root,
            )
            return False

        self.natron_executable_path = selected_path
        self._set_status(f"Natron executable set: {selected_path.name}.", "success")
        return True

    def _ensure_natron_executable(self) -> bool:
        if self.natron_executable_path and self.natron_executable_path.is_file():
            return True
        self.natron_executable_path = None
        if self._browse_natron_executable():
            return True
        self._set_status(
            "Choose the Natron executable before opening a comp.",
            "warning",
        )
        return False

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

        shot_rows.sort(
            key=lambda shot_row: (
                shot_row.sequence.casefold(),
                shot_row.section_number,
                shot_row.shot_number,
                shot_row.shot_name.casefold(),
            )
        )
        self.shot_rows_by_name = {
            shot_row.shot_name: shot_row for shot_row in shot_rows
        }
        self.shot_names = list(self.shot_rows_by_name)
        self._replace_list_values(self.shot_list, self.shot_names)
        self._refresh_shot_comp_colors(show_path, sequence_name)

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

    def _show_show_context_menu(self, event: tk.Event) -> str:
        if not self.show_names:
            return "break"
        index = self.show_list.nearest(event.y)
        row_bounds = self.show_list.bbox(index)
        if row_bounds is None:
            return "break"
        _x, row_y, _width, row_height = row_bounds
        if not row_y <= event.y < row_y + row_height:
            return "break"

        self._select_show_for_context_menu(index)
        try:
            self.show_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.show_context_menu.grab_release()
        return "break"

    def _select_show_for_context_menu(self, index: int) -> None:
        self.show_list.selection_clear(0, tk.END)
        self.show_list.selection_set(index)
        self.show_list.activate(index)
        self._on_show_selected(None)

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
        show_path = self._selected_show_path()
        sequence_name = self._selected_value(
            self.sequence_list,
            self.sequence_names,
        )
        shot_name = self.shot_names[index]
        comp_exists = (
            show_path is not None
            and bool(sequence_name)
            and get_comp_path(show_path, sequence_name, shot_name).is_file()
        )
        self._configure_shot_context_menu(comp_exists=comp_exists)
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

    def _open_selected_show_in_explorer(self) -> None:
        self._open_folder_in_explorer(self._selected_show_path(), "show")

    def _open_selected_sequence_in_explorer(self) -> None:
        sequence_name = self._selected_value(
            self.sequence_list,
            self.sequence_names,
        )
        self._open_folder_in_explorer(
            self.sequence_paths_by_name.get(sequence_name),
            "sequence",
        )

    def _open_selected_shot_in_explorer(self) -> None:
        shot_name = self._active_selected_shot_name()
        shot_row = self.shot_rows_by_name.get(shot_name)
        self._open_folder_in_explorer(
            shot_row.shot_path if shot_row is not None else None,
            "shot",
        )

    def _open_folder_in_explorer(
        self,
        folder_path: Path | None,
        item_kind: str,
    ) -> None:
        if folder_path is None:
            self._set_status(
                f"Right-click a {item_kind} to open its folder.",
                "warning",
            )
            return
        if not folder_path.is_dir():
            self._set_status(
                f"Could not open {item_kind} folder because it does not exist: "
                f"{folder_path}",
                "error",
            )
            return

        try:
            open_folder_in_file_browser(folder_path)
        except Exception as error:
            self._set_status(
                f"Could not open {item_kind} folder: {error}",
                "error",
            )
            return

        self._set_status(
            f"Opened {item_kind} folder: {folder_path.name}.",
            "success",
        )

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
        if not self._ensure_natron_executable():
            return

        self._set_status(
            f"Checking Dropbox source files for {shot_name}...",
            "normal",
        )
        self.root.update_idletasks()
        try:
            result = create_and_open_comp(
                show_path,
                sequence_name,
                shot_name,
                smart_write_outputs=self._smart_write_output_options(),
                natron_executable=self.natron_executable_path,
                hydration_progress=self._update_source_hydration_progress,
            )
        except Exception as error:
            self._set_status(
                f"Failed to create and open comp for {shot_name}: {error}",
                "error",
            )
            return

        action = "Successfully created and opened" if result.created else "Opened existing"
        hydration = (
            f"Downloaded {result.hydrated_source_files} source frames. "
            if result.hydrated_source_files
            else ""
        )
        self._set_status(
            f"{hydration}{action} comp: {result.comp_path.name}.",
            "success",
        )
        self._refresh_shot_comp_colors(show_path, sequence_name)

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
        if not self._ensure_natron_executable():
            return

        self._set_status(
            f"Checking Dropbox source files for {shot_name}...",
            "normal",
        )
        self.root.update_idletasks()
        try:
            result = open_comp(
                show_path,
                sequence_name,
                shot_name,
                natron_executable=self.natron_executable_path,
                hydration_progress=self._update_source_hydration_progress,
            )
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

        hydration = (
            f"Downloaded {result.hydrated_source_files} source frames. "
            if result.hydrated_source_files
            else ""
        )
        self._set_status(
            f"{hydration}Opened comp: {result.comp_path.name}.",
            "success",
        )

    def _render_selected_comp(self) -> None:
        self._queue_selected_comps(start_if_idle=True)

    def _add_selected_comps_to_render_queue(self) -> None:
        self._queue_selected_comps(start_if_idle=False)

    def _queue_selected_comps(self, *, start_if_idle: bool) -> None:
        show_path = self._selected_show_path()
        sequence_name = self._selected_value(
            self.sequence_list,
            self.sequence_names,
        )
        shot_names = self._selected_values(self.shot_list, self.shot_names)
        if show_path is None or not sequence_name or not shot_names:
            self._set_status(
                (
                    "Select one or more shots to render their comps."
                    if start_if_idle
                    else "Select one or more shots to add to the render queue."
                ),
                "warning",
            )
            return
        if start_if_idle and not self._ensure_natron_executable():
            return

        existing_job_keys = set(self._render_job_keys_by_item_id.values())
        new_jobs: list[RenderQueueJob] = []
        duplicate_count = 0
        for shot_name in shot_names:
            job_key = self._render_queue_job_key(
                show_path,
                sequence_name,
                shot_name,
            )
            if job_key in existing_job_keys:
                duplicate_count += 1
                continue
            tree_item_id = self.queue_tree.insert(
                "",
                "end",
                values=(f"{sequence_name} / {shot_name}", "Queued"),
                tags=("queued",),
            )
            new_jobs.append(
                RenderQueueJob(
                    show_path=show_path,
                    sequence_name=sequence_name,
                    shot_name=shot_name,
                    tree_item_id=tree_item_id,
                )
            )
            self._render_job_keys_by_item_id[tree_item_id] = job_key
            existing_job_keys.add(job_key)

        if not new_jobs:
            noun = "comp is" if duplicate_count == 1 else "comps are"
            self._set_status(
                f"The selected {noun} already in the render queue.",
                "normal",
            )
            if (
                start_if_idle
                and self._active_render_job is None
                and self._pending_render_jobs
            ):
                self._start_next_queued_render()
            return

        self._pending_render_jobs.extend(new_jobs)
        self.queue_tree.see(new_jobs[-1].tree_item_id)
        self._update_queue_pause_controls()
        if not start_if_idle or self._active_render_job is not None:
            noun = "comp" if len(new_jobs) == 1 else "comps"
            self._set_status(
                self._render_queue_added_message(
                    len(new_jobs),
                    duplicate_count,
                    noun,
                ),
                "normal",
            )
            return

        self._start_next_queued_render()

    @staticmethod
    def _render_queue_job_key(
        show_path: Path,
        sequence_name: str,
        shot_name: str,
    ) -> tuple[str, str, str]:
        return (
            str(show_path.resolve(strict=False)).casefold(),
            sequence_name.casefold(),
            shot_name.casefold(),
        )

    @staticmethod
    def _render_queue_added_message(
        added_count: int,
        duplicate_count: int,
        noun: str,
    ) -> str:
        message = f"Added {added_count} {noun} to the render queue."
        if duplicate_count:
            duplicate_noun = "duplicate" if duplicate_count == 1 else "duplicates"
            message += f" Skipped {duplicate_count} {duplicate_noun}."
        return message

    def _start_next_queued_render(self) -> None:
        if self._queue_paused:
            if self._pending_render_jobs:
                self._set_status(
                    f"Render queue paused with {len(self._pending_render_jobs)} "
                    "pending job(s).",
                    "normal",
                )
            return
        if self._active_render_job is not None or not self._pending_render_jobs:
            return

        job = self._pending_render_jobs.pop(0)
        self._active_render_job = job
        self._update_queue_pause_controls()
        self._set_render_queue_job_status(job, "Preparing", "preparing")
        self._set_status(
            f"Checking Dropbox source files for {job.shot_name}...",
            "normal",
        )
        self.root.update_idletasks()
        try:
            result = render_comp(
                job.show_path,
                job.sequence_name,
                job.shot_name,
                natron_executable=self.natron_executable_path,
                hydration_progress=self._update_source_hydration_progress,
            )
        except Exception as error:
            self._hide_render_progress(job)
            self._set_render_queue_job_status(job, "Failed", "failed")
            self._active_render_job = None
            self._set_status(
                f"Failed to render comp for {job.shot_name}: {error}",
                "error",
            )
            self._start_next_queued_render()
            return

        self._set_render_queue_job_status(job, "Rendering", "rendering")
        self._show_render_progress(job, 0.0)
        self._set_status(f"Rendering comp: {result.comp_path.name}...", "normal")
        self._active_render_result = result
        self._poll_render_result(result, job)

    def _poll_render_result(
        self,
        result: RenderCompResult,
        job: RenderQueueJob,
    ) -> None:
        if (
            result is not self._active_render_result
            or job is not self._active_render_job
        ):
            return
        progress = read_render_comp_progress(result)
        if progress is not None and not self._queue_paused:
            self._update_render_progress(job, progress)
        try:
            completion = poll_render_comp(result)
        except Exception as error:
            self._hide_render_progress(job)
            self._set_render_queue_job_status(job, "Failed", "failed")
            self._active_render_result = None
            self._active_render_job = None
            self._set_status(
                f"Failed to render comp for {job.shot_name}: {error}",
                "error",
            )
            self._start_next_queued_render()
            return
        if completion is None:
            self.root.after(
                250,
                lambda: self._poll_render_result(result, job),
            )
            return

        self._hide_render_progress(job)
        self._set_render_queue_job_status(job, "Complete", "complete")
        self._active_render_result = None
        self._active_render_job = None
        hydration = (
            f"Downloaded {completion.hydrated_source_files} source frames. "
            if completion.hydrated_source_files
            else ""
        )
        self._set_status(
            f"{hydration}Successfully rendered comp: {completion.comp_path.name}.",
            "success",
        )
        self._start_next_queued_render()

    def _set_render_queue_job_status(
        self,
        job: RenderQueueJob,
        status: str,
        tag: str,
    ) -> None:
        self.queue_tree.item(
            job.tree_item_id,
            values=(f"{job.sequence_name} / {job.shot_name}", status),
            tags=(tag,),
        )
        self.queue_tree.see(job.tree_item_id)

    def _update_render_progress(
        self,
        job: RenderQueueJob,
        progress: RenderCompProgress,
    ) -> None:
        same_job = job == self._render_progress_job
        percent = max(0.0, min(99.0, progress.percent))
        completed_frames = progress.completed_frames
        total_frames = progress.total_frames
        finalizing = progress.finalizing
        if same_job:
            percent = max(percent, self._render_progress_percent)
            completed_frames = max(
                completed_frames,
                self._render_progress_completed_frames,
            )
            total_frames = max(
                total_frames,
                self._render_progress_total_frames,
            )
            finalizing = finalizing or self._render_progress_finalizing
        self._render_progress_completed_frames = completed_frames
        self._render_progress_total_frames = total_frames
        self._render_progress_finalizing = finalizing
        phase = "Finalizing" if finalizing else "Rendering"
        self._set_render_queue_job_status(
            job,
            f"{phase} — {percent:.0f}%",
            "rendering",
        )
        self._show_render_progress(job, percent)
        if total_frames:
            output_summary = (
                f" across {progress.total_outputs} outputs"
                if progress.total_outputs > 1
                else ""
            )
            self._set_status(
                f"{phase} {job.shot_name}: {completed_frames}/"
                f"{total_frames} writer-frames{output_summary} "
                f"({percent:.0f}%)...",
                "normal",
            )

    def _show_render_progress(
        self,
        job: RenderQueueJob,
        percent: float,
    ) -> None:
        bounded_percent = max(0.0, min(100.0, percent))
        if job == self._render_progress_job:
            bounded_percent = max(
                bounded_percent,
                self._render_progress_percent,
            )
        else:
            self._render_progress_completed_frames = 0
            self._render_progress_total_frames = 0
            self._render_progress_finalizing = False
        self._render_progress_job = job
        self._render_progress_percent = bounded_percent
        self._position_render_progress()

    def _hide_render_progress(self, job: RenderQueueJob | None = None) -> None:
        if job is not None and job != self._render_progress_job:
            return
        self._render_progress_job = None
        self._render_progress_percent = 0.0
        self._render_progress_completed_frames = 0
        self._render_progress_total_frames = 0
        self._render_progress_finalizing = False
        self.render_progress_canvas.place_forget()

    def _position_render_progress(self) -> None:
        job = self._render_progress_job
        if job is None or not self.queue_tree.exists(job.tree_item_id):
            self.render_progress_canvas.place_forget()
            return

        bounds = self.queue_tree.bbox(job.tree_item_id, "status")
        if not bounds:
            self.render_progress_canvas.place_forget()
            return

        x, y, width, height = bounds
        horizontal_padding = 4
        vertical_padding = 4
        bar_width = max(1, width - (horizontal_padding * 2))
        bar_height = max(1, height - (vertical_padding * 2))
        self.render_progress_canvas.place(
            x=x + horizontal_padding,
            y=y + vertical_padding,
            width=bar_width,
            height=bar_height,
        )
        self.render_progress_canvas.delete("all")
        self.render_progress_canvas.create_rectangle(
            0,
            0,
            bar_width,
            bar_height,
            fill="#202124",
            outline="#161719",
        )
        filled_width = int(bar_width * self._render_progress_percent / 100.0)
        if filled_width:
            self.render_progress_canvas.create_rectangle(
                1,
                1,
                filled_width,
                max(1, bar_height - 1),
                fill="#315f7a",
                outline="",
            )
        self.render_progress_canvas.create_text(
            bar_width // 2,
            bar_height // 2,
            text=f"{self._render_progress_percent:.0f}%",
            fill="#ffffff",
            font=("Segoe UI", 8, "bold"),
        )

    def _clear_render_queue(self) -> None:
        queue_items = self.queue_tree.get_children()
        active_result = self._active_render_result
        active_cancelled = False
        if active_result is not None:
            try:
                active_cancelled = terminate_render_comp(active_result)
            except (OSError, subprocess.SubprocessError) as error:
                self._set_status(
                    f"Could not cancel the active Natron render: {error}",
                    "error",
                )
                return

        self._active_render_result = None
        self._active_render_job = None
        self._pending_render_jobs.clear()
        self._render_job_keys_by_item_id.clear()
        self._queue_paused = False
        self._update_queue_pause_controls()
        self._hide_render_progress()
        if queue_items:
            self.queue_tree.delete(*queue_items)

        cleared_count = len(queue_items)
        if cleared_count == 0:
            self._set_status("The render queue is already empty.", "normal")
            return

        noun = "entry" if cleared_count == 1 else "entries"
        message = f"Cleared {cleared_count} queue {noun}."
        if active_cancelled:
            message = f"Cancelled the active render and {message.lower()}"
        self._set_status(message, "success")

    def _show_render_queue_context_menu(self, event: tk.Event) -> str:
        item_id = self.queue_tree.identify_row(event.y)
        if not item_id:
            return "break"

        self.queue_tree.selection_set(item_id)
        self.queue_tree.focus(item_id)
        active_item_id = (
            self._active_render_job.tree_item_id
            if self._active_render_job is not None
            else None
        )
        self.queue_context_menu.entryconfigure(
            0,
            label=(
                "Cancel Render"
                if item_id == active_item_id
                else "Remove from Queue"
            ),
            state="normal",
        )
        try:
            self.queue_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.queue_context_menu.grab_release()
        return "break"

    def _run_selected_render_queue_action(self) -> None:
        selected_items = self.queue_tree.selection()
        if not selected_items:
            return
        item_id = selected_items[0]
        if (
            self._active_render_job is not None
            and item_id == self._active_render_job.tree_item_id
        ):
            self._cancel_active_render_queue_item()
            return
        self._remove_selected_render_queue_item()

    def _cancel_active_render_queue_item(self) -> None:
        job = self._active_render_job
        result = self._active_render_result
        if job is None or result is None:
            self._set_status("There is no active render to cancel.", "normal")
            return

        try:
            terminate_render_comp(result)
        except (OSError, subprocess.SubprocessError) as error:
            self._set_status(
                f"Could not cancel the active Natron render: {error}",
                "error",
            )
            return

        self._active_render_result = None
        self._active_render_job = None
        self._hide_render_progress(job)
        self._set_render_queue_job_status(job, "Canceled", "canceled")
        self._set_status(f"Canceled render: {job.shot_name}.", "normal")
        self._start_next_queued_render()

    def _remove_selected_render_queue_item(self) -> None:
        selected_items = self.queue_tree.selection()
        if not selected_items:
            return
        item_id = selected_items[0]
        if (
            self._active_render_job is not None
            and item_id == self._active_render_job.tree_item_id
        ):
            self._set_status(
                "The active render cannot be removed from the queue; allow it "
                "to finish first.",
                "normal",
            )
            return

        values = self.queue_tree.item(item_id, "values")
        job_label = str(values[0]) if values else "entry"
        self._pending_render_jobs = [
            job
            for job in self._pending_render_jobs
            if job.tree_item_id != item_id
        ]
        self._render_job_keys_by_item_id.pop(item_id, None)
        self._update_queue_pause_controls()
        self.queue_tree.delete(item_id)
        self._position_render_progress()
        self._set_status(
            f"Removed {job_label} from the render queue.",
            "success",
        )

    def _update_queue_pause_controls(self) -> None:
        can_start_pending_jobs = (
            not self._queue_paused
            and self._active_render_job is None
            and bool(self._pending_render_jobs)
        )
        self.pause_queue_button.configure(
            state="disabled" if self._queue_paused else "normal"
        )
        self.resume_queue_button.configure(
            state=(
                "normal"
                if self._queue_paused or can_start_pending_jobs
                else "disabled"
            )
        )

    def _pause_render_queue(self) -> None:
        if self._queue_paused:
            self._set_status("The render queue is already paused.", "normal")
            return

        result = self._active_render_result
        renderer_paused = False
        if result is not None:
            try:
                renderer_paused = pause_render_comp(result)
            except OSError as error:
                self._set_status(
                    f"Could not pause the active Natron render: {error}",
                    "error",
                )
                return

        self._queue_paused = True
        self._update_queue_pause_controls()
        if self._active_render_job is not None and renderer_paused:
            self._set_render_queue_job_status(
                self._active_render_job,
                f"Paused — {self._render_progress_percent:.0f}%",
                "rendering",
            )
            self._position_render_progress()
            self._set_status(
                f"Paused active render: {self._active_render_job.shot_name}.",
                "normal",
            )
            return
        self._set_status("Render queue paused.", "normal")

    def _resume_render_queue(self) -> None:
        if not self._queue_paused:
            if self._active_render_job is not None:
                self._set_status("The render queue is already running.", "normal")
                return
            if not self._pending_render_jobs:
                self._set_status("There are no queued renders to start.", "normal")
                return
            if not self._ensure_natron_executable():
                return
            self._start_next_queued_render()
            return

        result = self._active_render_result
        renderer_resumed = False
        if result is not None:
            try:
                renderer_resumed = resume_render_comp(result)
            except OSError as error:
                self._set_status(
                    f"Could not resume the active Natron render: {error}",
                    "error",
                )
                return

        self._queue_paused = False
        self._update_queue_pause_controls()
        if self._active_render_job is not None and renderer_resumed:
            phase = (
                "Finalizing" if self._render_progress_finalizing else "Rendering"
            )
            self._set_render_queue_job_status(
                self._active_render_job,
                f"{phase} — {self._render_progress_percent:.0f}%",
                "rendering",
            )
            self._position_render_progress()
            self._set_status(
                f"Resumed active render: {self._active_render_job.shot_name}.",
                "normal",
            )
            return
        self._set_status("Render queue resumed.", "normal")
        self._start_next_queued_render()

    def _close(self) -> None:
        result = self._active_render_result
        self._active_render_result = None
        try:
            if result is not None:
                terminate_render_comp(result)
        except (OSError, subprocess.SubprocessError):
            pass
        finally:
            self.root.destroy()

    def _update_source_hydration_progress(
        self,
        completed: int,
        total: int,
        _source_path: Path,
    ) -> None:
        self._set_status(
            f"Downloading Dropbox source frames: {completed}/{total}...",
            "normal",
        )
        self.root.update_idletasks()

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

        smart_write_outputs = self._smart_write_output_options()
        succeeded = 0
        failed = 0
        last_failure = ""
        for shot_name in shot_names:
            try:
                create_comp(
                    show_path,
                    sequence_name,
                    shot_name,
                    smart_write_outputs=smart_write_outputs,
                )
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
        self._refresh_shot_comp_colors(show_path, sequence_name)

    def _smart_write_output_options(self) -> SmartWriteOutputOptions:
        return SmartWriteOutputOptions(
            exr=self.exr_var.get(),
            mp4=self.mp4_var.get(),
            mov=self.mov_var.get(),
            hero=self.hero_var.get(),
        )

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

    def _refresh_shot_comp_colors(
        self,
        show_path: Path | None = None,
        sequence_name: str = "",
    ) -> None:
        show_path = show_path or self._selected_show_path()
        sequence_name = sequence_name or self._selected_value(
            self.sequence_list,
            self.sequence_names,
        )
        if show_path is None or not sequence_name:
            return

        for index, shot_name in enumerate(self.shot_names):
            comp_path = get_comp_path(show_path, sequence_name, shot_name)
            color = (
                COMP_PRESENT_COLOR
                if comp_path.is_file()
                else COMP_MISSING_COLOR
            )
            self.shot_list.itemconfigure(index, foreground=color)

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
            text="EXR",
            variable=self.exr_var,
            style="Option.TCheckbutton",
        ).pack(anchor="w")

        ttk.Checkbutton(
            content,
            text="MP4",
            variable=self.mp4_var,
            style="Option.TCheckbutton",
        ).pack(anchor="w")

        ttk.Checkbutton(
            content,
            text="MOV",
            variable=self.mov_var,
            style="Option.TCheckbutton",
        ).pack(anchor="w")

        ttk.Checkbutton(
            content,
            text="Hero",
            variable=self.hero_var,
            style="Option.TCheckbutton",
        ).pack(anchor="w")

    def _build_queue_panel(self, parent: ttk.Frame) -> None:
        shell = tk.Frame(
            parent,
            background=BORDER_COLOR,
            highlightthickness=0,
            borderwidth=0,
        )
        shell.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(12, 0))
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)

        header = ttk.Frame(shell, style="PanelHeader.TFrame", padding=(16, 9))
        header.grid(row=0, column=0, sticky="ew", padx=1, pady=(1, 0))

        ttk.Label(
            header,
            text="Auto Compositor Queue",
            style="PanelTitle.TLabel",
        ).pack(anchor="w")

        content = ttk.Frame(shell, style="Panel.TFrame", padding=(12, 12))
        content.grid(row=1, column=0, sticky="nsew", padx=1, pady=(0, 1))
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        queue_list = ttk.Frame(content, style="Panel.TFrame")
        queue_list.grid(row=0, column=0, sticky="nsew")
        queue_list.columnconfigure(0, weight=1)
        queue_list.rowconfigure(0, weight=1)

        self.queue_tree = ttk.Treeview(
            queue_list,
            columns=("job", "status"),
            show="headings",
            selectmode="browse",
            style="Queue.Treeview",
        )
        self.queue_tree.heading("job", text="Job", anchor="w")
        self.queue_tree.heading("status", text="Status", anchor="w")
        self.queue_tree.column("job", width=560, minwidth=220, stretch=True)
        self.queue_tree.column("status", width=150, minwidth=100, stretch=False)
        self.queue_tree.grid(row=0, column=0, sticky="nsew")
        self.queue_tree.tag_configure("queued", foreground=TEXT_COLOR)
        self.queue_tree.tag_configure("preparing", foreground="#ffcf70")
        self.queue_tree.tag_configure("rendering", foreground="#74b9ff")
        self.queue_tree.tag_configure("complete", foreground="#74d680")
        self.queue_tree.tag_configure("failed", foreground="#ff7b72")
        self.queue_tree.tag_configure("canceled", foreground="#ff7b72")
        self.queue_tree.bind(
            "<Button-3>",
            self._show_render_queue_context_menu,
        )

        self.queue_context_menu = tk.Menu(
            self.root,
            tearoff=False,
            background="#303236",
            foreground=TEXT_COLOR,
            activebackground=SELECTION_COLOR,
            activeforeground="#ffffff",
            borderwidth=0,
        )
        self.queue_context_menu.add_command(
            label="Remove from Queue",
            command=self._run_selected_render_queue_action,
        )

        self.render_progress_canvas = tk.Canvas(
            self.queue_tree,
            background="#202124",
            borderwidth=0,
            highlightthickness=0,
        )
        self.queue_tree.bind(
            "<Configure>",
            lambda _event: self._position_render_progress(),
            add="+",
        )

        queue_scrollbar = ttk.Scrollbar(
            queue_list,
            orient="vertical",
        )

        def scroll_queue(*arguments: str) -> None:
            self.queue_tree.yview(*arguments)
            self._position_render_progress()

        def update_queue_scrollbar(first: str, last: str) -> None:
            queue_scrollbar.set(first, last)
            self._position_render_progress()

        queue_scrollbar.configure(command=scroll_queue)
        queue_scrollbar.grid(row=0, column=1, sticky="ns")
        self.queue_tree.configure(yscrollcommand=update_queue_scrollbar)

        controls = ttk.Frame(content, style="Panel.TFrame")
        controls.grid(row=0, column=1, sticky="ns", padx=(12, 0))

        self.pause_queue_button = ttk.Button(
            controls,
            text="Pause Queue",
            command=self._pause_render_queue,
            style="QueueControl.TButton",
            width=15,
        )
        self.pause_queue_button.pack(fill="x", pady=(0, 8))

        self.resume_queue_button = ttk.Button(
            controls,
            text="Resume Queue",
            command=self._resume_render_queue,
            style="QueueControl.TButton",
            width=15,
        )
        self.resume_queue_button.pack(fill="x", pady=(0, 8))
        self._update_queue_pause_controls()

        self.clear_queue_button = ttk.Button(
            controls,
            text="Clear Queue",
            command=self._clear_render_queue,
            style="QueueControl.TButton",
            width=15,
        )
        self.clear_queue_button.pack(fill="x")

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = AutoCompNatronApp()
    app.run()


if __name__ == "__main__":
    main()
