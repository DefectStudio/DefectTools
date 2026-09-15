"""Worker-only connection setup, available inside the portable application."""

import tkinter as tk
from tkinter import ttk

from portable_pipe_tools.render_farm.cloud_dispatch import (
    DispatcherConnection, load_cloud_settings, save_cloud_settings,
)


class WorkerConnectionDialog(tk.Toplevel):
    def __init__(self, parent, *, on_save, settings_path=None):
        super().__init__(parent)
        self.title("V2 Worker Connection")
        self.transient(parent)
        self.settings_path = settings_path
        self.on_save = on_save
        saved = load_cloud_settings(settings_path)
        self.url = tk.StringVar(self, value=saved.get("api_url", ""))
        self.token = tk.StringVar(self, value=saved.get("worker_token", ""))
        self.error = tk.StringVar(self)
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        for row, (label, variable) in enumerate((("V2 dispatcher URL", self.url), ("Worker token", self.token))):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
            ttk.Entry(body, textvariable=variable, show="*" if row else "", width=58).grid(row=row, column=1, sticky="ew")
        ttk.Label(body, text="Enter the V2 service supplied by your administrator. Localhost refers to this computer.\nSave, then use Check Setup to test access without claiming jobs.", wraplength=560).grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Label(body, textvariable=self.error, foreground="#b42318", wraplength=560).grid(row=3, column=0, columnspan=2)
        buttons = ttk.Frame(body)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=6)
        ttk.Button(buttons, text="Save", command=self.save).pack(side="left")
        self.grab_set()

    def save(self):
        try:
            connection = DispatcherConnection(self.url.get(), "worker", self.token.get())
            save_cloud_settings(api_url=connection.api_url, worker_token=connection.token,
                                settings_path=self.settings_path)
        except Exception as error:
            self.error.set(str(error))
            return
        self.on_save()
        self.destroy()
