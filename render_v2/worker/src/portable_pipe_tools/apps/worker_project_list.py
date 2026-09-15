"""Project list and modal editor for manually configured worker projects."""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from portable_pipe_tools.render_farm.project_registration import ProjectRegistration
from portable_pipe_tools.render_farm.v2_gui_settings import (
    load_registered_projects, save_registered_projects, load_dropbox_root, save_dropbox_root,
)
from portable_pipe_tools.render_farm.dropbox_projects import list_dropbox_projects


class ProjectDialog(tk.Toplevel):
    def __init__(self, parent, *, on_save, project=None, dropbox_projects=None):
        super().__init__(parent)
        self.withdraw()
        self.title("Edit project" if project else "Add project to Render Worker")
        self.transient(parent.winfo_toplevel())
        self.resizable(True, False)
        self.on_save = on_save
        self.original_id = project.project_id if project else None
        self.original_project = project
        self.dropbox_projects = dropbox_projects or {}
        values = project.to_dict() if project else {}
        self.fields = {key: tk.StringVar(self, value=values.get(key, "main" if key == "branch" else ""))
                       for key in ("name", "project_id", "local_uproject", "render_farm_root", "repository", "branch")}
        self.downloads = tk.BooleanVar(self, value=values.get("allow_downloads", False))
        self.error = tk.StringVar(self)
        body = ttk.Frame(self, padding=16)
        body.grid(sticky="nsew")
        self.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        self.entries = {}
        rows = [("Project name", "name"), ("Dropbox project", "project_id"),
                ("Local Unreal project (.uproject)", "local_uproject"),
                ("Show Render Farm folder", "render_farm_root")]
        for row, (label, key) in enumerate(rows):
            self._field(body, row, label, key)
        self.entries["project_id"].destroy()
        choices = list(self.dropbox_projects)
        if self.original_id and self.original_id not in choices:
            choices.append(self.original_id)
        self.entries["project_id"] = ttk.Combobox(body, textvariable=self.fields["project_id"],
                                                   values=choices, state="readonly", width=53)
        self.entries["project_id"].grid(row=1, column=1, sticky="ew", pady=6)
        self.entries["project_id"].bind("<<ComboboxSelected>>", self._select_show)
        self.entries["name"].configure(state="readonly")
        self.entries["render_farm_root"].configure(state="readonly")
        ttk.Button(body, text="Browse...", command=self._browse_project).grid(row=2, column=2, padx=(8, 0))
        ttk.Label(body, text="Project names come from folders directly under the selected Dropbox root. Choose the local Unreal project manually.",
                  wraplength=650).grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 12))
        self.download_checkbox = ttk.Checkbutton(body, text="Allow project downloads", variable=self.downloads,
                                               command=self._download_state)
        self.download_checkbox.grid(row=5, column=0, columnspan=3, sticky="w", pady=(0, 4))
        self._field(body, 6, "Repository URL", "repository")
        self._field(body, 7, "Git branch", "branch")
        ttk.Label(body, text="Uses the worker's UnrealEditor-Cmd.exe setting. Shot, sequence and render settings come from each job.",
                  wraplength=650).grid(row=8, column=0, columnspan=3, sticky="w", pady=(10, 6))
        ttk.Label(body, textvariable=self.error, foreground="#b42318", wraplength=650).grid(
            row=9, column=0, columnspan=3, sticky="w")
        buttons = ttk.Frame(body)
        buttons.grid(row=10, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=(0, 8))
        self.ok_button = ttk.Button(buttons, text="OK", command=self.save)
        self.ok_button.pack(side="left")
        self.bind("<Escape>", lambda event: self.destroy())
        self.bind("<Return>", lambda event: self.save())
        self._download_state()
        self.update_idletasks()
        owner = parent.winfo_toplevel()
        x = owner.winfo_rootx() + max(0, (owner.winfo_width() - self.winfo_reqwidth()) // 2)
        y = owner.winfo_rooty() + max(0, (owner.winfo_height() - self.winfo_reqheight()) // 2)
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.grab_set()
        self.entries["project_id"].focus_set()

    def _field(self, parent, row, label, key):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=6)
        entry = ttk.Entry(parent, textvariable=self.fields[key], width=55)
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        self.entries[key] = entry

    def _select_show(self, *_):
        identifier = self.fields["project_id"].get()
        if identifier in self.dropbox_projects:
            self.fields["name"].set(identifier)
            self.fields["render_farm_root"].set(str(self.dropbox_projects[identifier]))
        elif self.original_project and identifier == self.original_id:
            self.fields["name"].set(self.original_project.name)
            self.fields["render_farm_root"].set(self.original_project.render_farm_root)

    def _download_state(self):
        for key in ("repository", "branch"):
            self.entries[key].configure(state="normal" if self.downloads.get() else "disabled")

    def _browse_project(self):
        selected = filedialog.askopenfilename(parent=self, title="Choose local Unreal project",
                                              filetypes=[("Unreal project", "*.uproject")])
        if selected:
            self.fields["local_uproject"].set(selected)

    def save(self):
        try:
            identifier = self.fields["project_id"].get()
            if identifier not in self.dropbox_projects and identifier != self.original_id:
                raise ValueError("Choose a project from the configured Dropbox folder.")
            self._select_show()
            values = {key: variable.get() for key, variable in self.fields.items()}
            values["allow_downloads"] = self.downloads.get()
            project = ProjectRegistration.from_dict(values)
            self.on_save(project, self.original_id)
        except (ValueError, OSError) as error:
            self.error.set(str(error))
            return
        self.destroy()


class WorkerProjectList(ttk.Frame):
    def __init__(self, parent, *, settings_path, on_change=lambda message: None, on_root_change=lambda: None):
        super().__init__(parent)
        self.settings_path = Path(settings_path)
        self.on_change = on_change
        self.on_root_change = on_root_change
        self.projects = load_registered_projects(self.settings_path)
        self.dialog = None
        self.editing_enabled = True
        self.root_editing_enabled = True
        self.dropbox_root = tk.StringVar(self, value=load_dropbox_root(self.settings_path))
        self.catalog_status = tk.StringVar(self)
        style = ttk.Style(self)
        # Vista's native Treeview field has no color options. Replace only this
        # widget's field element so its disabled background is actually drawn.
        if "WorkerProjects.field" not in style.element_names():
            style.element_create("WorkerProjects.field", "from", "clam", "Treeview.field")
        tree_layout = style.layout("Treeview")
        tree_layout[0] = ("WorkerProjects.field", tree_layout[0][1])
        style.layout("WorkerProjects.Treeview", tree_layout)
        selection_background = style.lookup("Treeview", "background", ("selected",)) or "#0078d7"
        selection_foreground = style.lookup("Treeview", "foreground", ("selected",)) or "#ffffff"
        style.configure("WorkerProjects.Treeview", background="#ffffff", fieldbackground="#ffffff")
        style.map("WorkerProjects.Treeview",
                  background=[("disabled", "#e2e2e2"), ("selected", selection_background)],
                  fieldbackground=[("disabled", "#e2e2e2"), ("!disabled", "#ffffff")],
                  foreground=[("disabled", "#858585"), ("selected", selection_foreground)])
        style.map("WorkerProjects.Treeview.Heading", foreground=[("disabled", "#858585")])
        self.columnconfigure(0, weight=1)
        self.projects_frame = ttk.LabelFrame(self, text="Projects on this worker", padding=8)
        self.projects_frame.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.projects_frame.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(self.projects_frame, columns=("name", "project", "downloads", "status"),
                                 show="headings", selectmode="browse", height=4, style="WorkerProjects.Treeview")
        for key, title, width in [("name", "Project", 150), ("project", "Local Unreal project", 380),
                                  ("downloads", "Downloads", 85), ("status", "Location status", 175)]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=60, stretch=key in ("name", "project"))
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(self.projects_frame, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)
        buttons = ttk.Frame(self.projects_frame)
        buttons.grid(row=0, column=2, sticky="n", padx=(8, 0))
        self.add_button = ttk.Button(buttons, text="+", width=3, command=self.add)
        self.add_button.pack(pady=(0, 5))
        self.remove_button = ttk.Button(buttons, text="−", width=3, command=self.remove, state="disabled")
        self.remove_button.pack()
        ttk.Label(self.projects_frame, text="+ Add project    − Remove selected project    Double-click a project to edit").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(5, 0))
        source = ttk.Frame(self, padding=(8, 0))
        source.grid(row=0, column=0, sticky="ew")
        source.columnconfigure(1, weight=1)
        ttk.Label(source, text="Dropbox project root").grid(row=0, column=0, padx=(0, 8))
        # A native ttk read-only field can ignore fieldbackground on Windows.
        self.root_entry = tk.Entry(source, textvariable=self.dropbox_root, state="readonly",
                                   background="#ffffff", readonlybackground="#ffffff", foreground="#202020",
                                   disabledbackground="#e2e2e2", disabledforeground="#858585",
                                   font="TkDefaultFont", relief="sunken", borderwidth=1)
        self.root_entry.grid(row=0, column=1, sticky="ew")
        self.root_browse_button = ttk.Button(source, text="Browse...", command=self._browse_dropbox)
        self.root_browse_button.grid(row=0, column=2, padx=6)
        self.root_refresh_button = ttk.Button(source, text="Refresh", command=self._refresh_catalog)
        self.root_refresh_button.grid(row=0, column=3)
        ttk.Label(source, textvariable=self.catalog_status).grid(row=1, column=0, columnspan=4, sticky="w")
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)
        self.tree.bind("<Double-1>", self._double_click)
        self.tree.bind("<Return>", lambda event: self.edit())
        self.tree.bind("<Button-1>", lambda event: None if self.editing_enabled else "break")
        self.tree.bind("<KeyPress>", lambda event: None if self.editing_enabled else "break")
        self.refresh()
        self._refresh_catalog()
        self.set_editing_enabled(True)
        self.dropbox_root.trace_add("write", self._root_changed)

    def _root_changed(self, *_):
        self.set_editing_enabled(self.root_editing_enabled)
        self._refresh_catalog()
        self.on_root_change()

    def _browse_dropbox(self):
        if not self.root_editing_enabled:
            return
        selected = filedialog.askdirectory(parent=self, title="Choose Dropbox folder containing the show folders")
        if selected:
            try:
                list_dropbox_projects(selected)
                save_dropbox_root(selected, self.settings_path)
            except (OSError, ValueError) as error:
                messagebox.showerror("Dropbox projects", str(error), parent=self)
                return
            self.dropbox_root.set(selected)

    def _refresh_catalog(self):
        self.dropbox_projects = {}
        try:
            if not self.dropbox_root.get():
                raise ValueError("First, click Browse to choose the Dropbox project root. Other controls unlock after selection.")
            self.dropbox_projects = list_dropbox_projects(self.dropbox_root.get())
            self.catalog_status.set(f"{len(self.dropbox_projects)} Dropbox projects available")
        except (OSError, ValueError) as error:
            self.catalog_status.set(str(error))

    def refresh(self, selected=None):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for project in self.projects:
            self.tree.insert("", "end", iid=project.project_id,
                             values=(project.name, project.local_uproject,
                                     "Allowed" if project.allow_downloads else "Off", project.location_status()))
        if selected and self.tree.exists(selected):
            self.tree.selection_set(selected)
            self.tree.focus(selected)
            self.tree.see(selected)
        self._selection_changed()

    def _selection_changed(self, event=None):
        self.remove_button.configure(state="normal" if self.editing_enabled and self.tree.selection() else "disabled")

    def set_editing_enabled(self, enabled):
        self.root_editing_enabled = enabled
        root_is_set = bool(self.dropbox_root.get().strip())
        self.editing_enabled = enabled and root_is_set
        def update_buttons(parent):
            for child in parent.winfo_children():
                if isinstance(child, ttk.Button):
                    child.configure(state="normal" if self.editing_enabled else "disabled")
                update_buttons(child)
        update_buttons(self.projects_frame)
        self.tree.state(["!disabled" if self.editing_enabled else "disabled"])
        self.root_entry.configure(state="readonly" if enabled else "disabled")
        self.root_browse_button.configure(state="normal" if enabled else "disabled")
        self.root_refresh_button.configure(state="normal" if enabled and root_is_set else "disabled")
        self._selection_changed()

    def _open_dialog(self, project=None):
        if not self.editing_enabled:
            return
        if self.dialog is not None and self.dialog.winfo_exists():
            self.dialog.lift()
            return
        self._refresh_catalog()
        self.dialog = ProjectDialog(self, on_save=self.save_project, project=project,
                                    dropbox_projects=self.dropbox_projects)

    def add(self):
        self._open_dialog()

    def edit(self):
        selected = self.tree.selection()
        if selected:
            self._open_dialog(next(project for project in self.projects if project.project_id == selected[0]))

    def _double_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.edit()

    def save_project(self, project, original_id=None):
        if not self.editing_enabled:
            raise ValueError("Wait for the active render to finish before editing projects.")
        if any(item.project_id.casefold() == project.project_id.casefold()
               and item.project_id != original_id for item in self.projects):
            raise ValueError("A project with that ID is already registered on this worker.")
        updated = [project if item.project_id == original_id else item for item in self.projects]
        if original_id is None:
            updated.append(project)
        save_registered_projects(updated, self.settings_path)
        self.projects = updated
        self.refresh(project.project_id)
        self.on_change(f"Saved project: {project.name}")

    def remove(self):
        if not self.editing_enabled:
            return
        selected = self.tree.selection()
        if not selected:
            return
        updated = [project for project in self.projects if project.project_id != selected[0]]
        try:
            save_registered_projects(updated, self.settings_path)
        except (ValueError, OSError) as error:
            messagebox.showerror("Could not remove project", str(error), parent=self)
            return
        self.projects = updated
        self.refresh()
        self.on_change(f"Removed project registration: {selected[0]}. Project files were kept.")
