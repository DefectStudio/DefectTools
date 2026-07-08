from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


ALL_SEQUENCES_LABEL = "All Sequences"
SHOW_MANIFEST_FILENAME = "_show_manifest.json"
LOCAL_SAVE_FOLDER_NAME = "LocalSaveFiles"
SHOT_MANAGER_SAVE_FILENAME = "shot_manager_local_save.json"
LOCAL_SAVE_SCHEMA_VERSION = 1

COLUMN_TITLES = {
    "order": "Order",
    "sequence": "Sequence",
    "shot": "Shot",
    "path": "Folder Path",
}
SHOT_NAME_RE = re.compile(
    r"^(?P<sequence>[A-Za-z0-9]{3})_(?P<section>\d{3})_(?P<shot>\d{4,})$"
)


@dataclass(frozen=True)
class ShowFolderInfo:
    show_root: Path
    show_manifest: Path | None

    @property
    def name(self) -> str:
        return self.show_root.name

    @property
    def has_show_manifest(self) -> bool:
        return self.show_manifest is not None


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


def _get_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def get_local_save_folder() -> Path:
    return _get_repo_root() / LOCAL_SAVE_FOLDER_NAME


def get_local_save_file_path() -> Path:
    return get_local_save_folder() / SHOT_MANAGER_SAVE_FILENAME


def load_saved_dropbox_folder() -> str:
    local_save_file = get_local_save_file_path()

    if not local_save_file.exists():
        return ""

    try:
        data = json.loads(local_save_file.read_text(encoding="utf-8"))
    except Exception:
        return ""

    if not isinstance(data, dict):
        return ""

    return str(data.get("dropbox_folder") or "").strip()


