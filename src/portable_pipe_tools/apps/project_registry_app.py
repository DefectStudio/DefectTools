"""Manager-owned project registry, accessed through the dispatcher API."""

from queue import Empty, Queue
import re
from threading import Thread
import tkinter as tk
from tkinter import ttk


class ProjectEditor(tk.Toplevel):
    def __init__(self, registry, project=None):
        super().__init__(registry)
        self.registry = registry
        self.project = project
        self.title("Edit project" if project else "Create project")
        self.transient(registry)
        self.resizable(False, False)
        current = project or {}
        self.project_id = tk.StringVar(self, value=current.get("project_id", ""))
        self.display_name = tk.StringVar(self, value=current.get("display_name", ""))
        self.active = tk.BooleanVar(self, value=current.get("active", True))
        self.error = tk.StringVar(self)
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        for row, (label, variable) in enumerate((("Project ID", self.project_id), ("Display name", self.display_name))):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
            entry = ttk.Entry(body, textvariable=variable, width=44)
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            if row == 0:
                self.id_entry = entry
                if project:
                    entry.configure(state="readonly")
            else:
                self.name_entry = entry
        ttk.Checkbutton(body, text="Active — available in worker project lists", variable=self.active).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Label(body, text="IDs stay fixed. Use lowercase letters, numbers, underscores or hyphens.\nDisplay names and active status can be changed later.",
                  wraplength=460).grid(row=3, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Label(body, textvariable=self.error, foreground="#e87c70", wraplength=460).grid(
            row=4, column=0, columnspan=2, sticky="w")
        buttons = ttk.Frame(body)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12, 0))
        self.cancel_button = ttk.Button(buttons, text="Cancel", command=self.destroy)
        self.cancel_button.pack(side="left", padx=(0, 8))
        self.save_button = ttk.Button(buttons, text="Save", command=self.save)
        self.save_button.pack(side="left")
        self.bind("<Escape>", lambda event: self.destroy() if not registry.busy else None)
        self.protocol("WM_DELETE_WINDOW", lambda: self.destroy() if not registry.busy else None)
        self.grab_set()
        (self.name_entry if project else self.id_entry).focus_set()

    def save(self):
        if self.registry.busy:
            return
        identifier = self.project_id.get().strip()
        name = self.display_name.get().strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", identifier):
            self.error.set("Enter a valid Project ID (lowercase, maximum 64 characters).")
            return
        if not name or len(name) > 200:
            self.error.set("Enter a display name of 1–200 characters.")
            return
        self.error.set("")
        self.registry.save_editor(self, identifier, name, self.active.get())


class ProjectRegistryWindow(tk.Toplevel):
    def __init__(self, parent, *, client, can_manage, on_change=lambda projects: None):
        super().__init__(parent)
        self.title("Render Farm Projects")
        self.geometry("780x430")
        self.minsize(650, 330)
        self.transient(parent)
        self.client = client
        self.can_manage = can_manage
        self.on_change = on_change
        self.projects = []
        self.busy = False
        self.available = False
        self.editor = None
        self.results = Queue()
        self.status = tk.StringVar(self, value="Loading projects…")
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)
        ttk.Label(outer, text="Shared Project IDs", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.tree = ttk.Treeview(outer, columns=("id", "name", "active"), show="headings", selectmode="browse")
        for key, label, width in [("id", "Project ID", 200), ("name", "Display name", 350), ("active", "Active", 85)]:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, stretch=key == "name")
        self.tree.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(outer, orient="vertical", command=self.tree.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)
        controls = ttk.Frame(outer)
        controls.grid(row=2, column=0, columnspan=2, sticky="ew", pady=10)
        self.add_button = ttk.Button(controls, text="Create project…", command=self.add)
        self.add_button.pack(side="left", padx=(0, 8))
        self.edit_button = ttk.Button(controls, text="Edit selected…", command=self.edit)
        self.edit_button.pack(side="left", padx=(0, 8))
        self.refresh_button = ttk.Button(controls, text="Refresh", command=self.refresh)
        self.refresh_button.pack(side="left")
        ttk.Button(controls, text="Close", command=self.close).pack(side="right")
        ttk.Label(outer, textvariable=self.status, wraplength=730).grid(row=3, column=0, columnspan=2, sticky="w")
        self.tree.bind("<<TreeviewSelect>>", lambda event: self._controls())
        self.tree.bind("<Double-1>", self._double_click)
        self.tree.bind("<Return>", lambda event: self.edit())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after_id = self.after(75, self._poll)
        self.refresh()

    def _controls(self):
        writable = self.can_manage and self.available and not self.busy
        self.add_button.configure(state="normal" if writable else "disabled")
        self.edit_button.configure(state="normal" if writable and self.tree.selection() else "disabled")
        self.refresh_button.configure(state="disabled" if self.busy else "normal")

    def _run(self, operation, success, failure=None):
        if self.busy:
            return
        self.busy = True
        self._controls()
        def work():
            try:
                self.results.put((success, failure, operation(), None))
            except Exception as error:
                self.results.put((success, failure, None, error))
        Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            success, failure, value, error = self.results.get_nowait()
        except Empty:
            pass
        else:
            self.busy = False
            if error is None:
                success(value)
            elif failure is not None:
                failure(error)
            else:
                self.available = False
                self.status.set(f"Could not load the shared project registry: {error}")
            self._controls()
        self.after_id = self.after(75, self._poll)

    def _loaded(self, projects):
        self.projects = projects
        self.available = True
        selection = self.tree.selection()
        for item in self.tree.get_children():
            self.tree.delete(item)
        for project in projects:
            self.tree.insert("", "end", iid=project["project_id"], values=(project["project_id"], project["display_name"], "Yes" if project["active"] else "No"))
        if selection and self.tree.exists(selection[0]):
            self.tree.selection_set(selection[0])
        self.status.set(f"{len(projects)} project(s). " + (
            "Deactivate an entry to remove it from worker choices; existing jobs are kept."
            if self.can_manage else "Read-only: configure a manager connection to create or edit projects."))
        self.on_change(projects)

    def refresh(self):
        if not self.busy:
            self.status.set("Loading projects…")
            self._run(lambda: self.client.list_projects(include_inactive=self.can_manage), self._loaded)

    def _open_editor(self, project=None):
        if not self.can_manage or self.busy or not self.available:
            return
        if self.editor is not None and self.editor.winfo_exists():
            self.editor.lift()
            return
        self.editor = ProjectEditor(self, project)

    def add(self):
        self._open_editor()

    def edit(self):
        selection = self.tree.selection()
        if selection:
            self._open_editor(next(project for project in self.projects if project["project_id"] == selection[0]))

    def _double_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.edit()

    def save_editor(self, editor, project_id, name, active):
        editor.save_button.configure(state="disabled")
        editor.cancel_button.configure(state="disabled")
        self.status.set("Saving project…")
        def operation():
            if editor.project is None:
                return self.client.create_project(project_id, name, active=active)
            return self.client.update_project(project_id, name, active=active, revision=editor.project["revision"])
        def saved(project):
            editor.destroy()
            self.refresh()
        def failed(error):
            self.status.set(f"Could not save project: {error}")
            if editor.winfo_exists():
                editor.error.set(str(error))
                editor.save_button.configure(state="normal")
                editor.cancel_button.configure(state="normal")
        self._run(operation, saved, failed)

    def close(self):
        if self.busy:
            self.status.set("Finishing the current request…")
            return
        self.destroy()

    def destroy(self):
        if getattr(self, "after_id", None) is not None:
            self.after_cancel(self.after_id)
            self.after_id = None
        super().destroy()
