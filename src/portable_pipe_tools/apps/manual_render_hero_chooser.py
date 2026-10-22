"""Standalone, per-shot Unreal EXR hero chooser. No Unreal session is needed."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from portable_pipe_tools.render_hero import (
    RenderVersion,
    ShotRenders,
    discover_sequences,
    discover_shots,
    discover_shows,
    promote_render,
)


BACKGROUND = "#252629"
PANEL = "#2d2f32"
TEXT = "#e0e2e5"
MUTED = "#a8adb5"
ACCENT = "#327b96"
DEFAULT_ROOT = Path(r"K:\Defect Dropbox\defect")


def default_settings_path() -> Path:
    return Path(__file__).resolve().parents[3] / "LocalSaveFiles" / "manual_render_hero_chooser.json"


def load_settings(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {key: str(data[key]) for key in ("root", "show", "sequence") if key in data}
    except (OSError, ValueError, TypeError):
        return {}


@dataclass
class ShotControls:
    shot: ShotRenders
    selection: tk.StringVar
    versions: dict[str, RenderVersion]
    combo: ttk.Combobox
    button: ttk.Button
    status: tk.StringVar


class ManualRenderHeroChooser:
    def __init__(
        self,
        *,
        settings_path: Path | None = None,
        root_path: Path | None = None,
        show: str | None = None,
        sequence: str | None = None,
    ) -> None:
        self.settings_path = settings_path or default_settings_path()
        saved = load_settings(self.settings_path)
        self.root = tk.Tk()
        self.root.title("Manual Render Hero Chooser")
        self.root.geometry("1160x800")
        self.root.minsize(900, 540)
        self.root.configure(background=BACKGROUND)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.report_callback_exception = self._report_error
        initial = str(root_path) if root_path else saved.get("root", "")
        if not initial and DEFAULT_ROOT.is_dir():
            initial = str(DEFAULT_ROOT)
        self.folder_var = tk.StringVar(value=initial)
        self.show_var = tk.StringVar(value=show or saved.get("show", ""))
        self.sequence_var = tk.StringVar(value=sequence or saved.get("sequence", ""))
        self.status_var = tk.StringVar(value="Choose your defect Dropbox folder to begin.")
        self.count_var = tk.StringVar(value="")
        self.detail_var = tk.StringVar(value="Select a render version, then click Hero on its shot.")
        self._events: queue.Queue = queue.Queue()
        self._busy = False
        self._copying = False
        self._closed = False
        self._shows: dict[str, Path] = {}
        self._sequences: dict[str, Path] = {}
        self.rows: list[ShotControls] = []
        self._style()
        self._build()
        self.root.after(75, self._poll)
        if initial:
            self.root.after(100, self.refresh)

    def _style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background=BACKGROUND, foreground=TEXT)
        style.configure("TFrame", background=BACKGROUND)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BACKGROUND, foreground=TEXT)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Header.TLabel", foreground=MUTED, font=("Segoe UI", 9, "bold"))
        style.configure("TButton", background="#41454c", padding=(14, 7), borderwidth=0)
        style.map("TButton", background=[("active", "#525862"), ("disabled", "#303238")],
                  foreground=[("disabled", "#737983")])
        style.configure("Hero.TButton", background=ACCENT, font=("Segoe UI", 10, "bold"))
        style.map("Hero.TButton", background=[("active", "#4099b6"), ("disabled", "#303238")])
        style.configure("TEntry", fieldbackground="#1e2024", insertcolor=TEXT, padding=7)
        style.configure("TCombobox", fieldbackground="#1e2024", padding=7, arrowsize=15)
        style.map("TCombobox", fieldbackground=[("readonly", "#1e2024"), ("disabled", "#303238")],
                  foreground=[("readonly", TEXT), ("disabled", "#858b94")],
                  selectbackground=[("readonly", "#1e2024")], selectforeground=[("readonly", TEXT)])
        style.configure("TProgressbar", background=ACCENT, troughcolor="#1e2024")
        self.root.option_add("*TCombobox*Listbox.background", "#1e2024")
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))

    def _build(self) -> None:
        main = ttk.Frame(self.root, padding=22)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="Manual Render Hero Chooser", style="Title.TLabel").pack(anchor="w")
        ttk.Label(main, text="Choose which Unreal EXR render becomes each shot's hero.",
                  style="Muted.TLabel").pack(anchor="w", pady=(3, 20))

        pickers = ttk.Frame(main)
        pickers.pack(fill="x")
        pickers.columnconfigure(1, weight=1)
        ttk.Label(pickers, text="Defect Dropbox folder").grid(row=0, column=0, sticky="w", padx=(0, 16))
        self.folder_entry = ttk.Entry(pickers, textvariable=self.folder_var)
        self.folder_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.folder_entry.bind("<Return>", lambda _event: self.refresh())
        self.browse_button = ttk.Button(pickers, text="Browse...", command=self._browse)
        self.browse_button.grid(row=0, column=2)
        self.refresh_button = ttk.Button(pickers, text="Refresh", command=self.refresh)
        self.refresh_button.grid(row=0, column=3, padx=(8, 0))
        ttk.Label(pickers, text="Show").grid(row=1, column=0, sticky="w", pady=(12, 0))
        self.show_combo = ttk.Combobox(pickers, textvariable=self.show_var, state="disabled")
        self.show_combo.grid(row=1, column=1, columnspan=3, sticky="ew", pady=(12, 0))
        self.show_combo.bind("<<ComboboxSelected>>", lambda _event: self._select_show())
        ttk.Label(pickers, text="Sequence").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.sequence_combo = ttk.Combobox(pickers, textvariable=self.sequence_var, state="disabled")
        self.sequence_combo.grid(row=2, column=1, columnspan=3, sticky="ew", pady=(10, 0))
        self.sequence_combo.bind("<<ComboboxSelected>>", lambda _event: self._select_sequence())

        caption = ttk.Frame(main)
        caption.pack(fill="x", pady=(22, 10))
        ttk.Label(caption, text="SHOTS", style="Header.TLabel").pack(side="left")
        ttk.Label(caption, textvariable=self.count_var, style="Muted.TLabel").pack(side="right")
        table = ttk.Frame(main)
        table.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(table, background=PANEL, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.shot_frame = ttk.Frame(self.canvas, padding=12)
        self._canvas_window = self.canvas.create_window((0, 0), window=self.shot_frame, anchor="nw")
        self.shot_frame.bind("<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(self._canvas_window, width=event.width))
        self.root.bind_all("<MouseWheel>", self._scroll)
        self._render_rows([])

        ttk.Label(main, text="Hero replaces this shot's _hero folder with the selected EXRs, removing version labels.",
                  style="Muted.TLabel").pack(anchor="w", pady=(12, 0))
        ttk.Label(main, text="Original renders are kept. Shots without EXR renders are listed with Hero disabled.",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 10))
        ttk.Label(main, textvariable=self.detail_var, style="Muted.TLabel", wraplength=1080).pack(anchor="w")
        self.progress = ttk.Progressbar(main, mode="determinate")
        self.progress.pack(fill="x", pady=(12, 7))
        ttk.Label(main, textvariable=self.status_var, wraplength=1080).pack(anchor="w")

    def _scroll(self, event: tk.Event) -> str | None:
        # Leave an open version dropdown's own scrolling alone.
        if str(event.widget).startswith(str(self.canvas)) or event.widget == self.root:
            self.canvas.yview_scroll(-int(event.delta / 120), "units")
            return "break"
        return None

    def _browse(self) -> None:
        selected = filedialog.askdirectory(parent=self.root, title="Choose the defect Dropbox folder",
                                           initialdir=self.folder_var.get() or None, mustexist=True)
        if selected:
            self.folder_var.set(selected)
            self.refresh()

    def _save(self) -> None:
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(json.dumps({"root": self.folder_var.get(),
                "show": self.show_var.get(), "sequence": self.sequence_var.get()}, indent=2), encoding="utf-8")
        except OSError as exc:
            self.status_var.set(f"Could not remember your selection: {exc}")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for widget in (self.folder_entry, self.browse_button, self.refresh_button):
            widget.configure(state="disabled" if busy else "normal")
        self.show_combo.configure(state="readonly" if self._shows and not busy else "disabled")
        self.sequence_combo.configure(state="readonly" if self._sequences and not busy else "disabled")
        for row in self.rows:
            row.combo.configure(state="readonly" if row.versions and not busy else "disabled")
            row.button.configure(state="normal" if row.versions and not busy else "disabled")

    def _run(self, work: Callable, done: Callable, *, failure: Callable | None = None) -> None:
        self._set_busy(True)

        def worker() -> None:
            try:
                self._events.put(("done", done, work()))
            except Exception as exc:
                self._events.put(("error", failure, str(exc)))

        threading.Thread(target=worker, name="ManualRenderHeroChooser", daemon=False).start()

    def _poll(self) -> None:
        try:
            while True:
                kind, callback, value = self._events.get_nowait()
                if kind == "progress":
                    completed, total, message = value
                    self.progress.configure(maximum=max(1, total), value=completed)
                    self.status_var.set(message)
                else:
                    self._copying = False
                    self._set_busy(False)
                    if kind == "error":
                        self.status_var.set(f"Failed: {value}")
                        if callback:
                            callback(value)
                        messagebox.showerror("Manual Render Hero Chooser", value, parent=self.root)
                    else:
                        callback(value)
        except queue.Empty:
            pass
        if not self._closed:
            self.root.after(75, self._poll)

    def refresh(self) -> None:
        if self._busy:
            return
        raw = self.folder_var.get().strip().strip('"')
        if not raw:
            self.status_var.set("Browse to your defect Dropbox folder first.")
            return
        folder = Path(raw).expanduser()
        self.folder_var.set(str(folder))
        self._shows.clear()
        self._sequences.clear()
        self.show_combo.configure(values=())
        self.sequence_combo.configure(values=())
        self._render_rows([])
        self.status_var.set("Finding shows...")

        def done(paths: list[Path]) -> None:
            self._shows = {path.name: path for path in paths}
            self.show_combo.configure(values=list(self._shows))
            if not paths:
                self.show_var.set("")
                self.sequence_var.set("")
                self.status_var.set("No shows found. Choose the defect folder containing your show folders.")
                self._set_busy(False)
                return
            if self.show_var.get() not in self._shows:
                self.show_var.set(paths[0].name)
                self.sequence_var.set("")
            self._select_show()

        self._run(lambda: discover_shows(folder), done)

    def _select_show(self) -> None:
        path = self._shows.get(self.show_var.get())
        if path is None or self._busy:
            return
        self._sequences.clear()
        self.sequence_combo.configure(values=())
        self._render_rows([])
        self.status_var.set(f"Finding sequences in {path.name}...")
        self._save()

        def done(paths: list[Path]) -> None:
            self._sequences = {item.name: item for item in paths}
            self.sequence_combo.configure(values=list(self._sequences))
            if not paths:
                self.sequence_var.set("")
                self.status_var.set("This show has no sequence folders.")
                self._set_busy(False)
                return
            if self.sequence_var.get() not in self._sequences:
                self.sequence_var.set(paths[0].name)
            self._select_sequence()

        self._run(lambda: discover_sequences(path), done)

    def _select_sequence(self) -> None:
        path = self._sequences.get(self.sequence_var.get())
        if path is None or self._busy:
            return
        self._render_rows([])
        self._save()
        self.status_var.set(f"Scanning {path.name} render versions...")

        def done(shots: list[ShotRenders]) -> None:
            self._render_rows(shots)
            self.status_var.set(f"Ready. Choose a version and click Hero. ({path.name})" if shots else
                                f"No shot folders found in {path.name}.")
            self._set_busy(False)

        self._run(lambda: discover_shots(path), done)

    def _render_rows(self, shots: list[ShotRenders]) -> None:
        for child in self.shot_frame.winfo_children():
            child.destroy()
        self.rows.clear()
        self.canvas.yview_moveto(0)
        self.detail_var.set("Select a render version, then click Hero on its shot.")
        if hasattr(self, "progress"):
            self.progress.configure(value=0)
        self.count_var.set(f"{len(shots)} shots / {sum(bool(shot.versions) for shot in shots)} with EXR renders" if shots else "")
        self.shot_frame.columnconfigure(0, minsize=175)
        self.shot_frame.columnconfigure(1, weight=1)
        self.shot_frame.columnconfigure(2, minsize=90)
        self.shot_frame.columnconfigure(3, minsize=180)
        for column, text in enumerate(("SHOT NAME", "RENDERED EXR VERSION", "", "RESULT")):
            ttk.Label(self.shot_frame, text=text, style="Header.TLabel").grid(
                row=0, column=column, sticky="w", padx=(4, 10), pady=(1, 12))
        if not shots:
            ttk.Label(self.shot_frame, text="Choose a show and sequence to list its shots.",
                      style="Muted.TLabel").grid(row=1, column=0, columnspan=4, sticky="w", pady=20)
        for index, shot in enumerate(shots, start=1):
            versions = {f"{item.path.name}  ({item.frame_count} EXRs)": item for item in shot.versions}
            selection = tk.StringVar(value=next(iter(versions), "No EXR renders"))
            ttk.Label(self.shot_frame, text=shot.path.name).grid(
                row=index, column=0, sticky="w", padx=(4, 10), pady=9)
            combo = ttk.Combobox(self.shot_frame, textvariable=selection, values=list(versions),
                                 state="readonly" if versions else "disabled", width=44)
            combo.grid(row=index, column=1, sticky="ew", padx=(0, 12), pady=6)
            button = ttk.Button(self.shot_frame, text="Hero", style="Hero.TButton", width=6,
                                state="normal" if versions else "disabled")
            button.grid(row=index, column=2, sticky="ew", padx=(0, 12), pady=6)
            status = tk.StringVar(value=shot.error or ("" if versions else "No EXR renders"))
            ttk.Label(self.shot_frame, textvariable=status, style="Muted.TLabel", wraplength=180).grid(
                row=index, column=3, sticky="w", pady=6)
            row = ShotControls(shot, selection, versions, combo, button, status)
            button.configure(command=lambda row=row: self._hero(row))
            combo.bind("<<ComboboxSelected>>", lambda _event, row=row: self._detail(row))
            combo.bind("<FocusIn>", lambda _event, row=row: self._detail(row))
            combo.bind("<MouseWheel>", self._scroll)
            self.rows.append(row)

    def _detail(self, row: ShotControls) -> None:
        version = row.versions.get(row.selection.get())
        if version:
            self.detail_var.set(f"Source: {version.path}\nHero: {version.path.parent / '_hero'}")

    def _hero(self, row: ShotControls) -> None:
        if self._busy:
            return
        version = row.versions.get(row.selection.get())
        if version is None:
            return
        self._detail(row)
        row.status.set("Copying...")
        self._copying = True
        self.progress.configure(value=0)
        self.status_var.set(f"Copying {version.path.name}...")

        def progress(completed: int, total: int, message: str) -> None:
            self._events.put(("progress", None, (completed, total, message)))

        def done(result) -> None:
            row.status.set(f"Hero: v{version.version:03d}\n{result.copied_count} EXRs copied")
            self.progress.configure(maximum=1, value=1)
            self.status_var.set(f"Hero updated: {row.shot.path.name} / {version.path.name} / {result.copied_count} EXRs")
            if result.warnings:
                messagebox.showwarning("Hero updated", "\n".join(result.warnings), parent=self.root)

        self._run(lambda: promote_render(version.path, progress=progress),
                  done, failure=lambda _message: row.status.set("Failed - see error"))

    def _report_error(self, _kind, error, _traceback) -> None:
        self.status_var.set(f"Error: {error}")
        messagebox.showerror("Manual Render Hero Chooser", str(error), parent=self.root)

    def _close(self) -> None:
        if self._copying:
            messagebox.showinfo("Hero copy in progress", "Please let the hero copy finish before closing.", parent=self.root)
            return
        self._save()
        self._closed = True
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Initial defect Dropbox folder")
    parser.add_argument("--show", help="Initial show folder name")
    parser.add_argument("--sequence", help="Initial sequence folder name")
    parser.add_argument("--settings", type=Path, help="Override the local settings file")
    args = parser.parse_args()
    ManualRenderHeroChooser(settings_path=args.settings, root_path=args.root,
                            show=args.show, sequence=args.sequence).run()


if __name__ == "__main__":
    main()
