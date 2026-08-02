from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

from portable_pipe_tools.render_farm.queue import (
    QueuePaths,
    create_queue_folders,
    default_worker_name,
    safe_name,
)
from portable_pipe_tools.render_farm.test_job import create_test_job
from portable_pipe_tools.render_farm.settings import (
    load_saved_render_farm_root,
    save_render_farm_root,
)
from portable_pipe_tools.render_farm.worker import WorkerResult, run_once


WORKER_LOGGER = logging.getLogger("render_worker")


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
    result: Any = None
    error: Exception | None = None


class RenderWorkerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Render Worker")
        self.root.geometry("960x680")
        self.root.minsize(800, 540)

        self.farm_root_var = tk.StringVar(value=load_saved_render_farm_root())
        self.worker_name_var = tk.StringVar(value=default_worker_name())
        self.simulate_result_var = tk.StringVar(value="success")
        self.status_var = tk.StringVar(value="Ready")

        self._busy = False
        self._closing = False
        self._log_queue: Queue[str] = Queue()
        self._completion_queue: Queue[BackgroundCompletion] = Queue()
        self._poll_after_id: str | None = None

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
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._schedule_queue_poll()

        self._log("Ready.")
        self._log(
            "Choose the show RenderFarm base folder. This is the folder that owns "
            "00_Submitting through 04_RenderFailed."
        )
        if self.farm_root_var.get():
            self._log(f"Loaded saved RenderFarm folder: {self.farm_root_var.get()}")

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
                "Filesystem queue prototype — configure this worker, inspect its "
                "activity, and process one simulated render job at a time."
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
            text="Prototype only; Unreal rendering is not connected yet.",
        ).grid(row=2, column=2, sticky="w", padx=(8, 0), pady=4)

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
            text="Process One Job",
            command=self._process_one_job,
        )
        self.process_one_button.pack(side="left", padx=(0, 8))

        ttk.Button(
            button_row,
            text="Clear Log",
            command=self._clear_log,
        ).pack(side="right")

        self._action_buttons = (
            self.initialize_button,
            self.create_test_job_button,
            self.process_one_button,
        )

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
            ),
            on_success=self._job_processed,
        )

    def _job_processed(self, result: WorkerResult | None) -> None:
        if result is None:
            self._log("No queued job was available.")
            return
        self._log(f"Job finished with status: {result.status.upper()}")
        self._log(f"Final job folder: {result.final_folder}")
        self._log(f"Reason: {result.reason}")

    def _run_background(
        self,
        label: str,
        work: Callable[[], Any],
        on_success: Callable[[Any], None],
    ) -> None:
        if self._busy:
            self._log("Another worker operation is already running.")
            return

        self._set_busy(True, label)
        self._log(f"{label} started...")

        def perform_work() -> None:
            try:
                result = work()
            except Exception as error:
                completion = BackgroundCompletion(
                    label=label,
                    on_success=on_success,
                    error=error,
                )
            else:
                completion = BackgroundCompletion(
                    label=label,
                    on_success=on_success,
                    result=result,
                )
            self._completion_queue.put(completion)

        Thread(
            target=perform_work,
            name="RenderWorkerUiTask",
            daemon=True,
        ).start()

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
            self._log(
                f"ERROR during {completion.label}: "
                f"{type(completion.error).__name__}: {completion.error}"
            )
            messagebox.showerror(
                "Render Worker Error",
                str(completion.error),
                parent=self.root,
            )
            return

        completion.on_success(completion.result)
        self._log(f"{completion.label} finished.")

    def _set_busy(self, busy: bool, status: str) -> None:
        self._busy = busy
        self.status_var.set(status)
        button_state = "disabled" if busy else "normal"
        entry_state = "disabled" if busy else "normal"
        combo_state = "disabled" if busy else "readonly"

        for button in self._action_buttons:
            button.configure(state=button_state)
        self.browse_button.configure(state=button_state)
        self.farm_root_entry.configure(state=entry_state)
        self.worker_name_entry.configure(state=entry_state)
        self.simulate_result_combo.configure(state=combo_state)

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

    def _on_close(self) -> None:
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
        WORKER_LOGGER.removeHandler(self._worker_log_handler)
        self.root.destroy()


def main() -> None:
    app = RenderWorkerApp()
    app.run()


if __name__ == "__main__":
    main()
