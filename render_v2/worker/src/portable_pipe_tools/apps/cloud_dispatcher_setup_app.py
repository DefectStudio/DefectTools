from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from portable_pipe_tools.render_farm.cloud_dispatch import (
    DispatcherClient,
    DispatcherConnection,
    load_cloud_settings,
    save_cloud_settings,
)


DEFAULT_API_URL = "https://defect-farm-api.twilight-tooth-7b7c.workers.dev"
ROLE_LABELS = {
    "Render Worker": "worker",
    "Unreal Submitter": "submit",
    "Farm Manager": "manager",
}


class CloudDispatcherSetupApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Defect Farm Cloud Setup")
        self.root.geometry("720x330")
        self.root.minsize(620, 300)

        settings = load_cloud_settings()
        self.api_url_var = tk.StringVar(
            value=str(settings.get("api_url") or DEFAULT_API_URL)
        )
        self.role_label_var = tk.StringVar(value="Render Worker")
        self.token_var = tk.StringVar()
        configured_roles = [
            label
            for label, role in ROLE_LABELS.items()
            if str(settings.get(f"{role}_token") or "").strip()
        ]
        configured_text = (
            ", ".join(configured_roles) if configured_roles else "None yet"
        )
        self.status_var = tk.StringVar(
            value=f"Configured on this computer: {configured_text}"
        )

        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)

        ttk.Label(
            outer,
            text="Defect Farm Cloud Dispatcher",
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        ttk.Label(
            outer,
            text=(
                "Configure this computer without storing farm keys in Git. "
                "Ask the farm administrator for the key matching this machine's role."
            ),
            wraplength=650,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 16))

        ttk.Label(outer, text="Cloud API").grid(
            row=2, column=0, sticky="w", padx=(0, 12), pady=6
        )
        ttk.Entry(outer, textvariable=self.api_url_var).grid(
            row=2, column=1, sticky="ew", pady=6
        )

        ttk.Label(outer, text="This computer's role").grid(
            row=3, column=0, sticky="w", padx=(0, 12), pady=6
        )
        ttk.Combobox(
            outer,
            textvariable=self.role_label_var,
            values=tuple(ROLE_LABELS),
            state="readonly",
        ).grid(row=3, column=1, sticky="w", pady=6)

        ttk.Label(outer, text="Role key").grid(
            row=4, column=0, sticky="w", padx=(0, 12), pady=6
        )
        token_entry = ttk.Entry(outer, textvariable=self.token_var, show="•")
        token_entry.grid(row=4, column=1, sticky="ew", pady=6)
        token_entry.focus_set()

        ttk.Label(
            outer,
            textvariable=self.status_var,
            wraplength=650,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(14, 8))

        buttons = ttk.Frame(outer)
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="Cancel", command=self.root.destroy).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(
            buttons,
            text="Verify and Save",
            command=self._verify_and_save,
        ).pack(side="right")

    def _verify_and_save(self) -> None:
        api_url = self.api_url_var.get().strip()
        role_label = self.role_label_var.get()
        role = ROLE_LABELS[role_label]
        token = self.token_var.get().strip()
        if not token:
            messagebox.showerror(
                "Defect Farm Cloud Setup",
                "Paste the role key supplied by the farm administrator.",
                parent=self.root,
            )
            return

        self.status_var.set("Verifying the encrypted connection with Cloudflare...")
        self.root.update_idletasks()
        try:
            connection = DispatcherConnection(api_url=api_url, role=role, token=token)
            confirmed_role = DispatcherClient(connection).check_auth()
            if confirmed_role != role:
                raise ValueError(
                    f"That key belongs to the {confirmed_role} role, not {role}."
                )
            keyword = f"{role}_token"
            save_cloud_settings(api_url=api_url, **{keyword: token})
        except Exception as error:
            self.status_var.set("Verification failed; nothing was saved.")
            messagebox.showerror(
                "Defect Farm Cloud Setup",
                f"Could not verify this role key:\n{error}",
                parent=self.root,
            )
            return

        self.token_var.set("")
        self.status_var.set(f"Verified and saved: {role_label}")
        messagebox.showinfo(
            "Defect Farm Cloud Setup",
            f"{role_label} Cloud Dispatcher access is ready on this computer.",
            parent=self.root,
        )

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    CloudDispatcherSetupApp().run()


if __name__ == "__main__":
    main()
