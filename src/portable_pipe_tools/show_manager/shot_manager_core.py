from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import xml.etree.ElementTree as ET

ALL_SEQUENCES_LABEL = "All Sequences"
SHOW_MANIFEST_FILENAME = "_show_manifest.json"
SEQUENCE_MANIFEST_SUFFIX = "_sequence_shots_manifest.json"
LOCAL_SAVE_FOLDER_NAME = "LocalSaveFiles"
SHOT_MANAGER_SAVE_FILENAME = "shot_manager_local_save.json"
LOCAL_SAVE_SCHEMA_VERSION = 2
CHECKED_BOX = "☑"
UNCHECKED_BOX = "☐"
MOVE_DISPLAY = "▲  ▼"
SHOT_TREE_ROW_HEIGHT = 30
RENDER_CONTEXT_SEGMENTS = ("lite", "unreal", "_output")
HERO_MP4_SUFFIX = "_heroMP4s"
EDL_EMPTY_DISPLAY = "—"
EDL_FRAME_HANDLE_COUNT = 10

COLUMN_TITLES = {
    "move": "Move",
    "shot": "Shot",
    "order": "Current Order",
    "edl_order": "EDL Order",
    "is_active": "Current Active",
    "edl_is_active": "EDL Active",
    "frame_range": "Frame Range",
    "keep_range": "Keep Range",
    "edl_frame_range": "EDL Frame Range",
    "edl_proposed_range": "EDL Proposed Range",
    "sequence": "Sequence",
    "path": "Folder Path",
}
SHOT_NAME_RE = re.compile(r"^(?P<sequence>[A-Za-z0-9]{3})_(?P<section>\d{3})_(?P<shot>\d{4,})$")
EDL_SHOT_NAME_RE = re.compile(
    r"(?i)(?<![A-Z0-9])(?P<sequence>[A-Z]{3})_000_(?P<shot>\d{4})(?!\d)"
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
    keep_range: bool = False
    edl_order: int | None = None
    edl_is_active: bool | None = None
    edl_frame_ranges: tuple[tuple[int, int], ...] = ()
    edl_proposed_range: tuple[int, int] | None = None


class SequenceManifestError(ValueError):
    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path
        super().__init__(f"Invalid sequence manifest: {manifest_path}")


@dataclass(frozen=True)
class EdlShotOccurrence:
    edit_index: int
    timeline_start: int
    timeline_end: int
    source_in: int | None
    source_out: int | None
    sequence: str
    shot_name: str
    source_name: str


@dataclass(frozen=True)
class ResolveEdlImport:
    xml_path: Path
    timeline_name: str
    occurrences: tuple[EdlShotOccurrence, ...]
    unrecognized_clip_names: tuple[str, ...]


@dataclass(frozen=True)
class EdlComparisonSummary:
    sequence: str
    first_order: int
    last_order: int
    active_count: int
    inactive_count: int
    return_cut_count: int
    missing_shot_names: tuple[str, ...]


@dataclass(frozen=True)
class SequenceManifestExportResult:
    output_path: Path
    previous_output_backup_path: Path | None


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


def format_shot_frame_range(
    start_frame: int | None,
    end_frame: int | None,
) -> str:
    if start_frame is None and end_frame is None:
        return EDL_EMPTY_DISPLAY
    start_display = EDL_EMPTY_DISPLAY if start_frame is None else str(start_frame)
    end_display = EDL_EMPTY_DISPLAY if end_frame is None else str(end_frame)
    return f"{start_display} - {end_display}"


def format_edl_frame_ranges(
    frame_ranges: tuple[tuple[int, int], ...],
) -> str:
    if not frame_ranges:
        return EDL_EMPTY_DISPLAY
    return "; ".join(
        format_shot_frame_range(start_frame, end_frame)
        for start_frame, end_frame in frame_ranges
    )


def calculate_edl_proposed_range(
    edl_frame_ranges: tuple[tuple[int, int], ...],
    original_start_frame: int | None,
    original_end_frame: int | None,
    handle_frame_count: int = EDL_FRAME_HANDLE_COUNT,
) -> tuple[int, int] | None:
    if (
        not edl_frame_ranges
        or original_start_frame is None
        or original_end_frame is None
    ):
        return None

    edl_start_frame = min(start_frame for start_frame, _ in edl_frame_ranges)
    edl_end_frame = max(end_frame for _, end_frame in edl_frame_ranges)
    proposed_start_frame = max(
        original_start_frame,
        edl_start_frame - handle_frame_count,
    )
    proposed_end_frame = min(
        original_end_frame,
        edl_end_frame + handle_frame_count,
    )
    if proposed_start_frame > proposed_end_frame:
        return None
    return proposed_start_frame, proposed_end_frame


def refresh_edl_proposed_range(shot_row: ShotRow) -> None:
    if (
        shot_row.keep_range
        and shot_row.start_frame is not None
        and shot_row.end_frame is not None
    ):
        shot_row.edl_proposed_range = (
            shot_row.start_frame,
            shot_row.end_frame,
        )
        return
    shot_row.edl_proposed_range = calculate_edl_proposed_range(
        shot_row.edl_frame_ranges,
        shot_row.start_frame,
        shot_row.end_frame,
    )


def calculate_estimated_frames_cut(shot_rows: list[ShotRow]) -> int:
    estimated_frames_cut = 0
    for shot_row in shot_rows:
        if (
            shot_row.start_frame is None
            or shot_row.end_frame is None
            or shot_row.edl_proposed_range is None
        ):
            continue
        original_frame_count = max(
            0,
            shot_row.end_frame - shot_row.start_frame + 1,
        )
        proposed_start_frame, proposed_end_frame = shot_row.edl_proposed_range
        proposed_frame_count = max(
            0,
            proposed_end_frame - proposed_start_frame + 1,
        )
        estimated_frames_cut += max(
            0,
            original_frame_count - proposed_frame_count,
        )
    return estimated_frames_cut


def _xml_local_name(tag: str) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _xml_children(element: ET.Element | None, name: str) -> list[ET.Element]:
    if element is None:
        return []
    return [child for child in element if _xml_local_name(child.tag) == name]


def _xml_child(element: ET.Element | None, name: str) -> ET.Element | None:
    children = _xml_children(element, name)
    return children[0] if children else None


def _xml_text(element: ET.Element | None, name: str, default: str = "") -> str:
    child = _xml_child(element, name)
    if child is None or child.text is None:
        return default
    return str(child.text).strip()


def _extract_edl_shot_name(candidates: list[str]) -> tuple[str, str, str] | None:
    for candidate in candidates:
        source_name = str(candidate or "").strip()
        if not source_name:
            continue
        match = EDL_SHOT_NAME_RE.search(source_name)
        if not match:
            continue
        sequence_name = match.group("sequence").upper()
        shot_name = f"{sequence_name}_000_{match.group('shot')}"
        return sequence_name, shot_name, source_name
    return None


def _read_edl_track(
    track: ET.Element,
) -> tuple[
    list[tuple[int, int, int, int | None, int | None, str, str, str]],
    list[str],
]:
    recognized: list[
        tuple[int, int, int, int | None, int | None, str, str, str]
    ] = []
    unrecognized: list[str] = []

    for clip_index, clip_item in enumerate(_xml_children(track, "clipitem")):
        enabled_text = _xml_text(clip_item, "enabled", "TRUE").upper()
        if enabled_text in ("FALSE", "0", "NO"):
            continue

        try:
            timeline_start = int(_xml_text(clip_item, "start"))
            timeline_end = int(_xml_text(clip_item, "end"))
        except (TypeError, ValueError):
            continue

        source_in = _coerce_optional_int(_xml_text(clip_item, "in"))
        source_out = _coerce_optional_int(_xml_text(clip_item, "out"))

        file_node = _xml_child(clip_item, "file")
        candidates = [
            _xml_text(clip_item, "name"),
            _xml_text(file_node, "name"),
            _xml_text(file_node, "pathurl"),
        ]
        parsed_shot = _extract_edl_shot_name(candidates)
        if parsed_shot is None:
            display_name = next((value for value in candidates if value), "<unnamed clip>")
            unrecognized.append(display_name)
            continue

        sequence_name, shot_name, source_name = parsed_shot
        recognized.append(
            (
                timeline_start,
                timeline_end,
                clip_index,
                source_in,
                source_out,
                sequence_name,
                shot_name,
                source_name,
            )
        )

    return recognized, unrecognized


def parse_resolve_edl_xml(xml_path: str | Path) -> ResolveEdlImport:
    """Parse the picture track with the most recognizable Unreal shot clips."""
    resolved_xml_path = _as_path(xml_path)
    if not resolved_xml_path.is_file():
        raise FileNotFoundError(f"Resolve XML file does not exist: {resolved_xml_path}")

    try:
        xml_root = ET.parse(resolved_xml_path).getroot()
    except ET.ParseError as error:
        raise ValueError(f"Could not parse Resolve XML: {error}") from error

    sequence_nodes = [
        element
        for element in xml_root.iter()
        if _xml_local_name(element.tag) == "sequence"
    ]
    if not sequence_nodes:
        raise ValueError("The XML does not contain an editable sequence.")

    track_candidates: list[
        tuple[
            int,
            int,
            str,
            list[
                tuple[int, int, int, int | None, int | None, str, str, str]
            ],
            list[str],
        ]
    ] = []
    for sequence_index, sequence_node in enumerate(sequence_nodes):
        timeline_name = _xml_text(sequence_node, "name", f"Sequence {sequence_index + 1}")
        video_node = _xml_child(_xml_child(sequence_node, "media"), "video")
        for track_index, track in enumerate(_xml_children(video_node, "track")):
            recognized, unrecognized = _read_edl_track(track)
            track_candidates.append(
                (
                    sequence_index,
                    track_index,
                    timeline_name,
                    recognized,
                    unrecognized,
                )
            )

    usable_tracks = [candidate for candidate in track_candidates if candidate[3]]
    if not usable_tracks:
        raise ValueError(
            "No enabled video clips containing names like TIC_000_0825 "
            "were found in the XML."
        )

    selected_track = max(
        usable_tracks,
        key=lambda candidate: (
            len(candidate[3]),
            -candidate[0],
            -candidate[1],
        ),
    )
    _sequence_index, _track_index, timeline_name, raw_occurrences, unrecognized = (
        selected_track
    )

    ordered_occurrences = sorted(
        raw_occurrences,
        key=lambda occurrence: (occurrence[0], occurrence[1], occurrence[2]),
    )
    occurrences = tuple(
        EdlShotOccurrence(
            edit_index=edit_index,
            timeline_start=timeline_start,
            timeline_end=timeline_end,
            source_in=source_in,
            source_out=source_out,
            sequence=sequence_name,
            shot_name=shot_name,
            source_name=source_name,
        )
        for edit_index, (
            timeline_start,
            timeline_end,
            _clip_index,
            source_in,
            source_out,
            sequence_name,
            shot_name,
            source_name,
        ) in enumerate(ordered_occurrences, start=1)
    )

    return ResolveEdlImport(
        xml_path=resolved_xml_path,
        timeline_name=timeline_name,
        occurrences=occurrences,
        unrecognized_clip_names=tuple(unrecognized),
    )


def clear_edl_comparison(shot_rows: list[ShotRow]) -> None:
    for shot_row in shot_rows:
        shot_row.edl_order = None
        shot_row.edl_is_active = None
        shot_row.edl_frame_ranges = ()
        shot_row.edl_proposed_range = None


def apply_edl_sequence_comparison(
    shot_rows: list[ShotRow],
    edl_import: ResolveEdlImport,
    sequence_name: str,
    first_order: int,
) -> EdlComparisonSummary:
    """Apply a preview-only per-sequence EDL proposal to loaded shot rows."""
    clean_sequence_name = str(sequence_name or "").strip().upper()
    if not clean_sequence_name or clean_sequence_name == ALL_SEQUENCES_LABEL.upper():
        raise ValueError("Choose one sequence before building an EDL comparison.")
    if first_order < 0:
        raise ValueError("First Shot Number in Sequence must be 0 or greater.")

    sequence_rows = [
        shot_row
        for shot_row in shot_rows
        if shot_row.sequence.upper() == clean_sequence_name
    ]
    if not sequence_rows:
        raise ValueError(f"No manifest shots are loaded for sequence {clean_sequence_name}.")

    rows_by_name: dict[str, ShotRow] = {}
    for shot_row in sequence_rows:
        if shot_row.shot_name in rows_by_name:
            raise ValueError(
                f"The manifest contains more than one row for {shot_row.shot_name}."
            )
        rows_by_name[shot_row.shot_name] = shot_row

    sequence_occurrences = [
        occurrence
        for occurrence in edl_import.occurrences
        if occurrence.sequence == clean_sequence_name
    ]
    ordered_edl_shot_names: list[str] = []
    seen_edl_shot_names: set[str] = set()
    occurrences_by_shot_name: dict[str, list[EdlShotOccurrence]] = {}
    for occurrence in sequence_occurrences:
        occurrences_by_shot_name.setdefault(occurrence.shot_name, []).append(
            occurrence
        )
        if occurrence.shot_name in seen_edl_shot_names:
            continue
        seen_edl_shot_names.add(occurrence.shot_name)
        ordered_edl_shot_names.append(occurrence.shot_name)

    clear_edl_comparison(sequence_rows)
    for order_offset, shot_name in enumerate(ordered_edl_shot_names):
        shot_row = rows_by_name.get(shot_name)
        if shot_row is None:
            continue
        shot_row.edl_is_active = True
        shot_row.edl_order = first_order + order_offset
        edl_frame_ranges: list[tuple[int, int]] = []
        if shot_row.start_frame is not None:
            for occurrence in occurrences_by_shot_name.get(shot_name, []):
                if occurrence.source_in is None or occurrence.source_out is None:
                    continue
                # Resolve XMEML source-out frames are exclusive. Manifest ranges
                # are inclusive, so subtract one when displaying the used range.
                edl_start_frame = shot_row.start_frame + occurrence.source_in
                edl_end_frame = shot_row.start_frame + occurrence.source_out - 1
                frame_range = (edl_start_frame, edl_end_frame)
                if edl_end_frame >= edl_start_frame and frame_range not in edl_frame_ranges:
                    edl_frame_ranges.append(frame_range)
        shot_row.edl_frame_ranges = tuple(edl_frame_ranges)

    inactive_rows = sorted(
        (
            shot_row
            for shot_row in sequence_rows
            if shot_row.shot_name not in seen_edl_shot_names
        ),
        key=lambda row: (
            row.order,
            row.section_number,
            row.shot_number,
            row.shot_name.lower(),
        ),
    )
    inactive_first_order = first_order + len(ordered_edl_shot_names)
    for order_offset, shot_row in enumerate(inactive_rows):
        shot_row.edl_is_active = False
        shot_row.edl_order = inactive_first_order + order_offset

    for shot_row in sequence_rows:
        refresh_edl_proposed_range(shot_row)

    missing_shot_names = tuple(
        shot_name
        for shot_name in ordered_edl_shot_names
        if shot_name not in rows_by_name
    )
    proposed_orders = [
        shot_row.edl_order
        for shot_row in sequence_rows
        if shot_row.edl_order is not None
    ]
    if len(proposed_orders) != len(set(proposed_orders)):
        raise ValueError("The EDL proposal produced duplicate shot order numbers.")

    last_order = max(proposed_orders, default=first_order)
    return EdlComparisonSummary(
        sequence=clean_sequence_name,
        first_order=first_order,
        last_order=last_order,
        active_count=sum(
            1 for shot_row in sequence_rows if shot_row.edl_is_active is True
        ),
        inactive_count=sum(
            1 for shot_row in sequence_rows if shot_row.edl_is_active is False
        ),
        return_cut_count=len(sequence_occurrences) - len(ordered_edl_shot_names),
        missing_shot_names=missing_shot_names,
    )


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

        destination_file_name = f"{shot_row.order:03d}_{latest_mp4_path.name}"
        dest_path = _build_unique_dest_path(
            dump_folder,
            destination_file_name,
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


def _group_manifest_rows(shot_rows: list[ShotRow]) -> dict[Path, list[ShotRow]]:
    rows_by_manifest: dict[Path, list[ShotRow]] = {}
    for shot_row in shot_rows:
        if shot_row.manifest_path is None:
            continue
        rows_by_manifest.setdefault(shot_row.manifest_path, []).append(shot_row)
    return rows_by_manifest


def save_order_updates_to_manifests(shot_rows: list[ShotRow]) -> int:
    rows_by_manifest = _group_manifest_rows(shot_rows)
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

    return len(saved_paths)


def _set_shot_active_fields(shot_data: dict, is_active: bool) -> bool:
    changed = False
    active_value = 1 if is_active else 0

    if _coerce_bool(shot_data.get("is_active"), default=False) != is_active or "is_active" not in shot_data:
        shot_data["is_active"] = is_active
        changed = True

    if _coerce_optional_int(shot_data.get("is_active_value")) != active_value or "is_active_value" not in shot_data:
        shot_data["is_active_value"] = active_value
        changed = True

    return changed


def build_updated_sequence_manifest(
    manifest_data: dict,
    shot_rows: list[ShotRow],
    expected_sequence_name: str,
    *,
    update_order: bool = True,
    update_active: bool = True,
    update_frame_range: bool = True,
) -> dict:
    """Return a manifest copy containing only the selected EDL proposal changes."""
    sequence_name = str(expected_sequence_name or "").strip().upper()
    manifest_sequence_name = str(
        manifest_data.get("sequence_name") or sequence_name
    ).strip().upper()
    if manifest_sequence_name != sequence_name:
        raise ValueError(
            f"Manifest sequence is {manifest_sequence_name!r}, expected {sequence_name!r}."
        )

    sequence_rows = [
        shot_row
        for shot_row in shot_rows
        if shot_row.sequence.upper() == sequence_name
    ]
    if not sequence_rows:
        raise ValueError(f"No shot rows are loaded for sequence {sequence_name}.")
    if update_order and any(
        shot_row.edl_order is None
        for shot_row in sequence_rows
    ):
        raise ValueError("Import and review Resolve EDL order values before exporting JSON.")
    if update_active and any(
        shot_row.edl_is_active is None
        for shot_row in sequence_rows
    ):
        raise ValueError("Import and review Resolve EDL active values before exporting JSON.")

    if update_order:
        proposed_orders = [int(shot_row.edl_order) for shot_row in sequence_rows]
        if len(proposed_orders) != len(set(proposed_orders)):
            raise ValueError("Proposed EDL order numbers must be unique.")

    updated_manifest = deepcopy(manifest_data)
    shots = updated_manifest.get("shots")
    if not isinstance(shots, list):
        raise ValueError("Manifest 'shots' field must be a list.")

    rows_by_name = {shot_row.shot_name: shot_row for shot_row in sequence_rows}
    matched_shot_names: set[str] = set()
    for shot_data in shots:
        if not isinstance(shot_data, dict):
            continue
        shot_name = str(shot_data.get("shot_name") or "").strip()
        shot_row = rows_by_name.get(shot_name)
        if shot_row is None:
            continue
        if shot_name in matched_shot_names:
            raise ValueError(f"Manifest contains duplicate shot row: {shot_name}")
        matched_shot_names.add(shot_name)
        if update_order:
            shot_data["order"] = int(shot_row.edl_order)
        if update_active:
            _set_shot_active_fields(shot_data, bool(shot_row.edl_is_active))
        if update_frame_range and shot_row.edl_proposed_range is not None:
            shot_data["start_frame"] = shot_row.edl_proposed_range[0]
            shot_data["end_frame"] = shot_row.edl_proposed_range[1]

    missing_manifest_rows = sorted(set(rows_by_name) - matched_shot_names)
    if missing_manifest_rows:
        raise ValueError(
            f"Could not find loaded shot rows in the manifest: {missing_manifest_rows}"
        )

    if update_active:
        active_count = sum(
            1
            for shot_data in shots
            if isinstance(shot_data, dict)
            and _coerce_bool(
                shot_data.get("is_active", shot_data.get("is_active_value")),
                default=False,
            )
        )
        updated_manifest["shot_count"] = len(shots)
        updated_manifest["active_shot_count"] = active_count
        updated_manifest["inactive_shot_count"] = len(shots) - active_count
    return updated_manifest


def _write_json_file_atomically(json_path: Path, data: dict) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=json_path.parent,
            prefix=f".{json_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            json.dump(data, temporary_file, indent=4, ensure_ascii=False)
            temporary_file.write("\n")
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, json_path)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def get_updated_sequence_manifest_path(manifest_path: str | Path) -> Path:
    resolved_manifest_path = _as_path(manifest_path)
    return resolved_manifest_path.with_name(
        f"{resolved_manifest_path.stem}_updated{resolved_manifest_path.suffix}"
    )


def export_edl_updates_to_sequence_manifest(
    manifest_path: str | Path,
    shot_rows: list[ShotRow],
    sequence_name: str,
    *,
    update_order: bool = True,
    update_active: bool = True,
    update_frame_range: bool = True,
) -> SequenceManifestExportResult:
    """Overwrite the stable *_updated.json without modifying the Unreal export."""
    resolved_manifest_path = _as_path(manifest_path)
    if not resolved_manifest_path.is_file():
        raise FileNotFoundError(
            f"Sequence manifest does not exist: {resolved_manifest_path}"
        )

    manifest_data = _read_json_file(resolved_manifest_path)
    updated_manifest = build_updated_sequence_manifest(
        manifest_data,
        shot_rows,
        sequence_name,
        update_order=update_order,
        update_active=update_active,
        update_frame_range=update_frame_range,
    )
    output_path = get_updated_sequence_manifest_path(resolved_manifest_path)
    _write_json_file_atomically(output_path, updated_manifest)
    return SequenceManifestExportResult(
        output_path=output_path,
        previous_output_backup_path=None,
    )


def save_active_updates_to_manifests(shot_rows: list[ShotRow]) -> int:
    rows_by_manifest = _group_manifest_rows(shot_rows)
    saved_paths: set[Path] = set()

    for manifest_path, manifest_rows in rows_by_manifest.items():
        manifest_data = _read_json_file(manifest_path)
        shots = manifest_data.get("shots") or []
        if not isinstance(shots, list):
            raise ValueError(f"Manifest 'shots' field must be a list: {manifest_path}")

        active_by_shot_name = {shot_row.shot_name: shot_row.is_active for shot_row in manifest_rows}
        changed = False

        for shot_data in shots:
            if not isinstance(shot_data, dict):
                continue
            shot_name = str(shot_data.get("shot_name") or "").strip()
            if shot_name not in active_by_shot_name:
                continue
            if _set_shot_active_fields(shot_data, active_by_shot_name[shot_name]):
                changed = True

        if changed:
            _write_json_file(manifest_path, manifest_data)
            saved_paths.add(manifest_path)

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
    try:
        manifest = _read_json_file(manifest_path)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise SequenceManifestError(manifest_path) from error
    shots = manifest.get("shots")
    if not isinstance(shots, list):
        raise SequenceManifestError(manifest_path)
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


def _shot_rows_from_sequence_folder(
    sequence_folder: Path,
    *,
    active_only: bool = False,
) -> list[ShotRow]:
    manifest_path = _get_sequence_manifest_path(sequence_folder)
    if manifest_path.is_file():
        manifest_rows = _shot_rows_from_sequence_manifest(sequence_folder)
        if active_only:
            return [shot_row for shot_row in manifest_rows if shot_row.is_active]
        if manifest_rows:
            return manifest_rows
    return _fallback_shot_rows_from_sequence_folder(sequence_folder)


def find_shot_folders(
    show_root: str | Path,
    selected_sequence: str,
    *,
    active_only: bool = False,
) -> list[ShotRow]:
    show_path = _as_path(show_root)
    if selected_sequence == ALL_SEQUENCES_LABEL:
        sequence_folders = find_sequence_folders(show_path)
    else:
        sequence_path = show_path / "sequences" / selected_sequence
        sequence_folders = [sequence_path] if _is_sequence_folder(sequence_path) else []
    shot_rows = []
    for sequence_folder in sequence_folders:
        shot_rows.extend(
            _shot_rows_from_sequence_folder(
                sequence_folder,
                active_only=active_only,
            )
        )
    return sorted(shot_rows, key=lambda row: (row.order, row.sequence.lower(), row.section_number, row.shot_number, row.shot_name.lower()))


class ShotManagerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Shot Manager")
        self.root.geometry("1480x800")
        self.root.minsize(1100, 620)
        self.dropbox_root_var = tk.StringVar()
        self.show_select_var = tk.StringVar()
        self.sequence_select_var = tk.StringVar(value=ALL_SEQUENCES_LABEL)
        self.first_shot_number_var = tk.StringVar(value="001")
        self.edl_source_var = tk.StringVar(value="No Resolve XML loaded.")
        self.update_shot_order_var = tk.BooleanVar(value=True)
        self.update_shot_active_var = tk.BooleanVar(value=True)
        self.update_frame_range_var = tk.BooleanVar(value=True)
        self.estimated_frames_cut_var = tk.StringVar(value="0")
        self.status_var = tk.StringVar(value="Choose a Dropbox folder to begin.")
        self.saved_show_name = ""
        self.saved_sequence_name = ""
        self.show_folders_by_name: dict[str, Path] = {}
        self.show_manifests_by_name: dict[str, Path | None] = {}
        self.sequence_folders_by_name: dict[str, Path] = {}
        self.show_manifest: Path | None = None
        self.current_shot_rows: list[ShotRow] = []
        self.shot_rows_by_item_id: dict[str, ShotRow] = {}
        self.move_buttons_by_item_id: dict[str, tuple[ttk.Button, ttk.Button]] = {}
        self.move_button_refresh_job: str | None = None
        self.edl_import: ResolveEdlImport | None = None
        self.edl_comparison_summary: EdlComparisonSummary | None = None
        self.shot_sort_column = "order"
        self.shot_sort_reverse = False
        self._build_ui()
        self._load_saved_local_state()

    def run(self) -> None:
        self.root.mainloop()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        style = ttk.Style(self.root)
        style.configure("ShotManager.Treeview", rowheight=SHOT_TREE_ROW_HEIGHT)
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
        self.shots_tree = ttk.Treeview(listing_frame, columns=columns, show="headings", selectmode="browse", style="ShotManager.Treeview")
        self._refresh_column_headings()
        self.shots_tree.column("move", width=78, minwidth=70, stretch=False, anchor="center")
        self.shots_tree.column("order", width=105, minwidth=95, stretch=False, anchor="center")
        self.shots_tree.column("edl_order", width=90, minwidth=80, stretch=False, anchor="center")
        self.shots_tree.column("is_active", width=110, minwidth=105, stretch=False, anchor="center")
        self.shots_tree.column("edl_is_active", width=95, minwidth=90, stretch=False, anchor="center")
        self.shots_tree.column("sequence", width=100, minwidth=80, stretch=False, anchor="center")
        self.shots_tree.column("shot", width=160, minwidth=130, stretch=False, anchor="center")
        self.shots_tree.column("frame_range", width=125, minwidth=110, stretch=False, anchor="center")
        self.shots_tree.column("keep_range", width=90, minwidth=80, stretch=False, anchor="center")
        self.shots_tree.column("edl_frame_range", width=235, minwidth=135, stretch=False, anchor="center")
        self.shots_tree.column("edl_proposed_range", width=155, minwidth=135, stretch=False, anchor="center")
        self.shots_tree.column("path", width=650, minwidth=280, stretch=True)
        self.shots_tree.bind("<Button-1>", self._on_shots_tree_click)
        self.shots_tree.bind("<Configure>", self._on_tree_configure, add="+")
        self.shots_tree.bind("<MouseWheel>", self._on_tree_mousewheel, add="+")
        self.shots_tree.bind("<Button-4>", self._on_tree_mousewheel, add="+")
        self.shots_tree.bind("<Button-5>", self._on_tree_mousewheel, add="+")
        self.shots_tree.grid(row=0, column=0, sticky="nsew")
        y_scroll = ttk.Scrollbar(listing_frame, orient="vertical", command=self._on_tree_y_scroll)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(listing_frame, orient="horizontal", command=self._on_tree_x_scroll)
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.shots_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        export_options_frame = ttk.Frame(outer)
        export_options_frame.pack(fill="x", pady=(8, 0))
        ttk.Checkbutton(
            export_options_frame,
            text="Update Shot Order",
            variable=self.update_shot_order_var,
        ).pack(side="left")
        ttk.Checkbutton(
            export_options_frame,
            text="Update Shot Active",
            variable=self.update_shot_active_var,
        ).pack(side="left", padx=(18, 0))
        ttk.Checkbutton(
            export_options_frame,
            text="Update Frame Range",
            variable=self.update_frame_range_var,
        ).pack(side="left", padx=(18, 0))
        ttk.Label(
            export_options_frame,
            text="Estimated Frames Cut",
        ).pack(side="left", padx=(28, 6))
        ttk.Label(
            export_options_frame,
            textvariable=self.estimated_frames_cut_var,
        ).pack(side="left")

        edl_frame = ttk.LabelFrame(
            outer,
            text="DaVinci Resolve EDL Comparison",
            padding=8,
        )
        edl_frame.pack(fill="x", pady=(8, 0))
        edl_frame.columnconfigure(5, weight=1)
        ttk.Label(edl_frame, text="First Shot Number in Sequence").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 8),
        )
        self.first_shot_number_entry = ttk.Entry(
            edl_frame,
            textvariable=self.first_shot_number_var,
            width=8,
        )
        self.first_shot_number_entry.grid(row=0, column=1, sticky="w", padx=(0, 12))
        self.first_shot_number_entry.bind(
            "<Return>",
            self._on_first_shot_number_committed,
        )
        self.first_shot_number_entry.bind(
            "<FocusOut>",
            self._on_first_shot_number_committed,
        )
        self.import_edl_button = ttk.Button(
            edl_frame,
            text="Import DaVinci Resolve EDL",
            command=self._import_resolve_edl,
        )
        self.import_edl_button.grid(row=0, column=2, padx=(0, 8))
        self.clear_edl_button = ttk.Button(
            edl_frame,
            text="Clear EDL Preview",
            command=self._clear_edl_preview,
        )
        self.clear_edl_button.grid(row=0, column=3, padx=(0, 8))
        self.export_sequence_json_button = ttk.Button(
            edl_frame,
            text="Export Sequence JSON",
            command=self._export_sequence_json,
        )
        self.export_sequence_json_button.grid(row=0, column=4, padx=(0, 12))
        ttk.Label(
            edl_frame,
            textvariable=self.edl_source_var,
            anchor="w",
        ).grid(row=0, column=5, sticky="ew")

        actions_frame = ttk.Frame(outer)
        actions_frame.pack(fill="x", pady=(8, 0))
        ttk.Button(actions_frame, text="Gather Show MP4s", command=self._gather_show_mp4s).pack(side="right")
        ttk.Label(outer, textvariable=self.status_var, anchor="w").pack(fill="x", pady=(8, 0))
        self._update_edl_control_states()

    def _get_single_selected_sequence(self) -> str:
        selected_sequence = self.sequence_select_var.get().strip().upper()
        if not selected_sequence or selected_sequence == ALL_SEQUENCES_LABEL.upper():
            return ""
        return selected_sequence

    def _suggest_first_shot_number(self) -> str:
        sequence_block_orders = [
            shot_row.order
            for shot_row in self.current_shot_rows
            if 0 < shot_row.order < 999
        ]
        all_orders = [
            shot_row.order
            for shot_row in self.current_shot_rows
            if shot_row.order >= 0
        ]
        suggested_order = min(sequence_block_orders or all_orders or [1])
        return f"{suggested_order:03d}"

    def _parse_first_shot_number(self) -> int:
        raw_value = self.first_shot_number_var.get().strip()
        if not re.fullmatch(r"\d+", raw_value):
            raise ValueError(
                "First Shot Number in Sequence must contain only whole numbers."
            )
        first_order = int(raw_value)
        if first_order < 0:
            raise ValueError("First Shot Number in Sequence must be 0 or greater.")
        return first_order

    def _update_edl_control_states(self) -> None:
        single_sequence_selected = bool(self._get_single_selected_sequence())
        has_manifest_rows = bool(self.current_shot_rows) and all(
            shot_row.manifest_path is not None
            for shot_row in self.current_shot_rows
        )
        can_import = single_sequence_selected and has_manifest_rows
        can_export = (
            can_import
            and self.edl_comparison_summary is not None
            and not self.edl_comparison_summary.missing_shot_names
        )
        self.first_shot_number_entry.configure(
            state="normal" if can_import else "disabled"
        )
        self.import_edl_button.configure(
            state="normal" if can_import else "disabled"
        )
        self.clear_edl_button.configure(
            state="normal" if self.edl_import is not None else "disabled"
        )
        self.export_sequence_json_button.configure(
            state="normal" if can_export else "disabled"
        )

    def _clear_edl_preview(self, set_status: bool = True) -> None:
        clear_edl_comparison(self.current_shot_rows)
        self.edl_import = None
        self.edl_comparison_summary = None
        self.edl_source_var.set("No Resolve XML loaded.")
        self._render_shot_rows()
        self._update_edl_control_states()
        if set_status:
            self._set_status("Cleared the Resolve EDL comparison preview.")

    def _rebuild_edl_comparison(self) -> EdlComparisonSummary:
        if self.edl_import is None:
            raise ValueError("Import a DaVinci Resolve XML before building a preview.")
        sequence_name = self._get_single_selected_sequence()
        if not sequence_name:
            raise ValueError("Choose one sequence before importing a Resolve EDL.")
        first_order = self._parse_first_shot_number()
        self.first_shot_number_var.set(f"{first_order:03d}")
        summary = apply_edl_sequence_comparison(
            self.current_shot_rows,
            self.edl_import,
            sequence_name,
            first_order,
        )
        self.edl_comparison_summary = summary
        self.shot_sort_column = "edl_order"
        self.shot_sort_reverse = False
        self._refresh_column_headings()
        self._render_shot_rows()
        self._update_edl_control_states()
        return summary

    def _on_first_shot_number_committed(self, _event: tk.Event) -> None:
        if self.edl_import is None:
            return
        try:
            summary = self._rebuild_edl_comparison()
        except Exception as error:
            self._set_status(f"Could not update the EDL proposal: {error}")
            messagebox.showerror("Shot Manager Error", str(error))
            return
        self._set_status(
            f"Updated {summary.sequence} EDL proposal to orders "
            f"{summary.first_order:03d}–{summary.last_order:03d}."
        )

    def _import_resolve_edl(self) -> None:
        sequence_name = self._get_single_selected_sequence()
        if not sequence_name:
            messagebox.showwarning(
                "Shot Manager",
                "Choose one sequence before importing a DaVinci Resolve EDL.",
            )
            return
        if not self.current_shot_rows or any(
            shot_row.manifest_path is None
            for shot_row in self.current_shot_rows
        ):
            messagebox.showwarning(
                "Shot Manager",
                "Export the sequence manifest from Unreal and refresh Shot Manager first.",
            )
            return

        selected_xml = filedialog.askopenfilename(
            title="Import DaVinci Resolve EDL XML",
            filetypes=(
                ("DaVinci Resolve XML", "*.xml"),
                ("All Files", "*.*"),
            ),
        )
        if not selected_xml:
            return

        try:
            self.edl_import = parse_resolve_edl_xml(selected_xml)
            self.edl_source_var.set(
                f"{self.edl_import.xml_path.name} — {self.edl_import.timeline_name}"
            )
            summary = self._rebuild_edl_comparison()
        except Exception as error:
            clear_edl_comparison(self.current_shot_rows)
            self.edl_import = None
            self.edl_comparison_summary = None
            self.edl_source_var.set("No Resolve XML loaded.")
            self._render_shot_rows()
            self._update_edl_control_states()
            self._set_status(f"Error importing Resolve EDL: {error}")
            messagebox.showerror("Shot Manager Error", str(error))
            return

        warning_lines: list[str] = []
        if summary.missing_shot_names:
            warning_lines.append(
                "EDL shots missing from the sequence manifest:\n"
                + "\n".join(summary.missing_shot_names)
            )
        if self.edl_import.unrecognized_clip_names:
            warning_lines.append(
                f"Unrecognized enabled picture clips: "
                f"{len(self.edl_import.unrecognized_clip_names)}"
            )
        if summary.active_count == 0:
            warning_lines.append(
                f"No {sequence_name} shots were found in the selected XML."
            )

        self._set_status(
            f"Resolve EDL preview for {sequence_name}: "
            f"{summary.active_count} active, {summary.inactive_count} inactive, "
            f"{summary.return_cut_count} return cut(s), proposed orders "
            f"{summary.first_order:03d}–{summary.last_order:03d}."
        )
        if warning_lines:
            messagebox.showwarning(
                "Resolve EDL Import Warnings",
                "\n\n".join(warning_lines),
            )

    def _export_sequence_json(self) -> None:
        if self.edl_import is None or self.edl_comparison_summary is None:
            messagebox.showwarning(
                "Shot Manager",
                "Import and review a DaVinci Resolve EDL first.",
            )
            return

        try:
            summary = self._rebuild_edl_comparison()
        except Exception as error:
            self._set_status(f"Could not validate the EDL proposal: {error}")
            messagebox.showerror("Shot Manager Error", str(error))
            return

        if summary.missing_shot_names:
            messagebox.showerror(
                "Cannot Export Sequence JSON",
                "These EDL shots are missing from the sequence manifest:\n\n"
                + "\n".join(summary.missing_shot_names),
            )
            return

        manifest_paths = {
            shot_row.manifest_path
            for shot_row in self.current_shot_rows
            if shot_row.manifest_path is not None
        }
        if len(manifest_paths) != 1:
            messagebox.showerror(
                "Cannot Export Sequence JSON",
                "The selected sequence must be loaded from exactly one sequence manifest.",
            )
            return
        manifest_path = next(iter(manifest_paths))
        assert manifest_path is not None
        output_path = get_updated_sequence_manifest_path(manifest_path)
        update_order = bool(self.update_shot_order_var.get())
        update_active = bool(self.update_shot_active_var.get())
        update_frame_range = bool(self.update_frame_range_var.get())

        warning_text = ""
        if self.edl_import.unrecognized_clip_names:
            warning_text = (
                f"\n\nWarning: the picture track contains "
                f"{len(self.edl_import.unrecognized_clip_names)} unrecognized "
                "enabled clip(s)."
            )
        order_export_text = (
            f"Use EDL order {summary.first_order:03d}–{summary.last_order:03d}"
            if update_order
            else "Keep original JSON"
        )
        active_export_text = (
            "Use EDL active status" if update_active else "Keep original JSON"
        )
        frame_export_text = (
            "Use EDL Proposed Range"
            if update_frame_range
            else "Keep original JSON"
        )
        confirmed = messagebox.askyesno(
            "Export Sequence JSON",
            f"Write the reviewed EDL values here?\n\n{output_path}\n\n"
            f"Source manifest (will not be changed):\n{manifest_path}\n\n"
            f"Sequence: {summary.sequence}\n"
            f"Shot Order: {order_export_text}\n"
            f"Shot Active: {active_export_text}\n"
            f"Frame Range: {frame_export_text}"
            f"{warning_text}\n\n"
            "If the updated JSON already exists, it will be overwritten.",
        )
        if not confirmed:
            self._set_status("Sequence JSON export cancelled; no files were changed.")
            return

        try:
            export_result = export_edl_updates_to_sequence_manifest(
                manifest_path,
                self.current_shot_rows,
                summary.sequence,
                update_order=update_order,
                update_active=update_active,
                update_frame_range=update_frame_range,
            )
        except Exception as error:
            self._set_status(f"Error exporting sequence JSON: {error}")
            messagebox.showerror("Shot Manager Error", str(error))
            return

        for shot_row in self.current_shot_rows:
            if update_order and shot_row.edl_order is not None:
                shot_row.order = shot_row.edl_order
            if update_active and shot_row.edl_is_active is not None:
                shot_row.is_active = shot_row.edl_is_active
        self._render_shot_rows()
        self._set_status(
            f"Exported {summary.sequence} sequence JSON to "
            f"{export_result.output_path.name}; source manifest unchanged."
        )
        messagebox.showinfo(
            "Sequence JSON Exported",
            f"Updated export:\n{export_result.output_path}\n\n"
            f"Source unchanged:\n{manifest_path}",
        )

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
            self.edl_import = None
            self.edl_comparison_summary = None
            self.edl_source_var.set("No Resolve XML loaded.")
            self._render_shot_rows()
            self._update_edl_control_states()
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
            self.edl_import = None
            self.edl_comparison_summary = None
            self.edl_source_var.set("No Resolve XML loaded.")
            self._render_shot_rows()
            self._update_edl_control_states()
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
        clear_edl_comparison(self.current_shot_rows)
        self.edl_import = None
        self.edl_comparison_summary = None
        self.edl_source_var.set("No Resolve XML loaded.")
        show_path = self._get_selected_show_path()
        if show_path is None:
            self.current_shot_rows = []
            self._render_shot_rows()
            self._update_edl_control_states()
            return
        selected_sequence = self.sequence_select_var.get().strip() or ALL_SEQUENCES_LABEL
        try:
            self.current_shot_rows = find_shot_folders(show_path, selected_sequence)
        except Exception as error:
            self._set_status(f"Error: {error}")
            messagebox.showerror("Shot Manager Error", str(error))
            self._update_edl_control_states()
            return
        self.first_shot_number_var.set(self._suggest_first_shot_number())
        self._render_shot_rows()
        self._update_edl_control_states()
        manifest_status = "show manifest found" if self.show_manifest else "show manifest missing"
        sequence_manifest_count = len({row.manifest_path for row in self.current_shot_rows if row.manifest_path is not None})
        active_count = sum(1 for row in self.current_shot_rows if row.is_active)
        inactive_count = len(self.current_shot_rows) - active_count
        where = "across all sequences" if selected_sequence == ALL_SEQUENCES_LABEL else f"in sequence {selected_sequence}"
        self._set_status(f"Showing {len(self.current_shot_rows)} shot(s) {where}; {active_count} active, {inactive_count} inactive; loaded {sequence_manifest_count} sequence manifest(s); {manifest_status}.")

    def _on_tree_y_scroll(self, *args: object) -> None:
        self.shots_tree.yview(*args)
        self._schedule_move_buttons_refresh()

    def _on_tree_x_scroll(self, *args: object) -> None:
        self.shots_tree.xview(*args)
        self._schedule_move_buttons_refresh()

    def _on_tree_configure(self, _event: tk.Event) -> None:
        self._schedule_move_buttons_refresh()

    def _on_tree_mousewheel(self, _event: tk.Event) -> None:
        self._schedule_move_buttons_refresh()

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

    def _set_inactive_orders_to_999(self) -> None:
        if not self.current_shot_rows:
            messagebox.showinfo("Shot Manager", "There are no shots to update.")
            return

        inactive_rows = [shot_row for shot_row in self.current_shot_rows if not shot_row.is_active]
        if not inactive_rows:
            self._set_status("No inactive shots were found in the current shot listing.")
            return

        changed_rows = [shot_row for shot_row in inactive_rows if shot_row.order != 999]
        if not changed_rows:
            self._set_status("All inactive shots in the current shot listing already have order 999.")
            return

        original_orders = [(shot_row, shot_row.order) for shot_row in changed_rows]
        for shot_row in changed_rows:
            shot_row.order = 999

        try:
            saved_manifest_count = save_order_updates_to_manifests(changed_rows)
        except Exception as error:
            for shot_row, original_order in original_orders:
                shot_row.order = original_order
            self._render_shot_rows()
            self._set_status(f"Error saving inactive shot order values: {error}")
            messagebox.showerror("Shot Manager Error", str(error))
            return

        self.shot_sort_column = "order"
        self.shot_sort_reverse = False
        self._refresh_column_headings()
        self._render_shot_rows()
        self._set_status(
            f"Set {len(changed_rows)} inactive shot order value(s) to 999 and saved {saved_manifest_count} manifest file(s)."
        )

    def _move_shot_order(self, shot_row: ShotRow, direction: int) -> None:
        if any(row.order <= 0 for row in self.current_shot_rows):
            messagebox.showwarning(
                "Shot Manager",
                "Shots with order 0 cannot be moved. Update those order values first.",
            )
            self._set_status(
                "Update order 0 values before moving shots so every shot has a valid order number."
            )
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

        if column_key == "keep_range":
            self._toggle_keep_range(shot_row)
            return "break"

        if column_key != "is_active":
            return None

        self._toggle_shot_active_state(shot_row)
        return "break"

    def _toggle_keep_range(self, shot_row: ShotRow) -> None:
        shot_row.keep_range = not shot_row.keep_range
        refresh_edl_proposed_range(shot_row)
        self._render_shot_rows()
        state_text = "keeping the original frame range" if shot_row.keep_range else "using the EDL proposed frame range"
        self._set_status(f"{shot_row.shot_name} is now {state_text}.")

    def _toggle_shot_active_state(self, shot_row: ShotRow) -> None:
        if shot_row.manifest_path is None:
            self._set_status(f"Cannot save active state for {shot_row.shot_name}; no sequence manifest was loaded for this shot.")
            messagebox.showwarning(
                "Shot Manager",
                "This shot was loaded from a folder scan, not from a manifest. Export the shot manifests first, then refresh Shot Manager.",
            )
            return

        original_state = shot_row.is_active
        shot_row.is_active = not original_state

        try:
            saved_manifest_count = save_active_updates_to_manifests([shot_row])
        except Exception as error:
            shot_row.is_active = original_state
            self._render_shot_rows()
            self._set_status(f"Error saving active state for {shot_row.shot_name}: {error}")
            messagebox.showerror("Shot Manager Error", str(error))
            return

        self._render_shot_rows()
        state_text = "active" if shot_row.is_active else "inactive"
        self._set_status(f"Set {shot_row.shot_name} to {state_text} and saved {saved_manifest_count} manifest file(s).")

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
        self.estimated_frames_cut_var.set(
            f"{calculate_estimated_frames_cut(self.current_shot_rows):,}"
        )
        self._clear_shots()
        for shot_row in self._get_sorted_shot_rows():
            item_id = self.shots_tree.insert(
                "",
                "end",
                values=(
                    MOVE_DISPLAY,
                    shot_row.shot_name,
                    shot_row.order,
                    (
                        f"{shot_row.edl_order:03d}"
                        if shot_row.edl_order is not None
                        else EDL_EMPTY_DISPLAY
                    ),
                    _active_display(shot_row.is_active),
                    (
                        _active_display(shot_row.edl_is_active)
                        if shot_row.edl_is_active is not None
                        else EDL_EMPTY_DISPLAY
                    ),
                    format_shot_frame_range(
                        shot_row.start_frame,
                        shot_row.end_frame,
                    ),
                    _active_display(shot_row.keep_range),
                    format_edl_frame_ranges(shot_row.edl_frame_ranges),
                    (
                        format_shot_frame_range(*shot_row.edl_proposed_range)
                        if shot_row.edl_proposed_range is not None
                        else EDL_EMPTY_DISPLAY
                    ),
                    shot_row.sequence,
                    str(shot_row.shot_path),
                ),
            )
            self.shot_rows_by_item_id[item_id] = shot_row
        self._schedule_move_buttons_refresh()

    def _schedule_move_buttons_refresh(self) -> None:
        if self.move_button_refresh_job is not None:
            try:
                self.root.after_cancel(self.move_button_refresh_job)
            except Exception:
                pass
        self.move_button_refresh_job = self.root.after_idle(self._refresh_move_buttons)

    def _refresh_move_buttons(self) -> None:
        self.move_button_refresh_job = None
        self._destroy_move_buttons()
        column_id = self._get_tree_column_id("move")
        if not column_id:
            return

        for item_id in self.shots_tree.get_children():
            shot_row = self.shot_rows_by_item_id.get(item_id)
            if shot_row is None:
                continue
            cell_bounds = self.shots_tree.bbox(item_id, column_id)
            if not cell_bounds:
                continue

            cell_x, cell_y, cell_width, cell_height = cell_bounds
            button_height = max(cell_height + 6, 1)
            button_width = max((cell_width - 8) // 2, 20)
            button_y = cell_y - 3
            up_button = ttk.Button(
                self.shots_tree,
                text="▲",
                width=2,
                command=lambda row=shot_row: self._move_shot_order(row, -1),
            )
            down_button = ttk.Button(
                self.shots_tree,
                text="▼",
                width=2,
                command=lambda row=shot_row: self._move_shot_order(row, 1),
            )
            up_button.place(x=cell_x + 2, y=button_y, width=button_width, height=button_height)
            down_button.place(x=cell_x + 6 + button_width, y=button_y, width=button_width, height=button_height)
            self.move_buttons_by_item_id[item_id] = (up_button, down_button)

    def _destroy_move_buttons(self) -> None:
        for up_button, down_button in self.move_buttons_by_item_id.values():
            up_button.destroy()
            down_button.destroy()
        self.move_buttons_by_item_id = {}

    def _get_sorted_shot_rows(self) -> list[ShotRow]:
        def sort_key(shot_row: ShotRow) -> tuple:
            if self.shot_sort_column == "order":
                return (shot_row.order, shot_row.sequence.lower(), shot_row.section_number, shot_row.shot_number, shot_row.shot_name.lower())
            if self.shot_sort_column == "edl_order":
                return (
                    shot_row.edl_order is None,
                    shot_row.edl_order if shot_row.edl_order is not None else 0,
                    shot_row.order,
                    shot_row.shot_name.lower(),
                )
            if self.shot_sort_column == "is_active":
                return (shot_row.is_active, shot_row.order, shot_row.sequence.lower(), shot_row.shot_name.lower())
            if self.shot_sort_column == "edl_is_active":
                return (
                    shot_row.edl_is_active is None,
                    bool(shot_row.edl_is_active),
                    shot_row.edl_order if shot_row.edl_order is not None else 0,
                    shot_row.shot_name.lower(),
                )
            if self.shot_sort_column == "sequence":
                return (shot_row.sequence.lower(), shot_row.order, shot_row.section_number, shot_row.shot_number, shot_row.shot_name.lower())
            if self.shot_sort_column == "shot":
                return (shot_row.shot_name.lower(), shot_row.sequence.lower(), shot_row.section_number, shot_row.shot_number)
            if self.shot_sort_column == "frame_range":
                return (
                    shot_row.start_frame is None,
                    shot_row.start_frame if shot_row.start_frame is not None else 0,
                    shot_row.end_frame is None,
                    shot_row.end_frame if shot_row.end_frame is not None else 0,
                    shot_row.shot_name.lower(),
                )
            if self.shot_sort_column == "keep_range":
                return (
                    shot_row.keep_range,
                    shot_row.order,
                    shot_row.shot_name.lower(),
                )
            if self.shot_sort_column == "edl_frame_range":
                first_edl_range = (
                    shot_row.edl_frame_ranges[0]
                    if shot_row.edl_frame_ranges
                    else (0, 0)
                )
                return (
                    not shot_row.edl_frame_ranges,
                    first_edl_range[0],
                    first_edl_range[1],
                    shot_row.shot_name.lower(),
                )
            if self.shot_sort_column == "edl_proposed_range":
                proposed_range = shot_row.edl_proposed_range or (0, 0)
                return (
                    shot_row.edl_proposed_range is None,
                    proposed_range[0],
                    proposed_range[1],
                    shot_row.shot_name.lower(),
                )
            if self.shot_sort_column == "path":
                return (str(shot_row.shot_path).lower(),)
            return (shot_row.order, shot_row.sequence.lower())

        return sorted(self.current_shot_rows, key=sort_key, reverse=self.shot_sort_reverse)

    def _clear_shots(self) -> None:
        self._destroy_move_buttons()
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
