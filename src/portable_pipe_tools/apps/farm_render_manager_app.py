from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from queue import Empty, Queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Iterable

from portable_pipe_tools.render_farm.auto_refresh_worker import (
    AutoRefreshResult,
    AutoRefreshWorker,
)
from portable_pipe_tools.render_farm.auto_refresh_interval import (
    AUTO_REFRESH_INTERVAL_LABELS,
    format_auto_refresh_interval,
    parse_auto_refresh_interval,
)
from portable_pipe_tools.render_farm.delete_render_jobs import delete_render_jobs
from portable_pipe_tools.render_farm.cloud_dispatch import (
    DispatcherClient,
    load_dispatcher_connection,
)
from portable_pipe_tools.render_farm.get_all_render_jobs import (
    get_all_render_jobs,
)
from portable_pipe_tools.render_farm.get_render_log import get_render_log
from portable_pipe_tools.render_farm.get_render_job_details import (
    get_render_job_details,
)
from portable_pipe_tools.render_farm.manager_settings import (
    get_default_manager_settings_path,
    load_saved_auto_refresh_enabled,
    load_saved_auto_refresh_interval_minutes,
    load_saved_dropbox_folder,
    save_auto_refresh_enabled,
    save_auto_refresh_interval_minutes,
    save_dropbox_folder,
)
from portable_pipe_tools.render_farm.manage_render_jobs import (
    clear_render_job_blacklist,
    resubmit_failed_render_job,
)
from portable_pipe_tools.render_farm.queue import (
    BLACKLISTED_WORKERS_FIELD,
    IS_RENDERING_FOLDER,
    RENDER_FAILED_FOLDER,
)
from portable_pipe_tools.render_farm.render_job import RenderJob
from portable_pipe_tools.render_farm.render_time import format_render_time
from portable_pipe_tools.render_farm.sort_render_jobs import (
    default_sort_descending,
    sort_render_jobs,
)
from portable_pipe_tools.render_farm.workers import (
    WorkerRecord,
    create_worker_stop_request,
    list_render_workers,
)
from portable_pipe_tools.apps.farm_render_manager_icon import (
    apply_farm_render_manager_icon,
    configure_windows_app_identity,
)


WINDOW_BACKGROUND = "#252629"
PANEL_BACKGROUND = "#2d2f32"
PANEL_HEADER = "#3b3d40"
TOOLBAR_BACKGROUND = "#333538"
BORDER_COLOR = "#161719"
TEXT_COLOR = "#d8dadd"
MUTED_TEXT = "#a5a9ae"
SELECTION_COLOR = "#315f7a"


@dataclass(frozen=True)
class ListColumn:
    key: str
    heading: str
    width: int
    anchor: str = "w"
    stretch: bool = False


# The column definitions are intentionally centralized. The real queue schema can
# replace or extend them without requiring layout changes.
JOB_COLUMNS = (
    ListColumn("job_name", "Job Name", 125),
    ListColumn("worker", "Worker", 94),
    ListColumn("user", "User", 68),
    ListColumn("status", "Status", 71),
    ListColumn("render_time", "Render Time", 85, anchor="center"),
    ListColumn("errors", "Errors", 41, anchor="center"),
    ListColumn("progress", "Progress", 80, anchor="center"),
    ListColumn("submitted", "Submitted", 135),
    ListColumn("completed", "Completed", 135),
)

WORKER_COLUMNS = (
    ListColumn("worker_name", "Worker", 145, stretch=True),
    ListColumn("project", "Project", 100),
    ListColumn("status", "Status", 135),
    ListColumn("current_job", "Current Job", 170),
    ListColumn("last_seen", "Last Seen", 85),
    ListColumn("commit", "Commit", 90),
)

PROJECT_CHOICES = ("All Projects",)
JobSelectionKey = tuple[str, str]
WorkerSelectionKey = tuple[str, str, str]
JOBS_VIEW = "jobs"
WORKERS_VIEW = "workers"
PACIFIC_STANDARD_TIME = timezone(timedelta(hours=-8), name="PST")
PACIFIC_DAYLIGHT_TIME = timezone(timedelta(hours=-7), name="PDT")
RENDER_TIME_REFRESH_MILLISECONDS = 1_000


def _nth_sunday(year: int, month: int, occurrence: int) -> int:
    first_weekday = datetime(year, month, 1).weekday()
    first_sunday = 1 + ((6 - first_weekday) % 7)
    return first_sunday + (occurrence - 1) * 7


def _pacific_timezone_for(utc_value: datetime) -> timezone:
    year = utc_value.year
    daylight_start_utc = datetime(
        year,
        3,
        _nth_sunday(year, 3, 2),
        10,
        tzinfo=timezone.utc,
    )
    daylight_end_utc = datetime(
        year,
        11,
        _nth_sunday(year, 11, 1),
        9,
        tzinfo=timezone.utc,
    )
    if daylight_start_utc <= utc_value < daylight_end_utc:
        return PACIFIC_DAYLIGHT_TIME
    return PACIFIC_STANDARD_TIME


def format_submitted_pacific(value: str) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""

    normalized_value = raw_value
    if normalized_value.upper().endswith("Z"):
        normalized_value = normalized_value[:-1] + "+00:00"
    try:
        submitted = datetime.fromisoformat(normalized_value)
    except ValueError:
        return raw_value

    if submitted.tzinfo is None:
        submitted = submitted.replace(tzinfo=timezone.utc)
    submitted_utc = submitted.astimezone(timezone.utc)
    submitted_pacific = submitted_utc.astimezone(
        _pacific_timezone_for(submitted_utc)
    )
    return submitted_pacific.strftime("%Y-%m-%d  |  %H:%M")