def save_dropbox_folder(dropbox_folder: str | Path) -> None:
    local_save_folder = get_local_save_folder()
    local_save_folder.mkdir(parents=True, exist_ok=True)

    data = {
        "schema_version": LOCAL_SAVE_SCHEMA_VERSION,
        "dropbox_folder": str(dropbox_folder),
    }

    get_local_save_file_path().write_text(
        json.dumps(data, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_show_manifest(show_root: str | Path) -> Path | None:
    show_manifest = _as_path(show_root) / SHOW_MANIFEST_FILENAME

    if show_manifest.is_file():
        return show_manifest

    return None


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


def find_show_folders(dropbox_root: str | Path) -> list[ShowFolderInfo]:
    """
    A show folder is any direct child of the Dropbox/root folder that has
    a child folder named 'sequences'.
    """
    root = _as_path(dropbox_root)

    if not root.exists():
        raise FileNotFoundError(f"Dropbox folder does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Dropbox folder is not a folder: {root}")

    show_folders: list[ShowFolderInfo] = []

    for child in root.iterdir():
        if not child.is_dir():
            continue

        if not (child / "sequences").is_dir():
            continue

        show_manifest = get_show_manifest(child)
        show_folders.append(
            ShowFolderInfo(
                show_root=child,
                show_manifest=show_manifest,
            )
        )

    return sorted(show_folders, key=lambda show_info: show_info.name.lower())


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
        self.show_manifests_by_name: dict[str, Path | None] = {}
        self.sequence_folders_by_name: dict[str, Path] = {}
        self.show_manifest: Path | None = None
        self.current_shot_rows: list[ShotRow] = []
        self.shot_sort_column = "order"
        self.shot_sort_reverse = False

        self._build_ui()
        self._load_saved_dropbox_folder()

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

        columns = tuple(COLUMN_TITLES)
        self.shots_tree = ttk.Treeview(
            listing_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        self._refresh_column_headings()

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

    def _load_saved_dropbox_folder(self) -> None:
        saved_dropbox_folder = load_saved_dropbox_folder()
        if not saved_dropbox_folder:
            return

        self.dropbox_root_var.set(saved_dropbox_folder)

        if Path(saved_dropbox_folder).is_dir():
            self._refresh_shows(save_local_file=False)
        else:
            self._set_status(f"Saved Dropbox folder was not found: {saved_dropbox_folder}")

    def _browse_dropbox_folder(self) -> None:
        selected = filedialog.askdirectory(
            title="Choose local Dropbox folder for shows",
        )
        if not selected:
            return

        self.dropbox_root_var.set(selected)
        self._refresh_shows()

    def _refresh_shows(self, save_local_file: bool = True) -> None:
        dropbox_root = self.dropbox_root_var.get().strip()

        if not dropbox_root:
            messagebox.showwarning(
                "Shot Manager",
                "Please choose the local Dropbox folder first.",
            )
            return

        try:
            show_folders = find_show_folders(dropbox_root)
            if save_local_file:
                save_dropbox_folder(dropbox_root)
        except Exception as error:
            self._set_status(f"Error: {error}")
            messagebox.showerror("Shot Manager Error", str(error))
            return

        self.show_folders_by_name = {
            show_info.name: show_info.show_root
            for show_info in show_folders
        }
        self.show_manifests_by_name = {
            show_info.name: show_info.show_manifest
            for show_info in show_folders
        }

        show_names = list(self.show_folders_by_name)
        manifest_count = sum(1 for show_info in show_folders if show_info.has_show_manifest)

        self.show_combo.configure(values=show_names)

        if show_names:
            current_show = self.show_select_var.get()
            selected_show = current_show if current_show in show_names else show_names[0]
            self.show_select_var.set(selected_show)
            self._refresh_sequences()
            self._set_status(
                f"Found {len(show_names)} show folder(s). Found {manifest_count} show manifest file(s)."
            )
        else:
            self.show_select_var.set("")
            self.sequence_select_var.set(ALL_SEQUENCES_LABEL)
            self.sequence_combo.configure(values=[ALL_SEQUENCES_LABEL])
            self.show_manifest = None
            self.current_shot_rows = []
            self._render_shot_rows()
            self._set_status("No show folders found. A show folder must contain a 'sequences' subfolder.")

    def _on_show_selected(self, _event: tk.Event) -> None:
        self._refresh_sequences()

    def _on_sequence_selected(self, _event: tk.Event) -> None:
        self._refresh_shots()

    def _refresh_sequences(self) -> None:
        show_path = self._get_selected_show_path()
        self.show_manifest = self._get_selected_show_manifest()

        if show_path is None:
            self.sequence_folders_by_name = {}
            self.sequence_combo.configure(values=[ALL_SEQUENCES_LABEL])
            self.sequence_select_var.set(ALL_SEQUENCES_LABEL)
            self.current_shot_rows = []
            self._render_shot_rows()
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
            self.current_shot_rows = []
            self._render_shot_rows()
            return

        selected_sequence = self.sequence_select_var.get().strip() or ALL_SEQUENCES_LABEL

        try:
            self.current_shot_rows = find_shot_folders(show_path, selected_sequence)
        except Exception as error:
            self._set_status(f"Error: {error}")
            messagebox.showerror("Shot Manager Error", str(error))
            return

        self._render_shot_rows()

        manifest_status = "show manifest found" if self.show_manifest else "show manifest missing"
        if selected_sequence == ALL_SEQUENCES_LABEL:
            self._set_status(
                f"Showing {len(self.current_shot_rows)} shot folder(s) across all sequences; {manifest_status}."
            )
        else:
            self._set_status(
                f"Showing {len(self.current_shot_rows)} shot folder(s) in sequence {selected_sequence}; {manifest_status}."
            )

    def _sort_shots_by(self, column_key: str) -> None:
        if column_key == self.shot_sort_column:
            self.shot_sort_reverse = not self.shot_sort_reverse
        else:
            self.shot_sort_column = column_key
            self.shot_sort_reverse = False

        self._refresh_column_headings()
        self._render_shot_rows()

        direction = "descending" if self.shot_sort_reverse else "ascending"
        column_title = COLUMN_TITLES.get(column_key, column_key)
        self._set_status(f"Sorted by {column_title} ({direction}).")

    def _refresh_column_headings(self) -> None:
        for column_key, column_title in COLUMN_TITLES.items():
            heading_text = column_title
            if column_key == self.shot_sort_column:
                heading_text = f"{column_title} {'▼' if self.shot_sort_reverse else '▲'}"

            self.shots_tree.heading(
                column_key,
                text=heading_text,
                command=lambda key=column_key: self._sort_shots_by(key),
            )

    def _render_shot_rows(self) -> None:
        self._clear_shots()

        for shot_row in self._get_sorted_shot_rows():
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

    def _get_sorted_shot_rows(self) -> list[ShotRow]:
        def sort_key(shot_row: ShotRow) -> tuple:
            if self.shot_sort_column == "order":
                return (shot_row.order,)

            if self.shot_sort_column == "sequence":
                return (
                    shot_row.sequence.lower(),
                    shot_row.section_number,
                    shot_row.shot_number,
                    shot_row.shot_name.lower(),
                )

            if self.shot_sort_column == "shot":
                return (
                    shot_row.shot_name.lower(),
                    shot_row.sequence.lower(),
                    shot_row.section_number,
                    shot_row.shot_number,
                )

            if self.shot_sort_column == "path":
                return (str(shot_row.shot_path).lower(),)

            return (shot_row.order,)

        return sorted(
            self.current_shot_rows,
            key=sort_key,
            reverse=self.shot_sort_reverse,
        )

    def _clear_shots(self) -> None:
        for item_id in self.shots_tree.get_children():
            self.shots_tree.delete(item_id)

    def _get_selected_show_path(self) -> Path | None:
        selected_show = self.show_select_var.get().strip()
        if not selected_show:
            return None

        return self.show_folders_by_name.get(selected_show)

    def _get_selected_show_manifest(self) -> Path | None:
        selected_show = self.show_select_var.get().strip()
        if not selected_show:
            return None

        return self.show_manifests_by_name.get(selected_show)

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)


def main() -> None:
    app = ShotManagerApp()
    app.run()


if __name__ == "__main__":
    main()
