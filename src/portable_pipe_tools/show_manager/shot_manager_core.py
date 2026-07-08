from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


ALL_SEQUENCES_LABEL = "All Sequences"
SHOT_NAME_RE = re.compile(
    r"^(?P<sequence>[A-Za-z0-9]{3})_(?P<section>\d{3})_(?P<shot>\d{4,})$"
)


@dataclass(frozen=True)
class ShotRow:
    order: int
    sequence: str
    shot_name: str
    shot_path: Path
    section_number: int
    shot_number: int


def _as_path(path_text: str | Path) -> Path:
    return Path(path_text).expanduser()


def _is_sequence_folder(folder_path: Path) -> bool:
    """
    Sequence folders are expected to be three characters, for example:
    BSH, EXF, JNG.
    """
    return (
        folder_path.is_dir()
        and len(folder_path.name) == 3
        and folder_path.name.isalnum()
        and not folder_path.name.startswith("_")
    )


def _parse_shot_folder_name(folder_name: str) -> tuple[str, int, int] | None:
    match = SHOT_NAME_RE.fullmatch(folder_name)
    if not match:
        return None

    return (
        match.group("sequence").upper(),
        int(match.group("section")),
        int(match.group("shot")),
    )


def find_show_folders(dropbox_root: str | Path) -> list[Path]:
    """
    A show folder is any direct child of the Dropbox/root folder that has
    a child folder named 'sequences'.
    """
    root = _as_path(dropbox_root)

    if not root.exists():
        raise FileNotFoundError(f"Dropbox folder does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Dropbox folder is not a folder: {root}")

    show_folders = [
        child
        for child in root.iterdir()
        if child.is_dir() and (child / "sequences").is_dir()
    ]

    return sorted(show_folders, key=lambda path: path.name.lower())


def find_sequence_folders(show_root: str | Path) -> list[Path]:
    sequences_root = _as_path(show_root) / "sequences"

    if not sequences_root.exists():
        return []

    sequence_folders = [
        child
        for child in sequences_root.iterdir()
        if _is_sequence_folder(child)
    ]

    return sorted(sequence_folders, key=lambda path: path.name.upper())


def find_shot_folders(show_root: str | Path, selected_sequence: str) -> list[ShotRow]:
    show_path = _as_path(show_root)

    if selected_sequence == ALL_SEQUENCES_LABEL:
        sequence_folders = find_sequence_folders(show_path)
    else:
        sequence_path = show_path / "sequences" / selected_sequence
        sequence_folders = [sequence_path] if _is_sequence_folder(sequence_path) else []

    shot_candidates: list[tuple[str, int, int, Path]] = []

    for sequence_folder in sequence_folders:
        sequence_name = sequence_folder.name.upper()

        for child in sequence_folder.iterdir():
            if not child.is_dir():
                continue

            parsed = _parse_shot_folder_name(child.name)
            if parsed is None:
                continue

            shot_sequence, section_number, shot_number = parsed
            if shot_sequence != sequence_name:
                continue

            shot_candidates.append(
                (
                    shot_sequence,
                    section_number,
                    shot_number,
                    child,
                )
            )

    shot_candidates.sort(
        key=lambda row: (
            row[0],
            row[1],
            row[2],
            row[3].name.lower(),
        )
    )

    return [
        ShotRow(
            order=index,
            sequence=sequence_name,
            shot_name=shot_path.name,
            shot_path=shot_path,
            section_number=section_number,
            shot_number=shot_number,
        )
        for index, (sequence_name, section_number, shot_number, shot_path)
        in enumerate(shot_candidates, start=1)
    ]


class ShotManagerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Shot Manager")
        self.root.geometry("1100x700")
        self.root.minsize(850, 520)

        self.dropbox_root_var = tk.StringVar()
        self.show_select_var = tk.StringVar()
        self.sequence_select_var = tk.StringVar(value=ALL_SEQUENCES_LABEL)
        self.status_var = tk.StringVar(value="Choose a Dropbox folder to begin.")

        self.show_folders_by_name: dict[str, Path] = {}
        self.sequence_folders_by_name: dict[str, Path] = {}

        self._build_ui()

    def run(self) -> None:
        self.root.mainloop()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        title = ttk.Label(
            outer,
            text="Shot Manager",
            font=("Segoe UI", 18, "bold"),
        )
        title.pack(anchor="w", pady=(0, 12))

        controls = ttk.LabelFrame(outer, text="Show Browser", padding=10)
        controls.pack(fill="x", pady=(0, 12))
        controls.columnconfigure(2, weight=1)

        ttk.Label(controls, text="Drop Box Folder").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=4,
        )

        ttk.Button(
            controls,
            text="Browse...",
            command=self._browse_dropbox_folder,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=4)

        dropbox_display = ttk.Entry(
            controls,
            textvariable=self.dropbox_root_var,
            state="readonly",
        )
        dropbox_display.grid(row=0, column=2, sticky="ew", pady=4)

        ttk.Button(
            controls,
            text="Refresh",
            command=self._refresh_shows,
        ).grid(row=0, column=3, sticky="ew", padx=(8, 0), pady=4)

        ttk.Label(controls, text="Show Select").grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=4,
        )

        self.show_combo = ttk.Combobox(
            controls,
            textvariable=self.show_select_var,
            state="readonly",
            values=[],
        )
        self.show_combo.grid(row=1, column=1, columnspan=3, sticky="ew", pady=4)
        self.show_combo.bind("<<ComboboxSelected>>", self._on_show_selected)

        ttk.Label(controls, text="Sequence Select").grid(
            row=2,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=4,
        )

        self.sequence_combo = ttk.Combobox(
            controls,
            textvariable=self.sequence_select_var,
            state="readonly",
            values=[ALL_SEQUENCES_LABEL],
        )
        self.sequence_combo.grid(row=2, column=1, columnspan=3, sticky="ew", pady=4)
        self.sequence_combo.bind("<<ComboboxSelected>>", self._on_sequence_selected)

        listing_frame = ttk.LabelFrame(outer, text="Shots Listing Window", padding=10)
        listing_frame.pack(fill="both", expand=True)
        listing_frame.rowconfigure(0, weight=1)
        listing_frame.columnconfigure(0, weight=1)

        columns = ("order", "sequence", "shot", "path")
        self.shots_tree = ttk.Treeview(
            listing_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        self.shots_tree.heading("order", text="Order")
        self.shots_tree.heading("sequence", text="Sequence")
        self.shots_tree.heading("shot", text="Shot")
        self.shots_tree.heading("path", text="Folder Path")

        self.shots_tree.column("order", width=70, minwidth=60, stretch=False, anchor="center")
        self.shots_tree.column("sequence", width=100, minwidth=80, stretch=False, anchor="center")
        self.shots_tree.column("shot", width=160, minwidth=130, stretch=False)
        self.shots_tree.column("path", width=700, minwidth=300, stretch=True)

        self.shots_tree.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(
            listing_frame,
            orient="vertical",
            command=self.shots_tree.yview,
        )
        y_scroll.grid(row=0, column=1, sticky="ns")

        x_scroll = ttk.Scrollbar(
            listing_frame,
            orient="horizontal",
            command=self.shots_tree.xview,
        )
        x_scroll.grid(row=1, column=0, sticky="ew")

        self.shots_tree.configure(
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )

        status = ttk.Label(
            outer,
            textvariable=self.status_var,
            anchor="w",
        )
        status.pack(fill="x", pady=(8, 0))

    def _browse_dropbox_folder(self) -> None:
        selected = filedialog.askdirectory(
            title="Choose local Dropbox folder for shows",
        )
        if not selected:
            return

        self.dropbox_root_var.set(selected)
        self._refresh_shows()

    def _refresh_shows(self) -> None:
        dropbox_root = self.dropbox_root_var.get().strip()

        if not dropbox_root:
            messagebox.showwarning(
                "Shot Manager",
                "Please choose the local Dropbox folder first.",
            )
            return

        try:
            show_folders = find_show_folders(dropbox_root)
        except Exception as error:
            self._set_status(f"Error: {error}")
            messagebox.showerror("Shot Manager Error", str(error))
            return

        self.show_folders_by_name = {
            show_path.name: show_path
            for show_path in show_folders
        }

        show_names = list(self.show_folders_by_name)

        self.show_combo.configure(values=show_names)

        if show_names:
            current_show = self.show_select_var.get()
            selected_show = current_show if current_show in show_names else show_names[0]
            self.show_select_var.set(selected_show)
            self._refresh_sequences()
            self._set_status(f"Found {len(show_names)} show folder(s).")
        else:
            self.show_select_var.set("")
            self.sequence_select_var.set(ALL_SEQUENCES_LABEL)
            self.sequence_combo.configure(values=[ALL_SEQUENCES_LABEL])
            self._clear_shots()
            self._set_status("No show folders found. A show folder must contain a 'sequences' subfolder.")

    def _on_show_selected(self, _event: tk.Event) -> None:
        self._refresh_sequences()

    def _on_sequence_selected(self, _event: tk.Event) -> None:
        self._refresh_shots()

    def _refresh_sequences(self) -> None:
        show_path = self._get_selected_show_path()

        if show_path is None:
            self.sequence_folders_by_name = {}
            self.sequence_combo.configure(values=[ALL_SEQUENCES_LABEL])
            self.sequence_select_var.set(ALL_SEQUENCES_LABEL)
            self._clear_shots()
            return

        sequence_folders = find_sequence_folders(show_path)
        self.sequence_folders_by_name = {
            sequence_path.name.upper(): sequence_path
            for sequence_path in sequence_folders
        }

        sequence_names = [ALL_SEQUENCES_LABEL, *self.sequence_folders_by_name.keys()]
        self.sequence_combo.configure(values=sequence_names)

        current_sequence = self.sequence_select_var.get()
        if current_sequence not in sequence_names:
            self.sequence_select_var.set(ALL_SEQUENCES_LABEL)

        self._refresh_shots()

    def _refresh_shots(self) -> None:
        show_path = self._get_selected_show_path()

        if show_path is None:
            self._clear_shots()
            return

        selected_sequence = self.sequence_select_var.get().strip() or ALL_SEQUENCES_LABEL

        try:
            shot_rows = find_shot_folders(show_path, selected_sequence)
        except Exception as error:
            self._set_status(f"Error: {error}")
            messagebox.showerror("Shot Manager Error", str(error))
            return

        self._clear_shots()

        for shot_row in shot_rows:
            self.shots_tree.insert(
                "",
                "end",
                values=(
                    shot_row.order,
                    shot_row.sequence,
                    shot_row.shot_name,
                    str(shot_row.shot_path),
                ),
            )

        if selected_sequence == ALL_SEQUENCES_LABEL:
            self._set_status(
                f"Showing {len(shot_rows)} shot folder(s) across all sequences."
            )
        else:
            self._set_status(
                f"Showing {len(shot_rows)} shot folder(s) in sequence {selected_sequence}."
            )

    def _clear_shots(self) -> None:
        for item_id in self.shots_tree.get_children():
            self.shots_tree.delete(item_id)

    def _get_selected_show_path(self) -> Path | None:
        selected_show = self.show_select_var.get().strip()
        if not selected_show:
            return None

        return self.show_folders_by_name.get(selected_show)

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)


def main() -> None:
    app = ShotManagerApp()
    app.run()


if __name__ == "__main__":
    main()