class FarmRenderManagerApp:
    """Deadline-inspired UI for monitoring render jobs and their details."""

    def __init__(
        self,
        settings_path: Path | None = None,
        prompt_on_startup: bool = True,
    ) -> None:
        configure_windows_app_identity()
        self.root = tk.Tk()
        self.root.title("Farm Render Manager")
        self.root.geometry("1280x800")
        self.root.minsize(960, 620)
        self._app_icon_image = apply_farm_render_manager_icon(self.root)

        self.settings_path = settings_path or get_default_manager_settings_path()
        try:
            dispatcher_connection = load_dispatcher_connection("manager")
        except Exception:
            dispatcher_connection = None
        self.dispatcher_client = (
            DispatcherClient(dispatcher_connection)
            if dispatcher_connection is not None
            else None
        )
        self.project_var = tk.StringVar(value=PROJECT_CHOICES[0])
        self.auto_refresh_var = tk.BooleanVar(
            value=load_saved_auto_refresh_enabled(self.settings_path)
        )
        refresh_interval_minutes = load_saved_auto_refresh_interval_minutes(
            self.settings_path
        )
        self.auto_refresh_interval_var = tk.StringVar(
            value=format_auto_refresh_interval(refresh_interval_minutes)
        )
        self.summary_var = tk.StringVar(
            value="Jobs: 0    Queued: 0    Rendering: 0    Completed: 0    Failed: 0"
        )
        self.list_title_var = tk.StringVar(value="Jobs")
        self.list_count_var = tk.StringVar(value="Render queue")
        self.details_title_var = tk.StringVar(
            value="Job Details - No Job Selected"
        )
        self.detail_count_var = tk.StringVar(value="0 properties")
        self.log_title_var = tk.StringVar(value="Render Log - Current Output")
        self.log_source_var = tk.StringVar(value="Waiting for selection")
        self.status_var = tk.StringVar(value="Ready")
        self.last_update_var = tk.StringVar(value="Last update: --")
        self.repository_status_var = tk.StringVar(
            value="Repository: Not connected"
        )
        self.repository_path: Path | None = None
        self.view_mode = JOBS_VIEW
        self.all_jobs: list[RenderJob] = []
        self.all_workers: list[WorkerRecord] = []
        self.job_sort_column: str | None = None
        self.job_sort_descending = False
        self._jobs_by_item: dict[str, RenderJob] = {}
        self._workers_by_item: dict[str, WorkerRecord] = {}
        self._auto_refresh_results: Queue[AutoRefreshResult] = Queue()
        self._auto_refresh_after_id: str | None = None
        self._refresh_feedback_after_id: str | None = None
        self._render_time_after_id: str | None = None
        self._closing = False
        self.auto_refresh_worker = AutoRefreshWorker(
            repository_path_provider=lambda: self.repository_path,
            result_queue=self._auto_refresh_results,
            interval_seconds=refresh_interval_minutes * 60,
        )

        self._configure_styles()
        self._build_menu()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._schedule_render_time_refresh()
        if self.auto_refresh_var.get():
            self.auto_refresh_worker.start()
        self._schedule_auto_refresh_poll()
        if prompt_on_startup:
            self.root.after_idle(self._initialize_repository)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.root.configure(background=WINDOW_BACKGROUND)
        self.root.option_add("*Font", ("Segoe UI", 9))

        style.configure("App.TFrame", background=WINDOW_BACKGROUND)
        style.configure("Toolbar.TFrame", background=TOOLBAR_BACKGROUND)
        style.configure("Panel.TFrame", background=PANEL_BACKGROUND)
        style.configure("PanelHeader.TFrame", background=PANEL_HEADER)
        style.configure(
            "Toolbar.TLabel",
            background=TOOLBAR_BACKGROUND,
            foreground=TEXT_COLOR,
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
            "ToolbarTitle.TLabel",
            background=TOOLBAR_BACKGROUND,
            foreground="#f0f1f2",
            font=("Segoe UI", 11, "bold"),
        )
        style.configure(
            "Summary.TLabel",
            background=WINDOW_BACKGROUND,
            foreground=MUTED_TEXT,
            font=("Segoe UI", 9),
        )
        style.configure(
            "PanelHeader.TLabel",
            background=PANEL_HEADER,
            foreground=TEXT_COLOR,
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "PanelCount.TLabel",
            background=PANEL_HEADER,
            foreground=MUTED_TEXT,
            font=("Segoe UI", 8),
        )
        style.configure(
            "Status.TLabel",
            background=TOOLBAR_BACKGROUND,
            foreground=MUTED_TEXT,
            font=("Segoe UI", 8),
        )
        style.configure(
            "Deadline.TCombobox",
            fieldbackground="#202124",
            background="#45484c",
            foreground=TEXT_COLOR,
            arrowcolor=TEXT_COLOR,
            bordercolor=BORDER_COLOR,
            lightcolor="#56595d",
            darkcolor=BORDER_COLOR,
            padding=3,
        )
        style.map(
            "Deadline.TCombobox",
            fieldbackground=[("readonly", "#202124")],
            foreground=[("readonly", TEXT_COLOR)],
            selectbackground=[("readonly", "#202124")],
            selectforeground=[("readonly", TEXT_COLOR)],
        )
        style.configure(
            "Deadline.TButton",
            background="#45484c",
            foreground=TEXT_COLOR,
            bordercolor=BORDER_COLOR,
            lightcolor="#56595d",
            darkcolor=BORDER_COLOR,
            padding=(10, 4),
        )
        style.map(
            "Deadline.TButton",
            background=[("active", "#55585c"), ("pressed", "#292b2e")],
            foreground=[("disabled", "#74777b")],
        )
        style.configure(
            "RefreshSuccess.TButton",
            background="#347149",
            foreground="#ffffff",
            bordercolor="#1d442a",
            lightcolor="#4b8c60",
            darkcolor="#1d442a",
            padding=(10, 4),
        )
        style.map(
            "RefreshSuccess.TButton",
            background=[("active", "#3f8256")],
        )
        style.configure(
            "RefreshFailed.TButton",
            background="#8a3e3e",
            foreground="#ffffff",
            bordercolor="#552323",
            lightcolor="#a75252",
            darkcolor="#552323",
            padding=(10, 4),
        )
        style.configure(
            "Deadline.TCheckbutton",
            background=TOOLBAR_BACKGROUND,
            foreground=TEXT_COLOR,
            indicatorbackground="#202124",
            indicatorforeground="#74d680",
            bordercolor=BORDER_COLOR,
            padding=(5, 2),
        )
        style.map(
            "Deadline.TCheckbutton",
            background=[("active", TOOLBAR_BACKGROUND)],
            foreground=[("active", "#ffffff")],
        )
        style.configure(
            "Deadline.Treeview",
            background=PANEL_BACKGROUND,
            fieldbackground=PANEL_BACKGROUND,
            foreground=TEXT_COLOR,
            borderwidth=0,
            relief="flat",
            rowheight=24,
            font=("Segoe UI", 9),
        )
        style.map(
            "Deadline.Treeview",
            background=[("selected", SELECTION_COLOR)],
            foreground=[("selected", "#ffffff")],
        )
        style.configure(
            "Deadline.Treeview.Heading",
            background="#45474a",
            foreground="#e4e5e6",
            bordercolor=BORDER_COLOR,
            lightcolor="#5a5d61",
            darkcolor=BORDER_COLOR,
            relief="flat",
            padding=(5, 4),
            font=("Segoe UI", 8, "bold"),
        )
        style.map(
            "Deadline.Treeview.Heading",
            background=[("active", "#53565a")],
        )
        style.configure(
            "Deadline.Vertical.TScrollbar",
            background="#484b4f",
            troughcolor="#242528",
            bordercolor=BORDER_COLOR,
            arrowcolor=TEXT_COLOR,
        )
        style.configure(
            "Deadline.Horizontal.TScrollbar",
            background="#484b4f",
            troughcolor="#242528",
            bordercolor=BORDER_COLOR,
            arrowcolor=TEXT_COLOR,
        )
        style.configure(
            "Deadline.TPanedwindow",
            background=WINDOW_BACKGROUND,
            sashwidth=7,
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
        for menu_name, item_names in (
            ("File", ("Change Dropbox Folder...", "Exit")),
            ("Edit", ("Select All", "Clear Selection")),
            ("View", ("Refresh", "Reset Layout")),
            ("Tools", ("Options...",)),
            ("Help", ("About Farm Render Manager",)),
        ):
            menu = tk.Menu(menu_bar, tearoff=False, **menu_options)
            for item_name in item_names:
                if item_name == "Exit":
                    menu.add_command(label=item_name, command=self._on_close)
                elif item_name == "Change Dropbox Folder...":
                    menu.add_command(
                        label=item_name,
                        command=self._browse_repository_folder,
                    )
                elif item_name == "Select All":
                    menu.add_command(
                        label=item_name,
                        accelerator="Ctrl+A",
                        command=self._select_all_jobs,
                    )
                elif item_name == "Clear Selection":
                    menu.add_command(
                        label=item_name,
                        command=self._clear_job_selection,
                    )
                else:
                    menu.add_command(label=item_name)
            menu_bar.add_cascade(label=menu_name, menu=menu)
        self.root.configure(menu=menu_bar)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, style="App.TFrame")
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        self._build_toolbar(outer)

        ttk.Label(
            outer,
            textvariable=self.summary_var,
            style="Summary.TLabel",
        ).grid(row=1, column=0, sticky="ew", padx=8, pady=(5, 4))

        vertical_pane = ttk.Panedwindow(
            outer,
            orient=tk.VERTICAL,
            style="Deadline.TPanedwindow",
        )
        vertical_pane.grid(row=2, column=0, sticky="nsew", padx=5)

        upper = ttk.Frame(vertical_pane, style="App.TFrame")
        upper.columnconfigure(0, weight=1)
        upper.rowconfigure(0, weight=1)
        vertical_pane.add(upper, weight=3)

        log_container = ttk.Frame(vertical_pane, style="App.TFrame")
        log_container.columnconfigure(0, weight=1)
        log_container.rowconfigure(0, weight=1)
        vertical_pane.add(log_container, weight=2)

        horizontal_pane = ttk.Panedwindow(
            upper,
            orient=tk.HORIZONTAL,
            style="Deadline.TPanedwindow",
        )
        horizontal_pane.grid(row=0, column=0, sticky="nsew")

        jobs_shell, jobs_content = self._create_panel(
            horizontal_pane,
            title_variable=self.list_title_var,
            count_variable=self.list_count_var,
        )
        horizontal_pane.add(jobs_shell, weight=6)

        details_shell, details_content = self._create_panel(
            horizontal_pane,
            title_variable=self.details_title_var,
            count_variable=self.detail_count_var,
        )
        horizontal_pane.add(details_shell, weight=4)

        self.job_list_frame = ttk.Frame(jobs_content, style="Panel.TFrame")
        self.job_list_frame.grid(row=0, column=0, sticky="nsew")
        self.job_list_frame.columnconfigure(0, weight=1)
        self.job_list_frame.rowconfigure(0, weight=1)
        self.worker_list_frame = ttk.Frame(jobs_content, style="Panel.TFrame")
        self.worker_list_frame.grid(row=0, column=0, sticky="nsew")
        self.worker_list_frame.columnconfigure(0, weight=1)
        self.worker_list_frame.rowconfigure(0, weight=1)

        self._build_job_list(self.job_list_frame)
        self._build_worker_list(self.worker_list_frame)
        self.job_list_frame.tkraise()
        self._build_job_detail_list(details_content)
        self._build_log_panel(log_container)
        self._build_status_bar(outer)

    def _build_toolbar(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent, style="Toolbar.TFrame", padding=(8, 6))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(7, weight=1)

        ttk.Label(
            toolbar,
            text="Farm Render Manager",
            style="ToolbarTitle.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=(0, 14))

        ttk.Separator(toolbar, orient="vertical").grid(
            row=0,
            column=1,
            sticky="ns",
            padx=(0, 14),
        )

        ttk.Label(
            toolbar,
            text="Project:",
            style="Toolbar.TLabel",
        ).grid(row=0, column=2, sticky="w", padx=(0, 6))

        self.project_combo = ttk.Combobox(
            toolbar,
            textvariable=self.project_var,
            values=PROJECT_CHOICES,
            state="readonly",
            width=28,
            style="Deadline.TCombobox",
        )
        self.project_combo.grid(row=0, column=3, sticky="w", padx=(0, 7))
        self.project_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._apply_project_filter(),
        )

        self.refresh_button = ttk.Button(
            toolbar,
            text="Refresh",
            style="Deadline.TButton",
            command=self._on_manual_refresh_clicked,
        )
        self.refresh_button.grid(row=0, column=4, sticky="w")

        ttk.Checkbutton(
            toolbar,
            text="Auto-refresh",
            variable=self.auto_refresh_var,
            command=self._on_auto_refresh_toggled,
            style="Deadline.TCheckbutton",
        ).grid(row=0, column=5, sticky="w", padx=(8, 0))

        self.auto_refresh_interval_combo = ttk.Combobox(
            toolbar,
            textvariable=self.auto_refresh_interval_var,
            values=AUTO_REFRESH_INTERVAL_LABELS,
            state="readonly",
            width=10,
            style="Deadline.TCombobox",
        )
        self.auto_refresh_interval_combo.grid(
            row=0,
            column=6,
            sticky="w",
            padx=(7, 0),
        )
        self.auto_refresh_interval_combo.bind(
            "<<ComboboxSelected>>",
            self._on_auto_refresh_interval_selected,
        )

        self.view_toggle_button = ttk.Button(
            toolbar,
            text="Workers",
            style="Deadline.TButton",
            command=self._toggle_list_view,
        )
        self.view_toggle_button.grid(
            row=0,
            column=8,
            sticky="e",
            padx=(8, 12),
        )

        self.repository_status_label = ttk.Label(
            toolbar,
            textvariable=self.repository_status_var,
            style="RepositoryDisconnected.TLabel",
        )
        self.repository_status_label.grid(row=0, column=9, sticky="e")

    def _create_panel(
        self,
        parent: ttk.Frame,
        *,
        title: str | None = None,
        title_variable: tk.StringVar | None = None,
        count_text: str | None = None,
        count_variable: tk.StringVar | None = None,
    ) -> tuple[tk.Frame, ttk.Frame]:
        shell = tk.Frame(
            parent,
            background=BORDER_COLOR,
            borderwidth=1,
            relief="solid",
        )
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)

        header = ttk.Frame(shell, style="PanelHeader.TFrame", padding=(7, 4))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        title_options: dict[str, Any] = {"style": "PanelHeader.TLabel"}
        if title_variable is not None:
            title_options["textvariable"] = title_variable
        else:
            title_options["text"] = title or ""
        ttk.Label(header, **title_options).grid(row=0, column=0, sticky="w")

        count_options: dict[str, Any] = {"style": "PanelCount.TLabel"}
        if count_variable is not None:
            count_options["textvariable"] = count_variable
        else:
            count_options["text"] = count_text or ""
        ttk.Label(header, **count_options).grid(row=0, column=1, sticky="e")

        content = ttk.Frame(shell, style="Panel.TFrame")
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        return shell, content

    def _build_job_list(self, parent: ttk.Frame) -> None:
        self.job_tree = self._create_tree(
            parent,
            JOB_COLUMNS,
            selectmode="extended",
        )
        self._configure_status_tags(self.job_tree)
        for column in JOB_COLUMNS:
            self.job_tree.heading(
                column.key,
                command=lambda key=column.key: self._queue_job_sort(key),
            )
        self.job_tree.bind("<<TreeviewSelect>>", self._on_job_selected)
        self.job_tree.bind("<Button-3>", self._show_job_context_menu)
        self.job_tree.bind("<Delete>", self._on_delete_key)
        self.job_tree.bind("<Control-a>", self._select_all_jobs)

        self.job_context_menu = tk.Menu(
            self.root,
            tearoff=False,
            background="#303236",
            foreground=TEXT_COLOR,
            activebackground="#8a3e3e",
            activeforeground="#ffffff",
            borderwidth=0,
        )
        self.job_context_menu.add_command(
            label="Resubmit",
            command=self._resubmit_selected_jobs,
        )
        self._resubmit_job_menu_index = int(self.job_context_menu.index("end"))
        self.job_context_menu.add_command(
            label="Clear Black List",
            command=self._clear_selected_job_blacklists,
        )
        self._clear_blacklist_menu_index = int(self.job_context_menu.index("end"))
        self.job_context_menu.add_separator()
        self.job_context_menu.add_command(
            label="Delete",
            accelerator="Del",
            command=self._delete_selected_jobs,
        )

    def _build_worker_list(self, parent: ttk.Frame) -> None:
        self.worker_tree = self._create_tree(
            parent,
            WORKER_COLUMNS,
            selectmode="browse",
        )
        self._configure_status_tags(self.worker_tree)
        self.worker_tree.bind("<<TreeviewSelect>>", self._on_worker_selected)
        self.worker_tree.bind("<Button-3>", self._show_worker_context_menu)

        self.worker_context_menu = tk.Menu(
            self.root,
            tearoff=False,
            background="#303236",
            foreground=TEXT_COLOR,
            activebackground="#8a3e3e",
            activeforeground="#ffffff",
            borderwidth=0,
        )
        self.worker_context_menu.add_command(
            label="STOP Worker",
            command=self._stop_selected_worker,
        )

    def _build_job_detail_list(self, parent: ttk.Frame) -> None:
        self.job_detail_tree = ttk.Treeview(
            parent,
            columns=("value",),
            show="tree headings",
            selectmode="browse",
            style="Deadline.Treeview",
        )
        self.job_detail_tree.grid(row=0, column=0, sticky="nsew")
        self.job_detail_tree.heading("#0", text="Property", anchor="w")
        self.job_detail_tree.heading("value", text="Value", anchor="w")
        self.job_detail_tree.column(
            "#0",
            width=175,
            minwidth=120,
            anchor="w",
            stretch=False,
        )
        self.job_detail_tree.column(
            "value",
            width=290,
            minwidth=140,
            anchor="w",
            stretch=True,
        )

        y_scroll = ttk.Scrollbar(
            parent,
            orient="vertical",
            command=self.job_detail_tree.yview,
            style="Deadline.Vertical.TScrollbar",
        )
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(
            parent,
            orient="horizontal",
            command=self.job_detail_tree.xview,
            style="Deadline.Horizontal.TScrollbar",
        )
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.job_detail_tree.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )
        self.job_detail_tree.tag_configure(
            "section",
            background="#3b3d40",
            foreground="#f0f1f2",
            font=("Segoe UI", 9, "bold"),
        )
        self._configure_status_tags(self.job_detail_tree)

    def _create_tree(
        self,
        parent: ttk.Frame,
        columns: tuple[ListColumn, ...],
        selectmode: str = "browse",
    ) -> ttk.Treeview:
        column_keys = tuple(column.key for column in columns)
        tree = ttk.Treeview(
            parent,
            columns=column_keys,
            show="headings",
            selectmode=selectmode,
            style="Deadline.Treeview",
        )
        tree.grid(row=0, column=0, sticky="nsew")

        for column in columns:
            tree.heading(column.key, text=column.heading, anchor=column.anchor)
            tree.column(
                column.key,
                width=column.width,
                minwidth=min(50, column.width),
                anchor=column.anchor,
                stretch=column.stretch,
            )

        y_scroll = ttk.Scrollbar(
            parent,
            orient="vertical",
            command=tree.yview,
            style="Deadline.Vertical.TScrollbar",
        )
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(
            parent,
            orient="horizontal",
            command=tree.xview,
            style="Deadline.Horizontal.TScrollbar",
        )
        x_scroll.grid(row=1, column=0, sticky="ew")
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        return tree

    def _configure_status_tags(self, tree: ttk.Treeview) -> None:
        tree.tag_configure("queued", foreground="#d6d7d9")
        tree.tag_configure("rendering", foreground="#74d680")
        tree.tag_configure("done", foreground="#70aee8")
        tree.tag_configure("failed", foreground="#ff7777")
        tree.tag_configure("waiting", foreground="#74d680")
        tree.tag_configure("stopping", foreground="#e6c56c")
        tree.tag_configure("stale", foreground="#ff7777")

    def _build_log_panel(self, parent: ttk.Frame) -> None:
        log_shell, log_content = self._create_panel(
            parent,
            title_variable=self.log_title_var,
            count_variable=self.log_source_var,
        )
        log_shell.grid(row=0, column=0, sticky="nsew", pady=(5, 0))

        self.log_text = tk.Text(
            log_content,
            wrap="none",
            state="disabled",
            height=10,
            relief="flat",
            borderwidth=0,
            background="#1d1e20",
            foreground="#c9cccf",
            insertbackground="#ffffff",
            selectbackground=SELECTION_COLOR,
            font=("Consolas", 9),
            padx=7,
            pady=6,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(
            log_content,
            orient="vertical",
            command=self.log_text.yview,
            style="Deadline.Vertical.TScrollbar",
        )
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(
            log_content,
            orient="horizontal",
            command=self.log_text.xview,
            style="Deadline.Horizontal.TScrollbar",
        )
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.log_text.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )

    def _build_status_bar(self, parent: ttk.Frame) -> None:
        status_bar = ttk.Frame(parent, style="Toolbar.TFrame", padding=(7, 3))
        status_bar.grid(row=3, column=0, sticky="ew", pady=(5, 0))
        status_bar.columnconfigure(1, weight=1)
        ttk.Label(
            status_bar,
            textvariable=self.status_var,
            style="Status.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            status_bar,
            textvariable=self.last_update_var,
            style="Status.TLabel",
        ).grid(row=0, column=2, sticky="e")

    def _toggle_list_view(self) -> None:
        if self.view_mode == JOBS_VIEW:
            self.view_mode = WORKERS_VIEW
            self.worker_list_frame.tkraise()
            self.list_title_var.set("Workers")
            self.list_count_var.set("Farm workers")
            self.log_title_var.set("Worker Status - Heartbeat JSON")
            self.view_toggle_button.configure(text="Jobs")
        else:
            self.view_mode = JOBS_VIEW
            self.job_list_frame.tkraise()
            self.list_title_var.set("Jobs")
            self.list_count_var.set("Render queue")
            self.log_title_var.set("Render Log - Current Output")
            self.view_toggle_button.configure(text="Workers")
        self._apply_project_filter()

    def set_projects(self, projects: Iterable[str]) -> None:
        """Replace the project filter choices while preserving All Projects."""
        choices = [PROJECT_CHOICES[0]]
        choices.extend(project for project in projects if project not in choices)
        self.project_combo.configure(values=tuple(choices))
        if self.project_var.get() not in choices:
            self.project_var.set(PROJECT_CHOICES[0])

    def _update_project_choices(self) -> None:
        projects = {job.project for job in self.all_jobs}
        projects.update(worker.project for worker in self.all_workers)
        self.set_projects(sorted(projects, key=str.casefold))

    def _initialize_repository(self) -> None:
        saved_folder = load_saved_dropbox_folder(self.settings_path)
        if saved_folder:
            saved_path = Path(saved_folder).expanduser()
            if saved_path.is_dir():
                self._set_repository_connected(saved_path)
            else:
                self.repository_path = None
                self.repository_status_var.set("Repository: Folder unavailable")
                self.repository_status_label.configure(
                    style="RepositoryUnavailable.TLabel"
                )
                self.status_var.set(
                    f"Saved Dropbox folder was not found: {saved_path}"
                )
            return

        self._browse_repository_folder(first_startup=True)

    def _browse_repository_folder(self, first_startup: bool = False) -> None:
        title = (
            "First Time Setup - Choose Dropbox Folder"
            if first_startup
            else "Choose Dropbox Folder"
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
            self.status_var.set("Dropbox connection has not been configured")
            return

        selected_path = Path(selected).expanduser()
        if not selected_path.is_dir():
            messagebox.showerror(
                "Farm Render Manager",
                f"The selected Dropbox folder does not exist:\n{selected_path}",
                parent=self.root,
            )
            return

        try:
            save_dropbox_folder(selected_path, self.settings_path)
        except Exception as error:
            messagebox.showerror(
                "Farm Render Manager",
                f"Could not save the local configuration:\n{error}",
                parent=self.root,
            )
            self.status_var.set(f"Could not save configuration: {error}")
            return

        self._set_repository_connected(selected_path)

    def _set_repository_connected(self, dropbox_folder: Path) -> None:
        self.repository_path = dropbox_folder
        self.repository_status_var.set("Repository: Connected")
        self.repository_status_label.configure(style="RepositoryConnected.TLabel")
        self.status_var.set(f"Connected to Dropbox folder: {dropbox_folder}")
        self._refresh_jobs()

    def _refresh_jobs(self) -> bool:
        if self.repository_path is None:
            self.status_var.set("Connect a Dropbox repository before refreshing")
            return False

        selected_job_keys = tuple(
            (job.project.casefold(), job.job_id)
            for item_id in self.job_tree.selection()
            if (job := self._jobs_by_item.get(item_id)) is not None
        )
        selected_worker_keys = tuple(
            (worker.project.casefold(), worker.worker_name.casefold(), worker.session_id)
            for item_id in self.worker_tree.selection()
            if (worker := self._workers_by_item.get(item_id)) is not None
        )

        try:
            jobs = get_all_render_jobs(self.repository_path)
            workers = list_render_workers(self.repository_path)
        except Exception as error:
            self.status_var.set(f"Could not load render jobs: {error}")
            messagebox.showerror(
                "Farm Render Manager",
                f"Could not load render jobs:\n{error}",
                parent=self.root,
            )
            return False

        self.all_jobs = jobs
        self.all_workers = workers
        self._update_project_choices()
        self._apply_project_filter(selected_job_keys, selected_worker_keys)
        unreadable_count = sum(job.load_error is not None for job in jobs)
        warning = (
            f" ({unreadable_count} with incomplete metadata)"
            if unreadable_count
            else ""
        )
        self.status_var.set(
            f"Loaded {len(jobs)} render jobs and {len(workers)} workers{warning}"
        )
        self.last_update_var.set(
            f"Last update: {datetime.now().astimezone().strftime('%H:%M:%S')}"
        )
        return True

    def _on_manual_refresh_clicked(self) -> None:
        if self._refresh_feedback_after_id is not None:
            self.root.after_cancel(self._refresh_feedback_after_id)
            self._refresh_feedback_after_id = None

        self.refresh_button.configure(
            text="Refreshing...",
            state="disabled",
            style="Deadline.TButton",
        )
        self.status_var.set("Refreshing render jobs...")
        self.root.update_idletasks()

        succeeded = self._refresh_jobs()
        if succeeded:
            self.refresh_button.configure(
                text="Refreshed  ✓",
                state="normal",
                style="RefreshSuccess.TButton",
            )
        else:
            self.refresh_button.configure(
                text="Refresh failed",
                state="normal",
                style="RefreshFailed.TButton",
            )
        self._refresh_feedback_after_id = self.root.after(
            1_500,
            self._reset_refresh_button,
        )

    def _reset_refresh_button(self) -> None:
        self._refresh_feedback_after_id = None
        self.refresh_button.configure(
            text="Refresh",
            state="normal",
            style="Deadline.TButton",
        )

    def _on_auto_refresh_toggled(self) -> None:
        enabled = self.auto_refresh_var.get()
        try:
            save_auto_refresh_enabled(enabled, self.settings_path)
        except Exception as error:
            messagebox.showerror(
                "Farm Render Manager",
                f"Could not save the auto-refresh setting:\n{error}",
                parent=self.root,
            )
            self.status_var.set(f"Could not save auto-refresh setting: {error}")
            self.auto_refresh_var.set(self.auto_refresh_worker.running)
            return

        if enabled:
            self.auto_refresh_worker.start()
            self.status_var.set(
                "Auto-refresh enabled (every "
                f"{self.auto_refresh_interval_var.get()})"
            )
        else:
            self.auto_refresh_worker.stop()
            self.status_var.set("Auto-refresh disabled")

    def _on_auto_refresh_interval_selected(
        self,
        _event: tk.Event[tk.Misc] | None = None,
    ) -> None:
        previous_minutes = int(self.auto_refresh_worker.interval_seconds / 60)
        try:
            minutes = parse_auto_refresh_interval(
                self.auto_refresh_interval_var.get()
            )
            save_auto_refresh_interval_minutes(minutes, self.settings_path)
        except Exception as error:
            self.auto_refresh_interval_var.set(
                format_auto_refresh_interval(previous_minutes)
            )
            messagebox.showerror(
                "Farm Render Manager",
                f"Could not save the auto-refresh interval:\n{error}",
                parent=self.root,
            )
            self.status_var.set(
                f"Could not save auto-refresh interval: {error}"
            )
            return

        was_running = self.auto_refresh_worker.running
        if was_running:
            self.auto_refresh_worker.stop()
        self.auto_refresh_worker.set_interval_seconds(minutes * 60)
        if was_running and self.auto_refresh_var.get():
            self.auto_refresh_worker.start()
        self.status_var.set(
            f"Auto-refresh interval set to {format_auto_refresh_interval(minutes)}"
        )

    def _schedule_auto_refresh_poll(self) -> None:
        self._auto_refresh_after_id = self.root.after(
            250,
            self._poll_auto_refresh_results,
        )

    def _schedule_render_time_refresh(self) -> None:
        self._render_time_after_id = self.root.after(
            RENDER_TIME_REFRESH_MILLISECONDS,
            self._refresh_render_time_cells,
        )

    def _refresh_render_time_cells(self) -> None:
        self._render_time_after_id = None
        if self._closing:
            return

        now_utc = datetime.now(timezone.utc)
        for item_id, job in self._jobs_by_item.items():
            if job.status.casefold() != "rendering":
                continue
            self.job_tree.set(
                item_id,
                "render_time",
                format_render_time(
                    job.render_started_utc,
                    job.render_finished_utc,
                    running=True,
                    now_utc=now_utc,
                ),
            )
        self._schedule_render_time_refresh()

    def _poll_auto_refresh_results(self) -> None:
        self._auto_refresh_after_id = None
        if self._closing:
            return

        while True:
            try:
                result = self._auto_refresh_results.get_nowait()
            except Empty:
                break

            if not self.auto_refresh_var.get():
                continue
            if self.repository_path != result.repository_path:
                continue
            if result.error is not None:
                self.status_var.set(f"Auto-refresh failed: {result.error}")
                continue

            selected_job_keys = tuple(
                (job.project.casefold(), job.job_id)
                for item_id in self.job_tree.selection()
                if (job := self._jobs_by_item.get(item_id)) is not None
            )
            selected_worker_keys = tuple(
                (
                    worker.project.casefold(),
                    worker.worker_name.casefold(),
                    worker.session_id,
                )
                for item_id in self.worker_tree.selection()
                if (worker := self._workers_by_item.get(item_id)) is not None
            )
            jobs = list(result.jobs)
            workers = list(result.workers)
            self.all_jobs = jobs
            self.all_workers = workers
            self._update_project_choices()
            self._apply_project_filter(selected_job_keys, selected_worker_keys)
            unreadable_count = sum(job.load_error is not None for job in jobs)
            warning = (
                f" ({unreadable_count} with incomplete metadata)"
                if unreadable_count
                else ""
            )
            self.status_var.set(
                f"Auto-refreshed {len(jobs)} render jobs and "
                f"{len(workers)} workers{warning}"
            )
            self.last_update_var.set(
                "Last update: "
                f"{datetime.now().astimezone().strftime('%H:%M:%S')}"
            )

        self._schedule_auto_refresh_poll()

    def _apply_project_filter(
        self,
        selected_job_keys: tuple[JobSelectionKey, ...] = (),
        selected_worker_keys: tuple[WorkerSelectionKey, ...] = (),
    ) -> None:
        selected_project = self.project_var.get()
        if self.view_mode == WORKERS_VIEW:
            visible_workers = (
                self.all_workers
                if selected_project == PROJECT_CHOICES[0]
                else [
                    worker
                    for worker in self.all_workers
                    if worker.project == selected_project
                ]
            )
            self.set_workers(visible_workers, selected_worker_keys)
            return

        visible_jobs = (
            self.all_jobs
            if selected_project == PROJECT_CHOICES[0]
            else [
                job for job in self.all_jobs if job.project == selected_project
            ]
        )
        if self.job_sort_column is not None:
            visible_jobs = sort_render_jobs(
                visible_jobs,
                self.job_sort_column,
                self.job_sort_descending,
            )
        self.set_jobs(visible_jobs, selected_job_keys)

    def _queue_job_sort(self, column: str) -> None:
        """Let Tk finish the heading release before rebuilding the job rows."""
        self.root.after_idle(self._sort_jobs_by_column, column)

    def _sort_jobs_by_column(self, column: str) -> None:
        selected_job_keys = tuple(
            (job.project.casefold(), job.job_id)
            for item_id in self.job_tree.selection()
            if (job := self._jobs_by_item.get(item_id)) is not None
        )
        if column == self.job_sort_column:
            self.job_sort_descending = not self.job_sort_descending
        else:
            self.job_sort_column = column
            self.job_sort_descending = default_sort_descending(column)

        self._update_job_sort_headings()
        self._apply_project_filter(selected_job_keys)

    def _update_job_sort_headings(self) -> None:
        for column in JOB_COLUMNS:
            marker = ""
            if column.key == self.job_sort_column:
                marker = " \u25bc" if self.job_sort_descending else " \u25b2"
            self.job_tree.heading(column.key, text=f"{column.heading}{marker}")

    def set_jobs(
        self,
        jobs: Iterable[RenderJob],
        selected_job_keys: tuple[JobSelectionKey, ...] = (),
    ) -> None:
        """Replace the visible rows with RenderJob objects."""
        self.job_tree.delete(*self.job_tree.get_children())
        self._jobs_by_item.clear()
        self.details_title_var.set("Job Details - No Job Selected")
        self.set_job_details(None)
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self.log_source_var.set("Waiting for selection")
        job_list = list(jobs)
        items_by_job_key: dict[JobSelectionKey, str] = {}

        for job in job_list:
            worker = job.worker if job.status.casefold() == "rendering" else ""
            user = job.submitted_user or job.submitted_by
            values = (
                job.job_name,
                worker,
                user,
                job.status.title(),
                format_render_time(
                    job.render_started_utc,
                    job.render_finished_utc,
                    running=job.status.casefold() == "rendering",
                ),
                job.error_count,
                f"{job.progress:g}%",
                format_submitted_pacific(job.submitted_utc),
                format_submitted_pacific(job.render_finished_utc),
            )
            tag = self._status_tag(job.status)
            item_id = self.job_tree.insert(
                "",
                "end",
                values=values,
                tags=(tag,) if tag else (),
            )
            self._jobs_by_item[item_id] = job
            items_by_job_key[(job.project.casefold(), job.job_id)] = item_id

        self._update_summary(job_list)
        restored_items = [
            items_by_job_key[key]
            for key in selected_job_keys
            if key in items_by_job_key
        ]
        if restored_items:
            self.job_tree.selection_set(restored_items)
            self.job_tree.focus(restored_items[0])
            self.job_tree.see(restored_items[0])
            self._on_job_selected(None)

    def set_workers(
        self,
        workers: Iterable[WorkerRecord],
        selected_worker_keys: tuple[WorkerSelectionKey, ...] = (),
    ) -> None:
        self.worker_tree.delete(*self.worker_tree.get_children())
        self._workers_by_item.clear()
        self.details_title_var.set("Worker Details - No Worker Selected")
        self.set_worker_details(None)
        self._set_log_text("", "Waiting for selection")
        worker_list = list(workers)
        items_by_worker_key: dict[WorkerSelectionKey, str] = {}

        for worker in worker_list:
            values = (
                worker.worker_name,
                worker.project,
                worker.status_label,
                worker.current_job_label,
                worker.last_seen_label,
                worker.worker_git_commit[:8] or "Unknown",
            )
            item_id = self.worker_tree.insert(
                "",
                "end",
                values=values,
                tags=(self._worker_status_tag(worker),),
            )
            self._workers_by_item[item_id] = worker
            key = (
                worker.project.casefold(),
                worker.worker_name.casefold(),
                worker.session_id,
            )
            items_by_worker_key[key] = item_id

        self._update_worker_summary(worker_list)
        restored_items = [
            items_by_worker_key[key]
            for key in selected_worker_keys
            if key in items_by_worker_key
        ]
        if restored_items:
            selected_item = restored_items[0]
            self.worker_tree.selection_set(selected_item)
            self.worker_tree.focus(selected_item)
            self.worker_tree.see(selected_item)
            self._on_worker_selected(None)

    def set_worker_details(self, worker: WorkerRecord | None) -> None:
        self.job_detail_tree.delete(*self.job_detail_tree.get_children())
        if worker is None:
            self.detail_count_var.set("0 properties")
            return

        sections = (
            (
                "Worker",
                (
                    ("Worker Name", worker.worker_name),
                    ("Machine Name", worker.machine_name or "Unknown"),
                    ("Project", worker.project),
                    ("Status", worker.status_label),
                    ("Last Seen", worker.last_seen_label),
                    ("Stop Requested", "Yes" if worker.stop_requested else "No"),
                ),
            ),
            (
                "Current Job",
                (
                    ("Job ID", worker.current_job_id or "—"),
                    ("Shot", worker.shot_name or "—"),
                    ("Version", worker.render_version or "—"),
                    ("Render Setting", worker.render_setting or "—"),
                ),
            ),
            (
                "Session",
                (
                    ("Session ID", worker.session_id or "Unknown"),
                    ("Process ID", str(worker.process_id or "Unknown")),
                    ("Started UTC", worker.started_utc or "Unknown"),
                    ("Last Heartbeat UTC", worker.last_heartbeat_utc or "Unknown"),
                    ("Git Branch", worker.worker_git_branch or "Unknown"),
                    ("Git Commit", worker.worker_git_commit or "Unknown"),
                    ("Status File", str(worker.status_file)),
                    ("STOP File", str(worker.stop_file)),
                ),
            ),
        )

        property_count = 0
        for section_name, details in sections:
            section_item = self.job_detail_tree.insert(
                "",
                "end",
                text=section_name,
                values=("",),
                tags=("section",),
                open=True,
            )
            for property_name, value in details:
                status_tag = (
                    self._worker_status_tag(worker)
                    if property_name == "Status"
                    else ""
                )
                self.job_detail_tree.insert(
                    section_item,
                    "end",
                    text=property_name,
                    values=(value,),
                    tags=(status_tag,) if status_tag else (),
                )
                property_count += 1

        suffix = "property" if property_count == 1 else "properties"
        self.detail_count_var.set(f"{property_count} {suffix}")

    def _update_worker_summary(self, workers: list[WorkerRecord]) -> None:
        online = sum(not worker.stale for worker in workers)
        rendering = sum(
            not worker.stale and worker.status == "rendering"
            for worker in workers
        )
        stopping = sum(
            not worker.stale
            and (
                worker.stop_requested
                or worker.status == "stopping_after_current_job"
            )
            for worker in workers
        )
        stale = sum(worker.stale for worker in workers)
        self.summary_var.set(
            f"Workers: {len(workers)}    Online: {online}    "
            f"Rendering: {rendering}    Stopping: {stopping}    Stale: {stale}"
        )

    @staticmethod
    def _worker_status_tag(worker: WorkerRecord) -> str:
        if worker.stale:
            return "stale"
        if worker.stop_requested or worker.status == "stopping_after_current_job":
            return "stopping"
        if worker.status == "rendering":
            return "rendering"
        return "waiting"

    def _set_log_text(self, text: str, source: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        if text:
            self.log_text.insert("1.0", text)
        self.log_text.configure(state="disabled")
        self.log_source_var.set(source)

    def set_job_details(self, job: RenderJob | None) -> None:
        """Display grouped property rows for the selected render job."""
        self.job_detail_tree.delete(*self.job_detail_tree.get_children())
        if job is None:
            self.detail_count_var.set("0 properties")
            return

        property_count = 0
        for section in get_render_job_details(job):
            section_item = self.job_detail_tree.insert(
                "",
                "end",
                text=section.name,
                values=("",),
                tags=("section",),
                open=True,
            )
            for detail in section.details:
                status_tag = ""
                if detail.property_name in {"Status", "Result Status"}:
                    status_tag = self._status_tag(detail.value)
                self.job_detail_tree.insert(
                    section_item,
                    "end",
                    text=detail.property_name,
                    values=(detail.value,),
                    tags=(status_tag,) if status_tag else (),
                )
                property_count += 1

        suffix = "property" if property_count == 1 else "properties"
        self.detail_count_var.set(f"{property_count} {suffix}")

    def _update_summary(self, jobs: list[RenderJob]) -> None:
        counts = Counter(self._status_tag(job.status) for job in jobs)
        self.summary_var.set(
            f"Jobs: {len(jobs)}    Queued: {counts['queued']}    "
            f"Rendering: {counts['rendering']}    Completed: {counts['done']}    "
            f"Failed: {counts['failed']}"
        )

    @staticmethod
    def _status_tag(status: str) -> str:
        normalized = status.strip().lower()
        if normalized in {"submitting", "queue", "queued", "pending"}:
            return "queued"
        if normalized in {"rendering", "running", "active"}:
            return "rendering"
        if normalized in {"done", "complete", "completed", "success"}:
            return "done"
        if normalized in {"failed", "failure", "error"}:
            return "failed"
        return ""

    def _on_job_selected(self, _event: tk.Event[tk.Misc]) -> None:
        selection = self.job_tree.selection()
        if not selection:
            return

        job = self._jobs_by_item.get(selection[0])
        if job is None:
            return
        name = job.job_name or "Unnamed Job"
        selection_count = len(selection)
        suffix = f" (+{selection_count - 1} selected)" if selection_count > 1 else ""
        self.details_title_var.set(f"Job Details - {name}{suffix}")
        self.set_job_details(job)
        try:
            log_text = get_render_log(job)
        except Exception as error:
            log_text = f"Could not load render log for {name}:\n{error}"
            self.status_var.set(f"Could not load render log: {error}")
        else:
            self.status_var.set(f"Selected job: {name}")

        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("1.0", log_text)
        self.log_text.configure(state="disabled")
        self.log_text.see("end")
        self.log_text.yview_moveto(1.0)
        self.log_source_var.set(f"{name}{suffix}")

    def _show_job_context_menu(self, event: tk.Event[tk.Misc]) -> str:
        row_id = self.job_tree.identify_row(event.y)
        if not row_id:
            return "break"
        if row_id not in self.job_tree.selection():
            self.job_tree.selection_set(row_id)
        self.job_tree.focus(row_id)
        selected_jobs = self._selected_jobs()
        can_resubmit = bool(selected_jobs) and all(
            job.queue_name == RENDER_FAILED_FOLDER for job in selected_jobs
        )
        can_clear_blacklist = (
            bool(selected_jobs)
            and all(job.queue_name != IS_RENDERING_FOLDER for job in selected_jobs)
            and any(
                bool(job.job_data.get(BLACKLISTED_WORKERS_FIELD))
                for job in selected_jobs
            )
        )
        self.job_context_menu.entryconfigure(
            self._resubmit_job_menu_index,
            state="normal" if can_resubmit else "disabled",
        )
        self.job_context_menu.entryconfigure(
            self._clear_blacklist_menu_index,
            state="normal" if can_clear_blacklist else "disabled",
        )
        try:
            self.job_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.job_context_menu.grab_release()
        return "break"

    def _on_worker_selected(self, _event: tk.Event[tk.Misc] | None) -> None:
        selection = self.worker_tree.selection()
        if not selection:
            return
        worker = self._workers_by_item.get(selection[0])
        if worker is None:
            return

        self.details_title_var.set(f"Worker Details - {worker.worker_name}")
        self.set_worker_details(worker)
        heartbeat_text = json.dumps(worker.raw_data, indent=4, ensure_ascii=False)
        if worker.load_error:
            heartbeat_text = (
                f"Could not read worker status:\n{worker.load_error}\n\n"
                f"Status file: {worker.status_file}"
            )
        self._set_log_text(heartbeat_text, worker.worker_name)
        self.status_var.set(
            f"Selected worker: {worker.worker_name} ({worker.status_label})"
        )

    def _show_worker_context_menu(self, event: tk.Event[tk.Misc]) -> str:
        row_id = self.worker_tree.identify_row(event.y)
        if not row_id:
            return "break"
        self.worker_tree.selection_set(row_id)
        self.worker_tree.focus(row_id)
        self._on_worker_selected(None)
        worker = self._workers_by_item.get(row_id)
        menu_state = (
            "disabled"
            if worker is None or worker.stop_requested
            else "normal"
        )
        self.worker_context_menu.entryconfigure(0, state=menu_state)
        try:
            self.worker_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.worker_context_menu.grab_release()
        return "break"

    def _stop_selected_worker(self) -> None:
        selection = self.worker_tree.selection()
        if not selection:
            return
        worker = self._workers_by_item.get(selection[0])
        if worker is None:
            return

        active_job_note = (
            "\n\nThe worker will interrupt its current render, return the job "
            "to the queue, and then stop."
            if worker.current_job_id or worker.status == "rendering"
            else "\n\nThe waiting worker will stop without claiming another job."
        )
        if worker.stale:
            active_job_note = (
                "\n\nThis worker is stale. The STOP marker will remain pending "
                "and will be honored if that worker returns."
            )
        confirmed = messagebox.askyesno(
            "STOP Render Worker",
            f'Request that "{worker.worker_name}" stop?'
            f"{active_job_note}",
            icon="warning",
            default="no",
            parent=self.root,
        )
        if not confirmed:
            return

        cloud_error: Exception | None = None
        dispatcher_client = getattr(self, "dispatcher_client", None)
        if dispatcher_client is not None:
            try:
                dispatcher_client.request_worker_stop(worker.worker_name)
            except Exception as error:
                cloud_error = error

        try:
            stop_file = create_worker_stop_request(
                worker.farm_root,
                worker.worker_name,
            )
        except Exception as error:
            messagebox.showerror(
                "STOP Render Worker",
                f"Could not create the STOP marker:\n{error}",
                parent=self.root,
            )
            self.status_var.set(f"Could not stop {worker.worker_name}: {error}")
            return

        if cloud_error is None:
            self.status_var.set(
                f"STOP requested for {worker.worker_name}: Cloud Dispatcher + "
                f"{stop_file.name}"
            )
        else:
            self.status_var.set(
                f"STOP marker created for {worker.worker_name}; Cloud request "
                f"will retry when available: {cloud_error}"
            )
        self._refresh_jobs()

    def _select_all_jobs(
        self,
        _event: tk.Event[tk.Misc] | None = None,
    ) -> str:
        if self.view_mode == WORKERS_VIEW:
            return "break"
        items = self.job_tree.get_children()
        if items:
            self.job_tree.selection_set(items)
            self.job_tree.focus(items[0])
            self._on_job_selected(None)
        return "break"

    def _clear_job_selection(self) -> None:
        if self.view_mode == WORKERS_VIEW:
            self.worker_tree.selection_remove(self.worker_tree.selection())
            self.details_title_var.set("Worker Details - No Worker Selected")
            self.set_worker_details(None)
            self._set_log_text("", "Waiting for selection")
            return
        self.job_tree.selection_remove(self.job_tree.selection())
        self.details_title_var.set("Job Details - No Job Selected")
        self.set_job_details(None)
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self.log_source_var.set("Waiting for selection")

    def _on_delete_key(self, _event: tk.Event[tk.Misc]) -> str:
        self._delete_selected_jobs()
        return "break"

    def _selected_jobs(self) -> list[RenderJob]:
        return [
            job
            for item_id in self.job_tree.selection()
            if (job := self._jobs_by_item.get(item_id)) is not None
        ]

    def _clear_selected_job_blacklists(self) -> None:
        selected_jobs = [
            job
            for job in self._selected_jobs()
            if job.queue_name != IS_RENDERING_FOLDER
            and bool(job.job_data.get(BLACKLISTED_WORKERS_FIELD))
        ]
        if not selected_jobs:
            return

        worker_count = sum(
            len(job.job_data.get(BLACKLISTED_WORKERS_FIELD, []))
            for job in selected_jobs
        )
        if len(selected_jobs) == 1:
            prompt = (
                f'Clear {worker_count} blacklisted worker(s) from '
                f'"{selected_jobs[0].job_name}"?'
            )
        else:
            prompt = (
                f"Clear {worker_count} blacklisted worker entries from "
                f"{len(selected_jobs)} selected jobs?"
            )
        prompt += (
            "\n\nAn active render worker may claim an eligible queued job "
            "immediately."
        )
        confirmed = messagebox.askyesno(
            "Clear Render Job Black List",
            prompt,
            icon="warning",
            default="no",
            parent=self.root,
        )
        if not confirmed:
            return

        auto_refresh_was_running = self.auto_refresh_worker.running
        if auto_refresh_was_running:
            self.auto_refresh_worker.stop()
        self.status_var.set("Clearing selected render-job black lists...")
        self.root.update_idletasks()

        changed_count = 0
        errors: list[str] = []
        for job in selected_jobs:
            try:
                changed_count += int(
                    clear_render_job_blacklist(
                        job,
                        getattr(self, "dispatcher_client", None),
                    )
                )
            except Exception as error:
                errors.append(f"{job.job_name}: {error}")

        self._refresh_jobs()
        if auto_refresh_was_running and self.auto_refresh_var.get():
            self.auto_refresh_worker.start()

        if errors:
            messagebox.showerror(
                "Clear Render Job Black List",
                "\n".join(errors),
                parent=self.root,
            )
            self.status_var.set(
                f"Cleared {changed_count} black lists with {len(errors)} errors"
            )
            return

        suffix = "job" if changed_count == 1 else "jobs"
        self.status_var.set(f"Cleared the black list for {changed_count} render {suffix}")

    def _resubmit_selected_jobs(self) -> None:
        selected_jobs = self._selected_jobs()
        if not selected_jobs:
            return
        if any(job.queue_name != RENDER_FAILED_FOLDER for job in selected_jobs):
            messagebox.showerror(
                "Resubmit Render Job",
                f"Only jobs in {RENDER_FAILED_FOLDER} can be resubmitted.",
                parent=self.root,
            )
            return

        if len(selected_jobs) == 1:
            prompt = (
                f'Resubmit failed render job "{selected_jobs[0].job_name}" as a '
                "brand-new queued job?"
            )
        else:
            prompt = (
                f"Resubmit {len(selected_jobs)} failed render jobs as brand-new "
                "queued jobs?"
            )
        prompt += (
            "\n\nEach replacement will receive a new job ID, a fresh submission "
            "time, zero attempts, and an empty black list. After the replacement "
            "is safely queued, the original failed job will be permanently deleted "
            "from both the Cloud Dispatcher and Dropbox."
            "\n\nThe shot, render version, and output paths do not change. If output "
            "already exists for that version, the worker will replace the matching "
            "MP4 and EXR version folder before rendering."
        )
        confirmed = messagebox.askyesno(
            "Resubmit Render Job",
            prompt,
            icon="warning",
            default="no",
            parent=self.root,
        )
        if not confirmed:
            return

        auto_refresh_was_running = self.auto_refresh_worker.running
        if auto_refresh_was_running:
            self.auto_refresh_worker.stop()
        self.status_var.set("Resubmitting selected render jobs...")
        self.root.update_idletasks()

        destinations: list[Path] = []
        errors: list[str] = []
        for job in selected_jobs:
            try:
                destinations.append(
                    resubmit_failed_render_job(
                        job,
                        getattr(self, "dispatcher_client", None),
                    )
                )
            except Exception as error:
                errors.append(f"{job.job_name}: {error}")

        self._refresh_jobs()
        if auto_refresh_was_running and self.auto_refresh_var.get():
            self.auto_refresh_worker.start()

        if errors:
            messagebox.showerror(
                "Resubmit Render Job",
                "\n".join(errors),
                parent=self.root,
            )
            self.status_var.set(
                f"Resubmitted {len(destinations)} render jobs with "
                f"{len(errors)} errors"
            )
            return

        suffix = "job" if len(destinations) == 1 else "jobs"
        self.status_var.set(
            f"Resubmitted {len(destinations)} render {suffix} to "
            f"01_NeedsRendering and deleted the old failed {suffix}"
        )

    def _delete_selected_jobs(self) -> None:
        selected_jobs = self._selected_jobs()
        if not selected_jobs:
            return

        if len(selected_jobs) == 1:
            prompt = (
                f'Permanently delete render job "{selected_jobs[0].job_name}"?'
            )
        else:
            prompt = (
                f"Permanently delete {len(selected_jobs)} selected render jobs?"
            )
        if any(job.status == "rendering" for job in selected_jobs):
            prompt += (
                "\n\nWARNING: A selected job is currently rendering. "
                "Deleting it may interrupt active work."
            )
        prompt += "\n\nThis cannot be undone."

        confirmed = messagebox.askyesno(
            "Delete Render Job",
            prompt,
            icon="warning",
            default="no",
            parent=self.root,
        )
        if not confirmed:
            return

        auto_refresh_was_running = self.auto_refresh_worker.running
        if auto_refresh_was_running:
            self.auto_refresh_worker.stop()
        self.status_var.set("Deleting selected render jobs...")
        self.root.update_idletasks()
        result = delete_render_jobs(selected_jobs)
        self._refresh_jobs()
        if auto_refresh_was_running and self.auto_refresh_var.get():
            self.auto_refresh_worker.start()

        deleted_count = len(result.deleted_folders)
        if result.errors:
            messagebox.showerror(
                "Delete Render Job",
                "\n".join(result.errors),
                parent=self.root,
            )
            self.status_var.set(
                f"Deleted {deleted_count} render jobs with "
                f"{len(result.errors)} errors"
            )
        else:
            suffix = "job" if deleted_count == 1 else "jobs"
            self.status_var.set(f"Deleted {deleted_count} render {suffix}")

    def _on_close(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self._auto_refresh_after_id is not None:
            self.root.after_cancel(self._auto_refresh_after_id)
            self._auto_refresh_after_id = None
        if self._refresh_feedback_after_id is not None:
            self.root.after_cancel(self._refresh_feedback_after_id)
            self._refresh_feedback_after_id = None
        if self._render_time_after_id is not None:
            self.root.after_cancel(self._render_time_after_id)
            self._render_time_after_id = None
        self.auto_refresh_worker.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = FarmRenderManagerApp()
    app.run()


if __name__ == "__main__":
    main()
