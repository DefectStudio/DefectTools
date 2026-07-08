from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ALL_SEQUENCES_LABEL = "All Sequences"
SHOW_MANIFEST_FILENAME = "_show_manifest.json"
SEQUENCE_MANIFEST_SUFFIX = "_sequence_shots_manifest.json"
ALL_SEQUENCES_MANIFEST_FILENAME = "all_sequences_shots_manifest.json"
LOCAL_SAVE_FOLDER_NAME = "LocalSaveFiles"
SHOT_MANAGER_SAVE_FILENAME = "shot_manager_local_save.json"
LOCAL_SAVE_SCHEMA_VERSION = 2
CHECKED_BOX = "☑"
UNCHECKED_BOX = "☐"
MOVE_DISPLAY = "▲  ▼"
RENDER_CONTEXT_SEGMENTS = ("lite", "unreal", "_output")
HERO_MP4_SUFFIX = "_heroMP4s"

COLUMN_TITLES = {
    "move": "Move",
    "order": "Order",
    "is_active": "Is Active?",
    "sequence": "Sequence",
    "shot": "Shot",
    "path": "Folder Path",
}
SHOT_NAME_RE = re.compile(r"^(?P<sequence>[A-Za-z0-9]{3})_(?P<section>\d{3})_(?P<shot>\d{4,})$")


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


@dataclass
class ShotRow:
    order: int
    sequence: str
    shot_name: str
    shot_path: Path
    section_number: int
    shot_number: int
    is_active: bool = False
    start_frame: int | None = None
    end_frame: int | None = None
    level_path: str = ""
    manifest_path: Path | None = None
    source: str = "folder"


@dataclass(frozen=True)
class Mp4GatherResult:
    dump_folder: Path
    copied_count: int
    active_shot_count: int
    missing_output_folders: tuple[str, ...]
    missing_beauty_mp4s: tuple[str, ...]


def _as_path(path_text: str | Path) -> Path:
    return Path(path_text).expanduser()


def _get_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def get_local_save_folder() -> Path:
    return _get_repo_root() / LOCAL_SAVE_FOLDER_NAME


def get_local_save_file_path() -> Path:
    return get_local_save_folder() / SHOT_MANAGER_SAVE_FILENAME


