"""One-time machine setup and project jobs for the standalone V2 worker."""

from __future__ import annotations

import json
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
import tkinter as tk
from tkinter import filedialog, ttk

from portable_pipe_tools.app_runtime import default_catalog_path, default_settings_path, default_workspace

from portable_pipe_tools.render_farm.project_catalog import load_catalog
from portable_pipe_tools.render_farm.project_workspace import ProjectWorkspace
from portable_pipe_tools.render_farm.project_render import render_project_shot
from portable_pipe_tools.render_farm.queue import write_json_atomic


class ProjectWorkerApp(ttk.Frame):
    def __init__(self, root, *, settings_path=None):
        super().__init__(root, padding=16)
        self.root = root
        self.settings_path = Path(settings_path or default_settings_path())
        try:
            self.settings = json.loads(self.settings_path.read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            self.settings = {}
        self.projects = {}
        self.events = Queue()
        self.cancel = Event()
        self.busy = False
        self.closing = False
        self.catalog = tk.StringVar(value=self.settings.get("catalog", ""))
        self.workspace = tk.StringVar(value=self.settings.get("workspace_root", str(default_workspace())))
        self.output = tk.StringVar(value=self.settings.get("output_root", str(default_workspace() / "renders")))
        self.project = tk.StringVar()
        self.shot = tk.StringVar(value=self.settings.get("last_shot", ""))
        self.status = tk.StringVar(value="Loading projects…")
        self.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(8, weight=1)
        ttk.Label(self, text="Render Worker V2", font=("Segoe UI", 17, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
        self._path_row(1, "Catalog (blank = default)", self.catalog, directory=False)
        self._path_row(2, "Project workspace", self.workspace)
        self._path_row(3, "Render outputs", self.output)
        ttk.Label(self, text="Project").grid(row=4, column=0, sticky="w", pady=6)
        self.project_box = ttk.Combobox(self, textvariable=self.project, state="readonly")
        self.project_box.grid(row=4, column=1, sticky="ew", padx=10)
        self.reload = ttk.Button(self, text="Reload projects", command=self.load_projects)
        self.reload.grid(row=4, column=2)
        ttk.Label(self, text="Shot").grid(row=5, column=0, sticky="w", pady=6)
        ttk.Entry(self, textvariable=self.shot).grid(row=5, column=1, sticky="ew", padx=10)
        buttons = ttk.Frame(self)
        buttons.grid(row=6, column=0, columnspan=3, sticky="w", pady=12)
        self.prepare_button = ttk.Button(buttons, text="Prepare project", command=lambda: self.start_job(False))
        self.prepare_button.pack(side="left", padx=(0, 8))
        self.render_button = ttk.Button(buttons, text="Render shot", command=lambda: self.start_job(True))
        self.render_button.pack(side="left", padx=(0, 8))
        self.stop_button = ttk.Button(buttons, text="Stop", command=self.stop, state="disabled")
        self.stop_button.pack(side="left")
        ttk.Label(self, textvariable=self.status, wraplength=740).grid(row=7, column=0, columnspan=3, sticky="w", pady=(0, 8))
        self.log = tk.Text(self, height=18, wrap="word", state="disabled")
        self.log.grid(row=8, column=0, columnspan=3, sticky="nsew")
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.after_id = self.after(100, self.poll)
        self.load_projects()

    def _path_row(self, row, title, variable, directory=True):
        ttk.Label(self, text=title).grid(row=row, column=0, sticky="w", pady=6)
        ttk.Entry(self, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=10)
        def browse():
            chosen = filedialog.askdirectory() if directory else filedialog.askopenfilename(filetypes=[("Project catalogs", "*.json")])
            if chosen:
                variable.set(chosen)
        ttk.Button(self, text="Browse…", command=browse).grid(row=row, column=2)

    def append(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def launch(self, operation, callback):
        if self.busy:
            return
        self.busy = True
        self.cancel.clear()
        for button in (self.prepare_button, self.render_button, self.reload):
            button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        def run():
            try:
                result = operation()
                self.events.put(("complete", (callback, result)))
            except Exception as error:
                self.events.put(("error", str(error)))
        Thread(target=run, daemon=True).start()

    def load_projects(self):
        catalog = self.catalog.get().strip() or str(default_catalog_path())
        def loaded(projects):
            self.projects = projects
            self.project_box.configure(values=list(projects))
            selected = self.settings.get("last_project", "")
            self.project.set(selected if selected in projects else next(iter(projects), ""))
            self.status.set("Ready. Select a project and enter a shot.")
        self.launch(lambda: load_catalog(catalog), loaded)

    def start_job(self, render):
        try:
            project_id = self.project.get()
            if project_id not in self.projects:
                raise ValueError("Select a project first")
            shot = self.projects[project_id].canonical_shot(self.shot.get()) if render else ""
            workspace = Path(self.workspace.get()).expanduser()
            output = Path(self.output.get()).expanduser()
            if not self.workspace.get().strip() or not self.output.get().strip():
                raise ValueError("Choose workspace and output folders")
            catalog = self.catalog.get().strip()
            self.settings.update(catalog=catalog, workspace_root=str(workspace), output_root=str(output),
                                 last_project=project_id, last_shot=self.shot.get())
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            write_json_atomic(self.settings_path, self.settings)
        except (ValueError, OSError) as error:
            self.status.set(str(error))
            return
        self.status.set("Starting project preparation…")
        def progress(message):
            self.events.put(("progress", message))
        def work():
            # Refresh the catalog for each job so central changes take effect.
            project = load_catalog(catalog or str(default_catalog_path()))[project_id]
            manager = ProjectWorkspace(workspace, progress=progress, cancelled=self.cancel.is_set,
                                       discovery_roots=tuple(Path(p) for p in self.settings["discovery_roots"]) if "discovery_roots" in self.settings else None,
                                       timeout_seconds=self.settings.get("preparation_timeout_seconds", 7200),
                                       cache_roots=tuple(Path(p) for p in self.settings.get("lfs_cache_roots", [])))
            with manager.acquire(project) as prepared:
                if render:
                    result = render_project_shot(prepared, shot, output, progress=progress, cancelled=self.cancel.is_set)
                    if not result["success"]:
                        raise RuntimeError(f"{result['reason']}\nSee {result['run_root']}")
                    return f"Render complete: {result['run_root']}"
                return f"Project ready: {prepared.checkout} ({prepared.commit[:12]})"
        self.launch(work, lambda result: self.status.set(result))

    def stop(self):
        self.cancel.set()
        self.status.set("Stopping…")

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "progress":
                    self.status.set(value)
                    self.append(value)
                    continue
                self.busy = False
                for button in (self.prepare_button, self.render_button, self.reload):
                    button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                if kind == "error":
                    self.status.set(value)
                    self.append(value)
                else:
                    callback, result = value
                    callback(result)
                    self.append(self.status.get())
        except Empty:
            pass
        if self.closing and not self.busy:
            self.root.destroy()
            return
        self.after_id = self.after(100, self.poll)

    def close(self):
        if self.busy:
            self.closing = True
            self.stop()
        else:
            self.after_cancel(self.after_id)
            self.root.destroy()


def main():
    root = tk.Tk()
    root.title("Render Worker V2")
    root.geometry("850x600")
    root.minsize(650, 450)
    ProjectWorkerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
