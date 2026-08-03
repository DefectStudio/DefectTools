from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
import os
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

from portable_pipe_tools.render_farm.animations import (
    DEFAULT_ANIMATION_SPRITE_FOLDER,
    SPRITE_DISPLAY_SCALE,
    SPRITE_FRAME_INTERVAL_MS,
    SPRITE_FRAME_SIZE,
    get_stage_sprite_paths,
    inspect_sprite_sheet,
)
from portable_pipe_tools.render_farm.queue import (
    QueuePaths,
    create_queue_folders,
    default_worker_name,
    safe_name,
)
from portable_pipe_tools.render_farm.listener import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    ContinuousWorkerState,
    ListenerAction,
    parse_poll_interval_seconds,
    waiting_status,
)
from portable_pipe_tools.render_farm.test_job import create_test_job
from portable_pipe_tools.render_farm.settings import (
    load_saved_poll_interval_seconds,
    load_saved_render_farm_root,
    load_saved_unreal_editor_cmd,
    save_poll_interval_seconds,
    save_render_farm_root,
    save_unreal_editor_cmd,
)
from portable_pipe_tools.render_farm.worker import (
    DEFAULT_MINIMUM_STAGE_SECONDS,
    WORKER_STAGE_LABELS,
    WorkerResult,
    WorkerStage,
    run_once,
)


WORKER_LOGGER = logging.getLogger("render_worker")
NO_ACTIVE_JOB_TEXT = "No active job"


def format_job_activity(job: dict[str, Any]) -> str:
    shot_name = str(job.get("shot_name") or "Unknown").strip()

    raw_version_value = job.get("render_version")
    raw_version = (
        "" if raw_version_value is None else str(raw_version_value).strip()
    )
    version_digits = raw_version[1:] if raw_version.lower().startswith("v") else raw_version
    try:
        version = f"v{int(version_digits):03d}"
    except ValueError:
        version = raw_version or "Unknown"

    render_config = str(job.get("render_config") or "").strip()
    render_setting = render_config.rsplit("/", 1)[-1]
    render_setting = render_setting.split(".", 1)[0] or "Unknown"

    return (
        f"Shot: {shot_name}  —  Version: {version}  —  "
        f"Render Setting: {render_setting}"
    )


class QueueLogHandler(logging.Handler):
    """Forward worker log records to the Tk main thread through a queue."""

    def __init__(self, output_queue: Queue[str]) -> None:
        super().__init__()
        self.output_queue = output_queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.output_queue.put(self.format(record))
        except Exception:
            self.handleError(record)


@dataclass(frozen=True)
class BackgroundCompletion:
    label: str
    on_success: Callable[[Any], None]
    on_error: Callable[[Exception], None] | None = None
    result: Any = None
    error: Exception | None = None


@dataclass(frozen=True)
class ListenerConfiguration:
    farm_root: Path
    worker_name: str
    unreal_editor_cmd: Path
    poll_interval_seconds: int


class RenderWorkerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Render Worker")
        self.root.geometry("1080x880")
        self.root.minsize(900, 720)

        self.farm_root_var = tk.StringVar(value=load_saved_render_farm_root())
        self.worker_name_var = tk.StringVar(value=default_worker_name())
        self.simulate_result_var = tk.StringVar(value="success")
        saved_poll_interval = load_saved_poll_interval_seconds()
        self.poll_interval_var = tk.StringVar(
            value=saved_poll_interval or str(DEFAULT_POLL_INTERVAL_SECONDS)
        )
        saved_unreal_editor_cmd = load_saved_unreal_editor_cmd()
        default_unreal_editor_cmd = (
            Path(os.environ.get("ProgramFiles") or r"C:\Program Files")
            / "Epic Games"
            / "UE_5.8"
            / "Engine"
            / "Binaries"
            / "Win64"
            / "UnrealEditor-Cmd.exe"
        )
        self.unreal_editor_cmd_var = tk.StringVar(
            value=(
                saved_unreal_editor_cmd
                or (
                    str(default_unreal_editor_cmd)
                    if default_unreal_editor_cmd.is_file()
                    else ""
                )
            )
        )
        self.status_var = tk.StringVar(value="Ready")
        self.current_stage_var = tk.StringVar(
            value=WORKER_STAGE_LABELS[WorkerStage.WAITING]
        )
        self.current_job_var = tk.StringVar(value=NO_ACTIVE_JOB_TEXT)

        self._busy = False
        self._closing = False
        self._listener_state = ContinuousWorkerState()
        self._listener_configuration: ListenerConfiguration | None = None
        self._listener_after_id: str | None = None
        self._listener_seconds_remaining = 0
        self._active_stage = WorkerStage.WAITING
        self._log_queue: Queue[str] = Queue()
        self._stage_queue: Queue[WorkerStage] = Queue()
        self._job_queue: Queue[dict[str, Any]] = Queue()
        self._completion_queue: Queue[BackgroundCompletion] = Queue()
        self._poll_after_id: str | None = None
        self._animation_after_id: str | None = None
        self._animation_frame_index = 0
        self._animation_frames: dict[WorkerStage, list[tk.PhotoImage]] = {}

        self._worker_log_handler = QueueLogHandler(self._log_queue)
        self._worker_log_handler.setFormatter(
            logging.Formatter(
                fmt="[%(asctime)s] %(levelname)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        WORKER_LOGGER.addHandler(self._worker_log_handler)
        WORKER_LOGGER.setLevel(logging.INFO)

        self._build_ui()
        self._load_animation_assets()
        self._set_worker_stage(WorkerStage.WAITING)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._schedule_queue_poll()

        self._log("Ready.")
        self._log(
            "Choose the show RenderFarm base folder. This is the folder that owns "
            "00_Submitting through 04_RenderFailed."
        )
        if self.farm_root_var.get():
            self._log(f"Loaded saved RenderFarm folder: {self.farm_root_var.get()}")
        if self.unreal_editor_cmd_var.get():
            self._log(
                f"Unreal command-line executable: {self.unreal_editor_cmd_var.get()}"
            )
        self._log(
            f"Project animation sprites: {DEFAULT_ANIMATION_SPRITE_FOLDER}"
        )

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="Render Worker",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            outer,
            text=(
                "Filesystem render worker — process one supervised job or listen "
                "continuously for Unreal Movie Render Graph jobs."
            ),
        ).pack(anchor="w", pady=(2, 12))

        setup_frame = ttk.LabelFrame(outer, text="Worker Setup", padding=10)
        setup_frame.pack(fill="x")
        setup_frame.columnconfigure(1, weight=1)

        ttk.Label(setup_frame, text="Show Render Farm Base Folder").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=4,
        )
        self.farm_root_entry = ttk.Entry(
            setup_frame,
            textvariable=self.farm_root_var,
        )
        self.farm_root_entry.grid(row=0, column=1, sticky="ew", pady=4)
        self.browse_button = ttk.Button(
            setup_frame,
            text="Browse...",
            command=self._browse_farm_root,
        )
        self.browse_button.grid(row=0, column=2, padx=(8, 0), pady=4)

        ttk.Label(setup_frame, text="Worker Name").grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=4,
        )
        self.worker_name_entry = ttk.Entry(
            setup_frame,
            textvariable=self.worker_name_var,
        )
        self.worker_name_entry.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(setup_frame, text="Simulation Result").grid(
            row=2,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=4,
        )
        self.simulate_result_combo = ttk.Combobox(
            setup_frame,
            textvariable=self.simulate_result_var,
            values=("success", "failure"),
            state="readonly",
            width=16,
        )
        self.simulate_result_combo.grid(row=2, column=1, sticky="w", pady=4)
        ttk.Label(
            setup_frame,
            text="Used only by the Simulate One Job button.",
        ).grid(row=2, column=2, sticky="w", padx=(8, 0), pady=4)

        ttk.Label(setup_frame, text="UnrealEditor-Cmd.exe").grid(
            row=3,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=4,
        )
        self.unreal_editor_cmd_entry = ttk.Entry(
            setup_frame,
            textvariable=self.unreal_editor_cmd_var,
        )
        self.unreal_editor_cmd_entry.grid(row=3, column=1, sticky="ew", pady=4)
        self.unreal_editor_cmd_browse_button = ttk.Button(
            setup_frame,
            text="Browse...",
            command=self._browse_unreal_editor_cmd,
        )
        self.unreal_editor_cmd_browse_button.grid(
            row=3,
            column=2,
            sticky="w",
            padx=(8, 0),
            pady=4,
        )

        ttk.Label(setup_frame, text="Polling Interval (seconds)").grid(
            row=4,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=4,
        )
        self.poll_interval_spinbox = ttk.Spinbox(
            setup_frame,
            from_=1,
            to=3600,
            textvariable=self.poll_interval_var,
            width=10,
        )
        self.poll_interval_spinbox.grid(row=4, column=1, sticky="w", pady=4)
        ttk.Label(
            setup_frame,
            text="Used by Start Worker; default is 15 seconds.",
        ).grid(row=4, column=2, sticky="w", padx=(8, 0), pady=4)

        button_row = ttk.Frame(outer)
        button_row.pack(fill="x", pady=(12, 8))

        self.initialize_button = ttk.Button(
            button_row,
            text="Initialize Queue",
            command=self._initialize_queue,
        )
        self.initialize_button.pack(side="left", padx=(0, 8))

        self.create_test_job_button = ttk.Button(
            button_row,
            text="Create Test Job",
            command=self._create_test_job,
        )
        self.create_test_job_button.pack(side="left", padx=(0, 8))

        self.process_one_button = ttk.Button(
            button_row,
            text="Simulate One Job",
            command=self._process_one_job,
        )
        self.process_one_button.pack(side="left", padx=(0, 8))

        self.render_one_button = ttk.Button(
            button_row,
            text="Render One Job with Unreal",
            command=self._render_one_job_with_unreal,
        )
        self.render_one_button.pack(side="left", padx=(0, 8))

        self.start_worker_button = ttk.Button(
            button_row,
            text="Start Worker",
            command=self._start_worker,
        )
        self.start_worker_button.pack(side="left", padx=(0, 8))

        self.stop_worker_button = ttk.Button(
            button_row,
            text="Stop Worker",
            command=self._stop_worker,
            state="disabled",
        )
        self.stop_worker_button.pack(side="left", padx=(0, 8))

        ttk.Button(
            button_row,
            text="Clear Log",
            command=self._clear_log,
        ).pack(side="right")

        self._action_buttons = (
            self.initialize_button,
            self.create_test_job_button,
            self.process_one_button,
            self.render_one_button,
        )

        activity_frame = ttk.LabelFrame(outer, text="Worker Activity", padding=8)
        activity_frame.pack(fill="x", pady=(2, 10))

        self.animation_image_label = ttk.Label(
            activity_frame,
            anchor="center",
            text="Loading animation...",
        )
        self.animation_image_label.pack(fill="x")
        ttk.Label(
            activity_frame,
            textvariable=self.current_stage_var,
            anchor="center",
            font=("Segoe UI", 11, "bold"),
        ).pack(fill="x", pady=(4, 0))
        ttk.Label(
            activity_frame,
            textvariable=self.current_job_var,
            anchor="center",
            font=("Segoe UI", 10),
        ).pack(fill="x", pady=(2, 0))

        log_header = ttk.Frame(outer)
        log_header.pack(fill="x", pady=(2, 4))
        ttk.Label(
            log_header,
            text="Worker Output Log",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        log_frame = ttk.Frame(outer)
        log_frame.pack(fill="both", expand=True)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_frame,
            wrap="none",
            height=24,
            state="disabled",
            font=("Consolas", 10),
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(
            log_frame,
            orient="vertical",
            command=self.log_text.yview,
        )
        y_scroll.grid(row=0, column=1, sticky="ns")

        x_scroll = ttk.Scrollbar(
            log_frame,
            orient="horizontal",
            command=self.log_text.xview,
        )
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.log_text.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=(8, 4))
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w")

    def run(self) -> None:
        self.root.mainloop()

    def _browse_farm_root(self) -> None:
        current_value = self.farm_root_var.get().strip()
        selected = filedialog.askdirectory(
            title="Choose Show Render Farm Base Folder",
            initialdir=current_value or None,
        )
        if selected:
            self.farm_root_var.set(selected)
            self._remember_farm_root(Path(selected))
            self._log(f"Selected show RenderFarm base folder: {selected}")

    def _browse_unreal_editor_cmd(self) -> None:
        current_value = self.unreal_editor_cmd_var.get().strip()
        selected = filedialog.askopenfilename(
            title="Choose UnrealEditor-Cmd.exe",
            initialdir=str(Path(current_value).parent) if current_value else None,
            initialfile=(
                Path(current_value).name
                if current_value
                else "UnrealEditor-Cmd.exe"
            ),
            filetypes=(
                ("Unreal command-line editor", "UnrealEditor-Cmd.exe"),
                ("Executables", "*.exe"),
            ),
        )
        if selected:
            self.unreal_editor_cmd_var.set(selected)
            self._remember_unreal_editor_cmd(Path(selected))
            self._log(f"Selected Unreal command-line executable: {selected}")

    def _get_farm_root(self) -> Path:
        raw_path = self.farm_root_var.get().strip()
        if not raw_path:
            raise ValueError("Please choose the show RenderFarm base folder.")
        return Path(raw_path).expanduser()

    def _get_worker_name(self) -> str:
        raw_name = self.worker_name_var.get().strip()
        if not raw_name:
            raise ValueError("Please enter a worker name.")
        worker_name = safe_name(raw_name, "WORKER")
        self.worker_name_var.set(worker_name)
        return worker_name

    def _get_unreal_editor_cmd(self) -> Path:
        raw_path = self.unreal_editor_cmd_var.get().strip()
        if not raw_path:
            raise ValueError("Please choose UnrealEditor-Cmd.exe.")
        executable = Path(raw_path).expanduser()
        if not executable.is_file():
            raise FileNotFoundError(
                f"UnrealEditor-Cmd.exe was not found: {executable}"
            )
        return executable

    def _get_poll_interval_seconds(self) -> int:
        interval = parse_poll_interval_seconds(self.poll_interval_var.get())
        self.poll_interval_var.set(str(interval))
        return interval

    def _start_worker(self) -> None:
        if self._listener_state.active:
            self._log("Start Worker ignored: the automatic worker is already active.")
            return
        if self._busy:
            self._log("Start Worker ignored: another worker operation is active.")
            return

        try:
            configuration = ListenerConfiguration(
                farm_root=self._get_farm_root(),
                worker_name=self._get_worker_name(),
                unreal_editor_cmd=self._get_unreal_editor_cmd(),
                poll_interval_seconds=self._get_poll_interval_seconds(),
            )
        except Exception as error:
            self._show_input_error(error)
            return

        confirmed = messagebox.askyesno(
            "Start Automatic Render Worker",
            "The worker will continuously claim and render real Unreal jobs "
            f"until stopped.\n\nWhen the queue is empty it will check every "
            f"{configuration.poll_interval_seconds} seconds. Stop Worker will "
            "finish an already-claimed render before stopping.\n\nAutomatic Git "
            "sync is not enabled; jobs render from the current checkout.\n\n"
            "Start the worker?",
            parent=self.root,
        )
        if not confirmed:
            self._log("Automatic worker start cancelled.")
            return

        if not self._listener_state.start():
            self._log("Start Worker ignored: the automatic worker is already active.")
            return

        self._listener_configuration = configuration
        self._remember_farm_root(configuration.farm_root)
        self._remember_unreal_editor_cmd(configuration.unreal_editor_cmd)
        self._remember_poll_interval(configuration.poll_interval_seconds)
        self._cancel_listener_countdown()
        self._refresh_control_states()
        self._set_worker_stage(WorkerStage.WAITING)
        self.status_var.set("Automatic worker started — checking for jobs")
        self._log(
            "Automatic worker started. Polling interval: "
            f"{configuration.poll_interval_seconds} seconds."
        )
        self._schedule_listener_check_now()

    def _stop_worker(self) -> None:
        if not self._listener_state.active:
            self._log("Stop Worker ignored: the automatic worker is not active.")
            return

        action = self._listener_state.request_stop()
        self._cancel_listener_countdown()
        self._refresh_control_states()
        if action is ListenerAction.FINISH_CURRENT:
            self.status_var.set(
                "Stop requested — finishing the current job or queue check"
            )
            self._log(
                "Stop requested. No new job will be claimed; an already-claimed "
                "render will finish first."
            )
            return

        self._finish_listener_stopped()

    def _schedule_listener_check_now(self) -> None:
        self._cancel_listener_countdown()
        if not self._listener_state.active:
            return
        self._listener_after_id = self.root.after(
            0,
            self._run_listener_job_check,
        )

    def _run_listener_job_check(self) -> None:
        self._listener_after_id = None
        configuration = self._listener_configuration
        if configuration is None or not self._listener_state.begin_job_check():
            if not self._listener_state.active:
                self._finish_listener_stopped()
            return

        started = self._run_background(
            label="Automatic worker job check",
            work=lambda: run_once(
                farm_root=configuration.farm_root,
                worker_name=configuration.worker_name,
                simulate_success=False,
                minimum_stage_seconds=DEFAULT_MINIMUM_STAGE_SECONDS,
                stage_callback=self._stage_queue.put,
                render_with_unreal=True,
                unreal_editor_cmd=configuration.unreal_editor_cmd,
                should_stop_before_claim=(
                    lambda: self._listener_state.stop_requested
                ),
                job_callback=self._job_queue.put,
            ),
            on_success=self._listener_job_check_finished,
            on_error=self._listener_job_check_errored,
        )
        if not started:
            action = self._listener_state.finish_job_check_with_error()
            if action is ListenerAction.STOPPED:
                self._finish_listener_stopped()
            else:
                self._schedule_listener_wait()

    def _listener_job_check_finished(self, result: WorkerResult | None) -> None:
        action = self._listener_state.finish_job_check(
            job_was_available=result is not None
        )
        self._job_processed(result)

        if action is ListenerAction.STOPPED:
            self._finish_listener_stopped()
        elif action is ListenerAction.CHECK_NOW:
            self._log("Automatic worker checking immediately for another job.")
            self._schedule_listener_check_now()
        else:
            self._schedule_listener_wait()

    def _listener_job_check_errored(self, error: Exception) -> None:
        del error
        action = self._listener_state.finish_job_check_with_error()
        if action is ListenerAction.STOPPED:
            self._finish_listener_stopped()
            return
        self._log("Automatic worker will continue listening after the error.")
        self._schedule_listener_wait()

    def _schedule_listener_wait(self) -> None:
        configuration = self._listener_configuration
        if configuration is None or not self._listener_state.active:
            return
        self._cancel_listener_countdown()
        self._listener_seconds_remaining = configuration.poll_interval_seconds
        self._set_worker_stage(WorkerStage.WAITING)
        self._listener_countdown_tick()

    def _listener_countdown_tick(self) -> None:
        self._listener_after_id = None
        if not self._listener_state.active:
            return
        if self._listener_state.stop_requested:
            self._finish_listener_stopped()
            return
        if self._listener_seconds_remaining <= 0:
            self._schedule_listener_check_now()
            return

        self.status_var.set(waiting_status(self._listener_seconds_remaining))
        self._listener_seconds_remaining -= 1
        self._listener_after_id = self.root.after(
            1_000,
            self._listener_countdown_tick,
        )

    def _cancel_listener_countdown(self) -> None:
        if self._listener_after_id is not None:
            self.root.after_cancel(self._listener_after_id)
            self._listener_after_id = None

    def _finish_listener_stopped(self) -> None:
        self._cancel_listener_countdown()
        self._listener_configuration = None
        self._listener_state.active = False
        self._listener_state.stop_requested = False
        self._listener_state.job_running = False
        self._set_worker_stage(WorkerStage.WAITING)
        self._clear_current_job()
        self.status_var.set("Worker stopped")
        self._refresh_control_states()
        self._log("Automatic worker stopped.")

    def _initialize_queue(self) -> None:
        try:
            farm_root = self._get_farm_root()
        except Exception as error:
            self._show_input_error(error)
            return

        self._remember_farm_root(farm_root)
        self._run_background(
            label="Initialize queue",
            work=lambda: create_queue_folders(farm_root),
            on_success=self._queue_initialized,
        )

    def _queue_initialized(self, paths: QueuePaths) -> None:
        self._log(f"Queue folders ready: {paths.root}")
        for folder in paths.all_queue_folders():
            self._log(f"  {folder.name}")

    def _create_test_job(self) -> None:
        try:
            farm_root = self._get_farm_root()
        except Exception as error:
            self._show_input_error(error)
            return

        self._remember_farm_root(farm_root)
        self._run_background(
            label="Create test job",
            work=lambda: create_test_job(farm_root),
            on_success=lambda queued_folder: self._log(
                f"Published test job: {queued_folder}"
            ),
        )

    def _process_one_job(self) -> None:
        try:
            farm_root = self._get_farm_root()
            worker_name = self._get_worker_name()
        except Exception as error:
            self._show_input_error(error)
            return

        simulate_success = self.simulate_result_var.get() == "success"
        self._remember_farm_root(farm_root)
        self._run_background(
            label="Process one job",
            work=lambda: run_once(
                farm_root=farm_root,
                worker_name=worker_name,
                simulate_success=simulate_success,
                minimum_stage_seconds=DEFAULT_MINIMUM_STAGE_SECONDS,
                stage_callback=self._stage_queue.put,
                job_callback=self._job_queue.put,
            ),
            on_success=self._job_processed,
        )

    def _render_one_job_with_unreal(self) -> None:
        try:
            farm_root = self._get_farm_root()
            worker_name = self._get_worker_name()
            unreal_editor_cmd = self._get_unreal_editor_cmd()
        except Exception as error:
            self._show_input_error(error)
            return

        confirmed = messagebox.askyesno(
            "Render One Farm Job with Unreal",
            "This will claim the next queued job and launch a real Unreal render.\n\n"
            "This checkpoint renders the worker's current project checkout; "
            "automatic Git sync is not enabled yet.\n\n"
            "Continue?",
            parent=self.root,
        )
        if not confirmed:
            self._log("Real Unreal render cancelled before claiming a job.")
            return

        self._remember_farm_root(farm_root)
        self._remember_unreal_editor_cmd(unreal_editor_cmd)
        self._run_background(
            label="Render one job with Unreal",
            work=lambda: run_once(
                farm_root=farm_root,
                worker_name=worker_name,
                simulate_success=False,
                minimum_stage_seconds=DEFAULT_MINIMUM_STAGE_SECONDS,
                stage_callback=self._stage_queue.put,
                render_with_unreal=True,
                unreal_editor_cmd=unreal_editor_cmd,
                job_callback=self._job_queue.put,
            ),
            on_success=self._job_processed,
        )

    def _job_processed(self, result: WorkerResult | None) -> None:
        if result is None:
            self._log("No queued job was available.")
            self._clear_current_job()
            return
        self._log(f"Job finished with status: {result.status.upper()}")
        self._log(f"Final job folder: {result.final_folder}")
        self._log(f"Reason: {result.reason}")
        self._clear_current_job()

    def _run_background(
        self,
        label: str,
        work: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[Exception], None] | None = None,
    ) -> bool:
        if self._busy:
            self._log("Another worker operation is already running.")
            return False

        self._set_busy(True, label)
        self._log(f"{label} started...")

        def perform_work() -> None:
            try:
                result = work()
            except Exception as error:
                completion = BackgroundCompletion(
                    label=label,
                    on_success=on_success,
                    on_error=on_error,
                    error=error,
                )
            else:
                completion = BackgroundCompletion(
                    label=label,
                    on_success=on_success,
                    on_error=on_error,
                    result=result,
                )
            self._completion_queue.put(completion)

        Thread(
            target=perform_work,
            name="RenderWorkerUiTask",
            daemon=True,
        ).start()
        return True

    def _schedule_queue_poll(self) -> None:
        self._poll_after_id = self.root.after(100, self._poll_queues)

    def _poll_queues(self) -> None:
        if self._closing:
            return

        while True:
            try:
                message = self._log_queue.get_nowait()
            except Empty:
                break
            self._append_log_line(message)

        while True:
            try:
                stage = self._stage_queue.get_nowait()
            except Empty:
                break
            self._set_worker_stage(stage)

        while True:
            try:
                job = self._job_queue.get_nowait()
            except Empty:
                break
            self.current_job_var.set(format_job_activity(job))

        while True:
            try:
                completion = self._completion_queue.get_nowait()
            except Empty:
                break
            self._handle_background_completion(completion)

        self._schedule_queue_poll()

    def _handle_background_completion(
        self,
        completion: BackgroundCompletion,
    ) -> None:
        self._set_busy(False, "Ready")
        if completion.error is not None:
            self._set_worker_stage(WorkerStage.WAITING)
            self._clear_current_job()
            self._log(
                f"ERROR during {completion.label}: "
                f"{type(completion.error).__name__}: {completion.error}"
            )
            if completion.on_error is not None:
                completion.on_error(completion.error)
                return
            messagebox.showerror(
                "Render Worker Error",
                str(completion.error),
                parent=self.root,
            )
            return

        completion.on_success(completion.result)
        self._log(f"{completion.label} finished.")
        self._set_worker_stage(WorkerStage.WAITING)

    def _set_busy(self, busy: bool, status: str) -> None:
        self._busy = busy
        self.status_var.set(status)
        self._refresh_control_states()

    def _refresh_control_states(self) -> None:
        configuration_locked = self._busy or self._listener_state.active
        button_state = "disabled" if configuration_locked else "normal"
        entry_state = "disabled" if configuration_locked else "normal"
        combo_state = "disabled" if configuration_locked else "readonly"

        for button in self._action_buttons:
            button.configure(state=button_state)
        self.start_worker_button.configure(state=button_state)
        self.stop_worker_button.configure(
            state=(
                "normal"
                if (
                    self._listener_state.active
                    and not self._listener_state.stop_requested
                )
                else "disabled"
            )
        )
        self.browse_button.configure(state=button_state)
        self.farm_root_entry.configure(state=entry_state)
        self.worker_name_entry.configure(state=entry_state)
        self.simulate_result_combo.configure(state=combo_state)
        self.poll_interval_spinbox.configure(state=entry_state)
        self.unreal_editor_cmd_entry.configure(state=entry_state)
        self.unreal_editor_cmd_browse_button.configure(state=button_state)

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _log(self, message: str) -> None:
        timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
        self._append_log_line(f"[{timestamp}] {message}")

    def _append_log_line(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _show_input_error(self, error: Exception) -> None:
        self._log(f"INPUT ERROR: {error}")
        messagebox.showerror(
            "Render Worker Setup",
            str(error),
            parent=self.root,
        )

    def _remember_farm_root(self, farm_root: Path) -> None:
        try:
            save_render_farm_root(farm_root)
        except Exception as error:
            self._log(f"WARNING: Could not remember the RenderFarm folder: {error}")

    def _remember_unreal_editor_cmd(self, unreal_editor_cmd: Path) -> None:
        try:
            save_unreal_editor_cmd(unreal_editor_cmd)
        except Exception as error:
            self._log(
                f"WARNING: Could not remember UnrealEditor-Cmd.exe: {error}"
            )

    def _remember_poll_interval(self, poll_interval_seconds: int) -> None:
        try:
            save_poll_interval_seconds(poll_interval_seconds)
        except Exception as error:
            self._log(f"WARNING: Could not remember polling interval: {error}")

    def _load_animation_assets(self) -> None:
        if self._animation_after_id is not None:
            self.root.after_cancel(self._animation_after_id)
            self._animation_after_id = None

        self._animation_frames = {}
        errors: list[str] = []

        for stage, sprite_path in get_stage_sprite_paths(
            DEFAULT_ANIMATION_SPRITE_FOLDER
        ).items():
            try:
                sheet_info = inspect_sprite_sheet(sprite_path)
                sheet_image = tk.PhotoImage(file=str(sprite_path))
                frames: list[tk.PhotoImage] = []
                for frame_index in range(sheet_info.frame_count):
                    source_x = frame_index * SPRITE_FRAME_SIZE
                    frame = tk.PhotoImage(
                        width=SPRITE_FRAME_SIZE,
                        height=SPRITE_FRAME_SIZE,
                    )
                    frame.tk.call(
                        str(frame),
                        "copy",
                        str(sheet_image),
                        "-from",
                        source_x,
                        0,
                        source_x + SPRITE_FRAME_SIZE,
                        SPRITE_FRAME_SIZE,
                        "-to",
                        0,
                        0,
                    )
                    frames.append(
                        frame.zoom(SPRITE_DISPLAY_SCALE, SPRITE_DISPLAY_SCALE)
                    )
                self._animation_frames[stage] = frames
            except Exception as error:
                errors.append(f"{sprite_path.name}: {error}")

        if errors:
            for error_message in errors:
                self._log(f"ANIMATION WARNING: {error_message}")
        else:
            frame_summary = ", ".join(
                f"{stage.value}={len(frames)}"
                for stage, frames in self._animation_frames.items()
            )
            self._log(f"Loaded animation frames: {frame_summary}")

        self._set_worker_stage(self._active_stage)

    def _clear_current_job(self) -> None:
        self.current_job_var.set(NO_ACTIVE_JOB_TEXT)

    def _set_worker_stage(self, stage: WorkerStage) -> None:
        self._active_stage = stage
        self.current_stage_var.set(WORKER_STAGE_LABELS[stage])
        self._animation_frame_index = 0
        if self._animation_after_id is not None:
            self.root.after_cancel(self._animation_after_id)
            self._animation_after_id = None
        self._show_next_animation_frame()

    def _show_next_animation_frame(self) -> None:
        frames = self._animation_frames.get(self._active_stage, [])
        if not frames:
            self.animation_image_label.configure(
                image="",
                text="Animation unavailable",
            )
            return

        frame = frames[self._animation_frame_index % len(frames)]
        self.animation_image_label.configure(image=frame, text="")
        self._animation_frame_index = (
            self._animation_frame_index + 1
        ) % len(frames)
        self._animation_after_id = self.root.after(
            SPRITE_FRAME_INTERVAL_MS,
            self._show_next_animation_frame,
        )

    def _on_close(self) -> None:
        if self._listener_state.active:
            action = self._listener_state.request_stop()
            self._cancel_listener_countdown()
            self._refresh_control_states()
            if action is ListenerAction.FINISH_CURRENT:
                self.status_var.set(
                    "Stop requested — finishing the current job or queue check"
                )
                messagebox.showwarning(
                    "Render Worker Stopping",
                    "Stop has been requested. The window will remain open until "
                    "the current job or queue check finishes.",
                    parent=self.root,
                )
                return
            self._listener_configuration = None

        if self._busy:
            messagebox.showwarning(
                "Render Worker Busy",
                "Wait for the current filesystem operation to finish before closing.",
                parent=self.root,
            )
            return

        self._closing = True
        if self._poll_after_id is not None:
            self.root.after_cancel(self._poll_after_id)
            self._poll_after_id = None
        if self._animation_after_id is not None:
            self.root.after_cancel(self._animation_after_id)
            self._animation_after_id = None
        self._cancel_listener_countdown()
        WORKER_LOGGER.removeHandler(self._worker_log_handler)
        self.root.destroy()


def main() -> None:
    app = RenderWorkerApp()
    app.run()


if __name__ == "__main__":
    main()