def load_local_save_data() -> dict:
    local_save_file = get_local_save_file_path()
    if not local_save_file.exists():
        return {}
    try:
        data = json.loads(local_save_file.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_local_save_data(data: dict) -> None:
    local_save_folder = get_local_save_folder()
    local_save_folder.mkdir(parents=True, exist_ok=True)
    data["schema_version"] = LOCAL_SAVE_SCHEMA_VERSION
    get_local_save_file_path().write_text(
        json.dumps(data, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def update_local_save_data(**updates: object) -> None:
    data = load_local_save_data()
    for key, value in updates.items():
        if value is not None:
            data[key] = str(value)
    save_local_save_data(data)


def load_saved_dropbox_folder() -> str:
    return str(load_local_save_data().get("dropbox_folder") or "").strip()


def load_saved_selected_show() -> str:
    return str(load_local_save_data().get("selected_show") or "").strip()


def load_saved_selected_sequence() -> str:
    return str(load_local_save_data().get("selected_sequence") or "").strip()


def save_dropbox_folder(dropbox_folder: str | Path) -> None:
    update_local_save_data(dropbox_folder=dropbox_folder)


def get_show_manifest(show_root: str | Path) -> Path | None:
    show_manifest = _as_path(show_root) / SHOW_MANIFEST_FILENAME
    return show_manifest if show_manifest.is_file() else None


def _is_sequence_folder(folder_path: Path) -> bool:
    return folder_path.is_dir() and len(folder_path.name) == 3 and folder_path.name.isalnum() and not folder_path.name.startswith("_")


def _parse_shot_folder_name(folder_name: str) -> tuple[str, int, int] | None:
    match = SHOT_NAME_RE.fullmatch(folder_name)
    if not match:
        return None
    return match.group("sequence").upper(), int(match.group("section")), int(match.group("shot"))


def _coerce_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y", "active"):
        return True
    if text in ("0", "false", "no", "n", "inactive", ""):
        return False
    return bool(value)


def _coerce_optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except Exception:
        return None


def _read_json_file(json_path: Path) -> dict:
    with json_path.open("r", encoding="utf-8") as json_file:
        data = json.load(json_file)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {json_path}")
    return data


def _write_json_file(json_path: Path, data: dict) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8", newline="\n") as json_file:
        json.dump(data, json_file, indent=4, ensure_ascii=False)
        json_file.write("\n")


def _get_sequence_manifest_path(sequence_folder: Path) -> Path:
    return sequence_folder / f"{sequence_folder.name.lower()}{SEQUENCE_MANIFEST_SUFFIX}"


def _get_all_sequences_manifest_path_from_sequence_manifest(manifest_path: Path) -> Path:
    return manifest_path.parent.parent / ALL_SEQUENCES_MANIFEST_FILENAME


def _active_display(is_active: bool) -> str:
    return CHECKED_BOX if is_active else UNCHECKED_BOX


def open_folder_in_file_browser(folder_path: Path) -> None:
    normalized_path = folder_path.resolve()
    if hasattr(os, "startfile"):
        os.startfile(str(normalized_path))
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(normalized_path)])
        return
    subprocess.Popen(["xdg-open", str(normalized_path)])


def _is_beauty_mp4(file_path: Path) -> bool:
    lower_name = file_path.name.lower()
    return file_path.is_file() and lower_name.endswith(".mp4") and "beauty" in lower_name


def _find_latest_beauty_mp4(output_folder: Path) -> Path | None:
    if not output_folder.is_dir():
        return None

    candidates: list[tuple[float, Path]] = []
    for file_path in output_folder.iterdir():
        if not _is_beauty_mp4(file_path):
            continue
        try:
            candidates.append((file_path.stat().st_mtime, file_path))
        except OSError:
            continue

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _build_unique_dest_path(dump_folder: Path, file_name: str, sequence_name: str, shot_name: str) -> Path:
    dest_path = dump_folder / file_name
    if not dest_path.exists():
        return dest_path

    stem = Path(file_name).stem
    ext = Path(file_name).suffix
    prefixed_path = dump_folder / f"{sequence_name}_{shot_name}_{file_name}"
    if not prefixed_path.exists():
        return prefixed_path

    index = 2
    while True:
        numbered_path = dump_folder / f"{sequence_name}_{shot_name}_{stem}_{index}{ext}"
        if not numbered_path.exists():
            return numbered_path
        index += 1


def gather_show_mp4s_for_active_shots(show_root: Path, shot_rows: list[ShotRow]) -> Mp4GatherResult:
    sequences_root = show_root / "sequences"
    show_dump_root = sequences_root / "_output"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    dump_folder = show_dump_root / f"{timestamp}{HERO_MP4_SUFFIX}"
    dump_folder.mkdir(parents=True, exist_ok=True)

    active_rows = [shot_row for shot_row in shot_rows if shot_row.is_active]
    missing_output_folders: list[str] = []
    missing_beauty_mp4s: list[str] = []
    copied_count = 0

    for shot_row in sorted(active_rows, key=lambda row: (row.order, row.sequence.lower(), row.shot_name.lower())):
        shot_output_folder = (
            sequences_root
            / shot_row.sequence
            / shot_row.shot_name
            / RENDER_CONTEXT_SEGMENTS[0]
            / RENDER_CONTEXT_SEGMENTS[1]
            / RENDER_CONTEXT_SEGMENTS[2]
        )

        if not shot_output_folder.is_dir():
            missing_output_folders.append(f"{shot_row.sequence}:{shot_row.shot_name}")
            continue

        latest_mp4_path = _find_latest_beauty_mp4(shot_output_folder)
        if latest_mp4_path is None:
            missing_beauty_mp4s.append(f"{shot_row.sequence}:{shot_row.shot_name}")
            continue

        dest_path = _build_unique_dest_path(
            dump_folder,
            latest_mp4_path.name,
            shot_row.sequence,
            shot_row.shot_name,
        )
        shutil.copy2(latest_mp4_path, dest_path)
        copied_count += 1

    return Mp4GatherResult(
        dump_folder=dump_folder,
        copied_count=copied_count,
        active_shot_count=len(active_rows),
        missing_output_folders=tuple(missing_output_folders),
        missing_beauty_mp4s=tuple(missing_beauty_mp4s),
    )


def save_order_updates_to_manifests(shot_rows: list[ShotRow]) -> int:
    rows_by_manifest: dict[Path, list[ShotRow]] = {}
    for shot_row in shot_rows:
        if shot_row.manifest_path is None:
            continue
        rows_by_manifest.setdefault(shot_row.manifest_path, []).append(shot_row)

    saved_paths: set[Path] = set()

    for manifest_path, manifest_rows in rows_by_manifest.items():
        manifest_data = _read_json_file(manifest_path)
        shots = manifest_data.get("shots") or []
        if not isinstance(shots, list):
            raise ValueError(f"Manifest 'shots' field must be a list: {manifest_path}")

        order_by_shot_name = {shot_row.shot_name: shot_row.order for shot_row in manifest_rows}
        changed = False

        for shot_data in shots:
            if not isinstance(shot_data, dict):
                continue
            shot_name = str(shot_data.get("shot_name") or "").strip()
            if shot_name not in order_by_shot_name:
                continue
            new_order = order_by_shot_name[shot_name]
            if _coerce_optional_int(shot_data.get("order")) != new_order:
                shot_data["order"] = new_order
                changed = True

        if changed:
            _write_json_file(manifest_path, manifest_data)
            saved_paths.add(manifest_path)

    all_sequence_manifest_paths = {
        _get_all_sequences_manifest_path_from_sequence_manifest(manifest_path)
        for manifest_path in rows_by_manifest
    }
    order_by_sequence_and_shot = {
        (shot_row.sequence.upper(), shot_row.shot_name): shot_row.order
        for shot_row in shot_rows
        if shot_row.manifest_path is not None
    }

    for all_sequences_manifest_path in all_sequence_manifest_paths:
        if not all_sequences_manifest_path.is_file():
            continue
        manifest_data = _read_json_file(all_sequences_manifest_path)
        shots = manifest_data.get("shots") or []
        if not isinstance(shots, list):
            continue

        changed = False
        for shot_data in shots:
            if not isinstance(shot_data, dict):
                continue
            sequence_name = str(shot_data.get("sequence_name") or "").strip().upper()
            shot_name = str(shot_data.get("shot_name") or "").strip()
            key = (sequence_name, shot_name)
            if key not in order_by_sequence_and_shot:
                continue
            new_order = order_by_sequence_and_shot[key]
            if _coerce_optional_int(shot_data.get("order")) != new_order:
                shot_data["order"] = new_order
                changed = True

        if changed:
            _write_json_file(all_sequences_manifest_path, manifest_data)
            saved_paths.add(all_sequences_manifest_path)

    return len(saved_paths)


def find_show_folders(dropbox_root: str | Path) -> list[ShowFolderInfo]:
    root = _as_path(dropbox_root)
    if not root.exists():
        raise FileNotFoundError(f"Dropbox folder does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Dropbox folder is not a folder: {root}")
    show_folders = []
    for child in root.iterdir():
        if child.is_dir() and (child / "sequences").is_dir():
            show_folders.append(ShowFolderInfo(show_root=child, show_manifest=get_show_manifest(child)))
    return sorted(show_folders, key=lambda show_info: show_info.name.lower())


def find_sequence_folders(show_root: str | Path) -> list[Path]:
    sequences_root = _as_path(show_root) / "sequences"
    if not sequences_root.exists():
        return []
    return sorted([child for child in sequences_root.iterdir() if _is_sequence_folder(child)], key=lambda path: path.name.upper())


def _shot_rows_from_sequence_manifest(sequence_folder: Path) -> list[ShotRow]:
    manifest_path = _get_sequence_manifest_path(sequence_folder)
    if not manifest_path.is_file():
        return []
    manifest = _read_json_file(manifest_path)
    shots = manifest.get("shots") or []
    if not isinstance(shots, list):
        raise ValueError(f"Manifest 'shots' field must be a list: {manifest_path}")
    sequence_name = str(manifest.get("sequence_name") or sequence_folder.name).upper()
    shot_rows = []
    for index, shot_data in enumerate(shots, start=1):
        if not isinstance(shot_data, dict):
            continue
        shot_name = str(shot_data.get("shot_name") or "").strip()
        parsed = _parse_shot_folder_name(shot_name)
        if parsed is None:
            continue
        shot_sequence, section_number, shot_number = parsed
        if shot_sequence != sequence_name:
            continue
        parsed_order = _coerce_optional_int(shot_data.get("order"))
        order = parsed_order if parsed_order is not None else index
        is_active = _coerce_bool(shot_data.get("is_active", shot_data.get("is_active_value")), default=False)
        shot_rows.append(
            ShotRow(
                order=order,
                sequence=sequence_name,
                shot_name=shot_name,
                shot_path=sequence_folder / shot_name,
                section_number=section_number,
                shot_number=shot_number,
                is_active=is_active,
                start_frame=_coerce_optional_int(shot_data.get("start_frame")),
                end_frame=_coerce_optional_int(shot_data.get("end_frame")),
                level_path=str(shot_data.get("level_path") or ""),
                manifest_path=manifest_path,
                source="manifest",
            )
        )
    return sorted(shot_rows, key=lambda row: (row.order, row.sequence.lower(), row.section_number, row.shot_number, row.shot_name.lower()))


def _fallback_shot_rows_from_sequence_folder(sequence_folder: Path) -> list[ShotRow]:
    sequence_name = sequence_folder.name.upper()
    shot_candidates = []
    for child in sequence_folder.iterdir():
        if not child.is_dir():
            continue
        parsed = _parse_shot_folder_name(child.name)
        if parsed is None:
            continue
        shot_sequence, section_number, shot_number = parsed
        if shot_sequence == sequence_name:
            shot_candidates.append((section_number, shot_number, child))
    shot_candidates.sort(key=lambda row: (row[0], row[1], row[2].name.lower()))
    return [
        ShotRow(
            order=index,
            sequence=sequence_name,
            shot_name=shot_path.name,
            shot_path=shot_path,
            section_number=section_number,
            shot_number=shot_number,
            is_active=False,
            source="folder",
        )
        for index, (section_number, shot_number, shot_path) in enumerate(shot_candidates, start=1)
    ]


def _shot_rows_from_sequence_folder(sequence_folder: Path) -> list[ShotRow]:
    manifest_rows = _shot_rows_from_sequence_manifest(sequence_folder)
    return manifest_rows if manifest_rows else _fallback_shot_rows_from_sequence_folder(sequence_folder)


def find_shot_folders(show_root: str | Path, selected_sequence: str) -> list[ShotRow]:
    show_path = _as_path(show_root)
    if selected_sequence == ALL_SEQUENCES_LABEL:
        sequence_folders = find_sequence_folders(show_path)
    else:
        sequence_path = show_path / "sequences" / selected_sequence
        sequence_folders = [sequence_path] if _is_sequence_folder(sequence_path) else []
    shot_rows = []
    for sequence_folder in sequence_folders:
        shot_rows.extend(_shot_rows_from_sequence_folder(sequence_folder))
    return sorted(shot_rows, key=lambda row: (row.order, row.sequence.lower(), row.section_number, row.shot_number, row.shot_name.lower()))


class ShotManagerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Shot Manager")
        self.root.geometry("1180x700")
        self.root.minsize(920, 520)
        self.dropbox_root_var = tk.StringVar()
        self.show_select_var = tk.StringVar()
        self.sequence_select_var = tk.StringVar(value=ALL_SEQUENCES_LABEL)
        self.status_var = tk.StringVar(value="Choose a Dropbox folder to begin.")
        self.saved_show_name = ""
        self.saved_sequence_name = ""
        self.show_folders_by_name: dict[str, Path] = {}
        self.show_manifests_by_name: dict[str, Path | None] = {}
        self.sequence_folders_by_name: dict[str, Path] = {}
        self.show_manifest: Path | None = None
        self.current_shot_rows: list[ShotRow] = []
        self.shot_rows_by_item_id: dict[str, ShotRow] = {}
        self.shot_sort_column = "order"
        self.shot_sort_reverse = False
        self._build_ui()
        self._load_saved_local_state()

    def run(self) -> None:
        self.root.mainloop()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Shot Manager", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(0, 12))
        controls = ttk.LabelFrame(outer, text="Show Browser", padding=10)
        controls.pack(fill="x", pady=(0, 12))
        controls.columnconfigure(2, weight=1)
        ttk.Label(controls, text="Drop Box Folder").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Button(controls, text="Browse...", command=self._browse_dropbox_folder).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=4)
        ttk.Entry(controls, textvariable=self.dropbox_root_var, state="readonly").grid(row=0, column=2, sticky="ew", pady=4)
        ttk.Button(controls, text="Refresh", command=self._refresh_shows).grid(row=0, column=3, sticky="ew", padx=(8, 0), pady=4)
        ttk.Label(controls, text="Show Select").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.show_combo = ttk.Combobox(controls, textvariable=self.show_select_var, state="readonly", values=[])
        self.show_combo.grid(row=1, column=1, columnspan=3, sticky="ew", pady=4)
        self.show_combo.bind("<<ComboboxSelected>>", self._on_show_selected)
        ttk.Label(controls, text="Sequence Select").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        self.sequence_combo = ttk.Combobox(controls, textvariable=self.sequence_select_var, state="readonly", values=[ALL_SEQUENCES_LABEL])
        self.sequence_combo.grid(row=2, column=1, columnspan=3, sticky="ew", pady=4)
        self.sequence_combo.bind("<<ComboboxSelected>>", self._on_sequence_selected)
        listing_frame = ttk.LabelFrame(outer, text="Shots Listing Window", padding=10)
        listing_frame.pack(fill="both", expand=True)
        listing_frame.rowconfigure(0, weight=1)
        listing_frame.columnconfigure(0, weight=1)
        columns = tuple(COLUMN_TITLES)
        self.shots_tree = ttk.Treeview(listing_frame, columns=columns, show="headings", selectmode="browse")
        self._refresh_column_headings()
        self.shots_tree.column("move", width=70, minwidth=60, stretch=False, anchor="center")
        self.shots_tree.column("order", width=70, minwidth=60, stretch=False, anchor="center")
        self.shots_tree.column("is_active", width=95, minwidth=90, stretch=False, anchor="center")
        self.shots_tree.column("sequence", width=100, minwidth=80, stretch=False, anchor="center")
        self.shots_tree.column("shot", width=160, minwidth=130, stretch=False)
        self.shots_tree.column("path", width=700, minwidth=300, stretch=True)
        self.shots_tree.bind("<Button-1>", self._on_shots_tree_click)
        self.shots_tree.grid(row=0, column=0, sticky="nsew")
        y_scroll = ttk.Scrollbar(listing_frame, orient="vertical", command=self.shots_tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(listing_frame, orient="horizontal", command=self.shots_tree.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.shots_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        actions_frame = ttk.Frame(outer)
        actions_frame.pack(fill="x", pady=(8, 0))
        ttk.Button(actions_frame, text="Fix 0 Orders", command=self._fix_zero_orders).pack(side="left")
        ttk.Button(actions_frame, text="Gather Show MP4s", command=self._gather_show_mp4s).pack(side="right")
        ttk.Label(outer, textvariable=self.status_var, anchor="w").pack(fill="x", pady=(8, 0))

    def _load_saved_local_state(self) -> None:
        local_save_data = load_local_save_data()
        saved_dropbox_folder = str(local_save_data.get("dropbox_folder") or "").strip()
        self.saved_show_name = str(local_save_data.get("selected_show") or "").strip()
        self.saved_sequence_name = str(local_save_data.get("selected_sequence") or "").strip()
        if not saved_dropbox_folder:
            return
        self.dropbox_root_var.set(saved_dropbox_folder)
        if Path(saved_dropbox_folder).is_dir():
            self._refresh_shows(save_local_file=False)
        else:
            self._set_status(f"Saved Dropbox folder was not found: {saved_dropbox_folder}")

    def _browse_dropbox_folder(self) -> None:
        selected = filedialog.askdirectory(title="Choose local Dropbox folder for shows")
        if selected:
            self.dropbox_root_var.set(selected)
            self._refresh_shows()

    def _save_current_selection(self) -> None:
        update_local_save_data(
            dropbox_folder=self.dropbox_root_var.get().strip(),
            selected_show=self.show_select_var.get().strip(),
            selected_sequence=self.sequence_select_var.get().strip(),
        )

    def _refresh_shows(self, save_local_file: bool = True) -> None:
        dropbox_root = self.dropbox_root_var.get().strip()
        if not dropbox_root:
            messagebox.showwarning("Shot Manager", "Please choose the local Dropbox folder first.")
            return
        try:
            show_folders = find_show_folders(dropbox_root)
            if save_local_file:
                save_dropbox_folder(dropbox_root)
        except Exception as error:
            self._set_status(f"Error: {error}")
            messagebox.showerror("Shot Manager Error", str(error))
            return
        self.show_folders_by_name = {show_info.name: show_info.show_root for show_info in show_folders}
        self.show_manifests_by_name = {show_info.name: show_info.show_manifest for show_info in show_folders}
        show_names = list(self.show_folders_by_name)
        manifest_count = sum(1 for show_info in show_folders if show_info.has_show_manifest)
        self.show_combo.configure(values=show_names)
        if show_names:
            current_show = self.show_select_var.get().strip()
            if current_show in show_names:
                selected_show = current_show
            elif self.saved_show_name in show_names:
                selected_show = self.saved_show_name
            else:
                selected_show = show_names[0]
            self.show_select_var.set(selected_show)
            self._refresh_sequences(save_local_file=save_local_file)
            if save_local_file:
                self._save_current_selection()
            self._set_status(f"Found {len(show_names)} show folder(s). Found {manifest_count} show manifest file(s).")
        else:
            self.show_select_var.set("")
            self.sequence_select_var.set(ALL_SEQUENCES_LABEL)
            self.sequence_combo.configure(values=[ALL_SEQUENCES_LABEL])
            self.show_manifest = None
            self.current_shot_rows = []
            self._render_shot_rows()
            if save_local_file:
                self._save_current_selection()
            self._set_status("No show folders found. A show folder must contain a 'sequences' subfolder.")

    def _on_show_selected(self, _event: tk.Event) -> None:
        self.saved_show_name = self.show_select_var.get().strip()
        self._refresh_sequences(save_local_file=True)
        self._save_current_selection()

    def _on_sequence_selected(self, _event: tk.Event) -> None:
        self.saved_sequence_name = self.sequence_select_var.get().strip()
        self._refresh_shots()
        self._save_current_selection()

    def _refresh_sequences(self, save_local_file: bool = False) -> None:
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
        self.sequence_folders_by_name = {sequence_path.name.upper(): sequence_path for sequence_path in sequence_folders}
        sequence_names = [ALL_SEQUENCES_LABEL, *self.sequence_folders_by_name.keys()]
        self.sequence_combo.configure(values=sequence_names)
        current_sequence = self.sequence_select_var.get().strip()
        if self.saved_sequence_name in sequence_names:
            selected_sequence = self.saved_sequence_name
        elif current_sequence in sequence_names:
            selected_sequence = current_sequence
        else:
            selected_sequence = ALL_SEQUENCES_LABEL
        self.sequence_select_var.set(selected_sequence)
        self.saved_sequence_name = selected_sequence
        if save_local_file:
            self._save_current_selection()
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
        sequence_manifest_count = len({row.manifest_path for row in self.current_shot_rows if row.manifest_path is not None})
        active_count = sum(1 for row in self.current_shot_rows if row.is_active)
        inactive_count = len(self.current_shot_rows) - active_count
        where = "across all sequences" if selected_sequence == ALL_SEQUENCES_LABEL else f"in sequence {selected_sequence}"
        self._set_status(f"Showing {len(self.current_shot_rows)} shot(s) {where}; {active_count} active, {inactive_count} inactive; loaded {sequence_manifest_count} sequence manifest(s); {manifest_status}.")

    def _sort_shots_by(self, column_key: str) -> None:
        if column_key == "move":
            return
        if column_key == self.shot_sort_column:
            self.shot_sort_reverse = not self.shot_sort_reverse
        else:
            self.shot_sort_column = column_key
            self.shot_sort_reverse = False
        self._refresh_column_headings()
        self._render_shot_rows()
        direction = "descending" if self.shot_sort_reverse else "ascending"
        self._set_status(f"Sorted by {COLUMN_TITLES.get(column_key, column_key)} ({direction}).")

    def _refresh_column_headings(self) -> None:
        for column_key, column_title in COLUMN_TITLES.items():
            heading_text = column_title
            if column_key == self.shot_sort_column and column_key != "move":
                heading_text = f"{column_title} {'▼' if self.shot_sort_reverse else '▲'}"
            self.shots_tree.heading(column_key, text=heading_text, command=lambda key=column_key: self._sort_shots_by(key))

    def _fix_zero_orders(self) -> None:
        if not self.current_shot_rows:
            messagebox.showinfo("Shot Manager", "There are no shots to update.")
            return

        used_orders = {shot_row.order for shot_row in self.current_shot_rows if shot_row.order > 0}
        zero_order_rows = [shot_row for shot_row in self.current_shot_rows if shot_row.order == 0]

        if not zero_order_rows:
            self._set_status("No shots with order 0 were found in the current shot listing.")
            return

        next_available_order = 1
        fixed_rows: list[ShotRow] = []

        for shot_row in sorted(zero_order_rows, key=lambda row: (row.sequence.lower(), row.section_number, row.shot_number, row.shot_name.lower())):
            while next_available_order in used_orders:
                next_available_order += 1
            shot_row.order = next_available_order
            used_orders.add(next_available_order)
            fixed_rows.append(shot_row)

        try:
            saved_manifest_count = save_order_updates_to_manifests(fixed_rows)
        except Exception as error:
            self._set_status(f"Error saving fixed order values: {error}")
            messagebox.showerror("Shot Manager Error", str(error))
            return

        self._render_shot_rows()
        self._set_status(f"Fixed {len(fixed_rows)} shot order value(s) and saved {saved_manifest_count} manifest file(s).")

    def _move_shot_order(self, shot_row: ShotRow, direction: int) -> None:
        if any(row.order <= 0 for row in self.current_shot_rows):
            messagebox.showwarning("Shot Manager", "Please run Fix 0 Orders before moving shots.")
            self._set_status("Run Fix 0 Orders before moving shots so every shot has a valid order number.")
            return

        ordered_rows = sorted(
            self.current_shot_rows,
            key=lambda row: (row.order, row.sequence.lower(), row.section_number, row.shot_number, row.shot_name.lower()),
        )
        current_index = next((index for index, row in enumerate(ordered_rows) if row is shot_row), -1)
        if current_index < 0:
            return

        target_index = current_index + direction
        if target_index < 0:
            self._set_status(f"{shot_row.shot_name} is already at the top of the current listing.")
            return
        if target_index >= len(ordered_rows):
            self._set_status(f"{shot_row.shot_name} is already at the bottom of the current listing.")
            return

        target_row = ordered_rows[target_index]
        original_order = shot_row.order
        target_order = target_row.order
        shot_row.order = target_order
        target_row.order = original_order

        try:
            saved_manifest_count = save_order_updates_to_manifests([shot_row, target_row])
        except Exception as error:
            shot_row.order = original_order
            target_row.order = target_order
            self._set_status(f"Error saving shot order move: {error}")
            messagebox.showerror("Shot Manager Error", str(error))
            return

        self.shot_sort_column = "order"
        self.shot_sort_reverse = False
        self._refresh_column_headings()
        self._render_shot_rows()
        direction_text = "up" if direction < 0 else "down"
        self._set_status(
            f"Moved {shot_row.shot_name} {direction_text}; swapped order {original_order} with {target_row.shot_name} order {target_order}. Saved {saved_manifest_count} manifest file(s)."
        )

    def _gather_show_mp4s(self) -> None:
        show_path = self._get_selected_show_path()
        if show_path is None:
            messagebox.showwarning("Shot Manager", "Please choose a show first.")
            return

        try:
            all_show_shot_rows = find_shot_folders(show_path, ALL_SEQUENCES_LABEL)
            result = gather_show_mp4s_for_active_shots(show_path, all_show_shot_rows)
        except Exception as error:
            self._set_status(f"Error gathering show MP4s: {error}")
            messagebox.showerror("Shot Manager Error", str(error))
            return

        if result.copied_count == 0:
            self._set_status(
                f"No MP4s copied. Active shots: {result.active_shot_count}; "
                f"missing folders: {len(result.missing_output_folders)}; "
                f"missing beauty MP4s: {len(result.missing_beauty_mp4s)}."
            )
            messagebox.showwarning(
                "Gather Show MP4s",
                "No MP4s were copied. Check that active shots have beauty MP4 renders in lite/unreal/_output.",
            )
            return

        self._set_status(
            f"Gathered {result.copied_count} MP4(s) from {result.active_shot_count} active shot(s) into: {result.dump_folder}."
        )
        self._show_gather_success_dialog(result)

    def _show_gather_success_dialog(self, result: Mp4GatherResult) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Gather Show MP4s")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.columnconfigure(0, weight=1)

        message = f"Copied {result.copied_count} MP4(s) into:\n{result.dump_folder}"
        ttk.Label(dialog, text=message, justify="left", padding=12).grid(row=0, column=0, sticky="ew")

        button_frame = ttk.Frame(dialog, padding=(12, 0, 12, 12))
        button_frame.grid(row=1, column=0, sticky="ew")
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=0)
        button_frame.columnconfigure(2, weight=0)

        def open_output_folder() -> None:
            try:
                open_folder_in_file_browser(result.dump_folder)
            except Exception as error:
                messagebox.showerror(
                    "Open Output Folder",
                    f"Could not open output folder:\n{result.dump_folder}\n\n{error}",
                    parent=dialog,
                )

        ttk.Button(button_frame, text="Open Output Folder", command=open_output_folder).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).grid(row=0, column=2)

        dialog.update_idletasks()
        x_pos = self.root.winfo_rootx() + max((self.root.winfo_width() - dialog.winfo_width()) // 2, 0)
        y_pos = self.root.winfo_rooty() + max((self.root.winfo_height() - dialog.winfo_height()) // 2, 0)
        dialog.geometry(f"+{x_pos}+{y_pos}")
        dialog.grab_set()
        dialog.focus_set()

    def _on_shots_tree_click(self, event: tk.Event) -> str | None:
        if self.shots_tree.identify_region(event.x, event.y) != "cell":
            return None
        column_key = self._get_tree_column_key(event.x)
        item_id = self.shots_tree.identify_row(event.y)
        if not item_id:
            return None
        shot_row = self.shot_rows_by_item_id.get(item_id)
        if shot_row is None:
            return None

        if column_key == "move":
            return self._handle_move_cell_click(event, item_id, shot_row)

        if column_key != "is_active":
            return None

        shot_row.is_active = not shot_row.is_active
        self._render_shot_rows()
        state_text = "active" if shot_row.is_active else "inactive"
        self._set_status(f"Set {shot_row.shot_name} to {state_text} in the Shot Manager view.")
        return "break"

    def _handle_move_cell_click(self, event: tk.Event, item_id: str, shot_row: ShotRow) -> str:
        column_id = self._get_tree_column_id("move")
        cell_bounds = self.shots_tree.bbox(item_id, column_id)
        if not cell_bounds:
            return "break"
        cell_x, _cell_y, cell_width, _cell_height = cell_bounds
        direction = -1 if event.x - cell_x < cell_width / 2 else 1
        self._move_shot_order(shot_row, direction)
        return "break"

    def _get_tree_column_key(self, x_position: int) -> str:
        column_id = self.shots_tree.identify_column(x_position)
        if not column_id.startswith("#"):
            return ""
        try:
            column_index = int(column_id[1:]) - 1
        except ValueError:
            return ""
        columns = tuple(self.shots_tree["columns"])
        if column_index < 0 or column_index >= len(columns):
            return ""
        return str(columns[column_index])

    def _get_tree_column_id(self, column_key: str) -> str:
        columns = tuple(self.shots_tree["columns"])
        try:
            column_index = columns.index(column_key) + 1
        except ValueError:
            return ""
        return f"#{column_index}"

    def _render_shot_rows(self) -> None:
        self._clear_shots()
        for shot_row in self._get_sorted_shot_rows():
            item_id = self.shots_tree.insert(
                "",
                "end",
                values=(
                    MOVE_DISPLAY,
                    shot_row.order,
                    _active_display(shot_row.is_active),
                    shot_row.sequence,
                    shot_row.shot_name,
                    str(shot_row.shot_path),
                ),
            )
            self.shot_rows_by_item_id[item_id] = shot_row

    def _get_sorted_shot_rows(self) -> list[ShotRow]:
        def sort_key(shot_row: ShotRow) -> tuple:
            if self.shot_sort_column == "order":
                return (shot_row.order, shot_row.sequence.lower(), shot_row.section_number, shot_row.shot_number, shot_row.shot_name.lower())
            if self.shot_sort_column == "is_active":
                return (shot_row.is_active, shot_row.order, shot_row.sequence.lower(), shot_row.shot_name.lower())
            if self.shot_sort_column == "sequence":
                return (shot_row.sequence.lower(), shot_row.order, shot_row.section_number, shot_row.shot_number, shot_row.shot_name.lower())
            if self.shot_sort_column == "shot":
                return (shot_row.shot_name.lower(), shot_row.sequence.lower(), shot_row.section_number, shot_row.shot_number)
            if self.shot_sort_column == "path":
                return (str(shot_row.shot_path).lower(),)
            return (shot_row.order, shot_row.sequence.lower())
        return sorted(self.current_shot_rows, key=sort_key, reverse=self.shot_sort_reverse)

    def _clear_shots(self) -> None:
        self.shot_rows_by_item_id = {}
        for item_id in self.shots_tree.get_children():
            self.shots_tree.delete(item_id)

    def _get_selected_show_path(self) -> Path | None:
        selected_show = self.show_select_var.get().strip()
        return self.show_folders_by_name.get(selected_show) if selected_show else None

    def _get_selected_show_manifest(self) -> Path | None:
        selected_show = self.show_select_var.get().strip()
        return self.show_manifests_by_name.get(selected_show) if selected_show else None

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)


def main() -> None:
    app = ShotManagerApp()
    app.run()


if __name__ == "__main__":
    main()
