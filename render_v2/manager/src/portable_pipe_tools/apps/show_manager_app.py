from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from portable_pipe_tools.show_manager.show_manager_core import (
    create_show,
    preview_show,
    validate_show,
)


class ShowManagerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Show Manager")
        self.root.geometry("900x650")
        self.root.minsize(760, 520)

        self.dropbox_root_var = tk.StringVar()
        self.show_name_var = tk.StringVar()

        self._build_ui()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        title = ttk.Label(
            outer,
            text="Show Manager",
            font=("Segoe UI", 16, "bold"),
        )
        title.pack(anchor="w", pady=(0, 12))

        form = ttk.Frame(outer)
        form.pack(fill="x")

        ttk.Label(form, text="File Server / Dropbox Root Path").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=4,
        )

        root_entry = ttk.Entry(form, textvariable=self.dropbox_root_var)
        root_entry.grid(row=0, column=1, sticky="ew", pady=4)

        browse_button = ttk.Button(form, text="Browse...", command=self._browse_root)
        browse_button.grid(row=0, column=2, sticky="ew", padx=(8, 0), pady=4)

        ttk.Label(form, text="Show Name").grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=4,
        )

        show_entry = ttk.Entry(form, textvariable=self.show_name_var)
        show_entry.grid(row=1, column=1, sticky="ew", pady=4)

        form.columnconfigure(1, weight=1)

        button_row = ttk.Frame(outer)
        button_row.pack(fill="x", pady=(12, 8))

        ttk.Button(
            button_row,
            text="Preview Folder Structure",
            command=self._preview,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            button_row,
            text="Create Show",
            command=self._create_show,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            button_row,
            text="Validate Existing Show",
            command=self._validate_show,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            button_row,
            text="Clear Log",
            command=self._clear_log,
        ).pack(side="right")

        log_frame = ttk.Frame(outer)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, wrap="none", height=24)
        self.log_text.pack(side="left", fill="both", expand=True)

        y_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        y_scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=y_scroll.set)

        x_scroll = ttk.Scrollbar(outer, orient="horizontal", command=self.log_text.xview)
        x_scroll.pack(fill="x")
        self.log_text.configure(xscrollcommand=x_scroll.set)

        self._log("Ready.")
        self._log("Choose a Dropbox/File Server root, enter a show name, then Preview.")

    def run(self) -> None:
        self.root.mainloop()

    def _browse_root(self) -> None:
        selected = filedialog.askdirectory(title="Choose File Server / Dropbox Root")
        if selected:
            self.dropbox_root_var.set(selected)

    def _get_inputs(self) -> tuple[str, str]:
        dropbox_root = self.dropbox_root_var.get().strip()
        show_name = self.show_name_var.get().strip()

        if not dropbox_root:
            raise ValueError("Please choose a File Server / Dropbox root path.")

        if not show_name:
            raise ValueError("Please enter a show name.")

        return dropbox_root, show_name

    def _preview(self) -> None:
        try:
            dropbox_root, show_name = self._get_inputs()
            lines = preview_show(dropbox_root, show_name)
            self._log_block(lines)
        except Exception as error:
            self._show_error(error)

    def _create_show(self) -> None:
        try:
            dropbox_root, show_name = self._get_inputs()
            preview_lines = preview_show(dropbox_root, show_name)

            show_root_line = next(
                line for line in preview_lines if line.startswith("Show Root:")
            )

            confirmed = messagebox.askyesno(
                "Create Show",
                f"{show_root_line}\n\nCreate this show folder structure?",
            )

            if not confirmed:
                self._log("Create cancelled.")
                return

            result = create_show(dropbox_root, show_name)

            self._log("")
            self._log("CREATE SHOW RESULT")
            self._log("------------------")
            self._log_block(result.messages)

            if result.created_folders:
                self._log("")
                self._log("Created folders:")
                for folder_path in result.created_folders:
                    self._log(f"  {folder_path}")

            if result.missing_folders:
                self._log("")
                self._log("Missing folders after create:")
                for folder_path in result.missing_folders:
                    self._log(f"  {folder_path}")

            messagebox.showinfo("Create Show", "Show creation finished.")

        except Exception as error:
            self._show_error(error)

    def _validate_show(self) -> None:
        try:
            dropbox_root, show_name = self._get_inputs()
            result = validate_show(dropbox_root, show_name)

            self._log("")
            self._log_block(result.messages)

            if result.missing_folders:
                messagebox.showwarning(
                    "Validate Existing Show",
                    f"Validation finished with {len(result.missing_folders)} missing folders.",
                )
            else:
                messagebox.showinfo(
                    "Validate Existing Show",
                    "Validation finished. No missing folders found.",
                )

        except Exception as error:
            self._show_error(error)

    def _clear_log(self) -> None:
        self.log_text.delete("1.0", "end")

    def _log(self, message: str) -> None:
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")

    def _log_block(self, lines: list[str]) -> None:
        for line in lines:
            self._log(line)

    def _show_error(self, error: Exception) -> None:
        message = str(error)
        self._log("")
        self._log("ERROR")
        self._log("-----")
        self._log(message)
        messagebox.showerror("Show Manager Error", message)


def main() -> None:
    app = ShowManagerApp()
    app.run()


if __name__ == "__main__":
    main()

