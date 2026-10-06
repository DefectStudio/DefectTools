import importlib
import os
from datetime import datetime

import unreal

import build_active_beauty_mp4_dump as active_beauty

# Reload the source helper module so Execute Python Script picks up edits
# without requiring an Unreal restart.
importlib.reload(active_beauty)


LOG_PREFIX = "[GatherShowActiveBeautyMp4s]"
SHOT_ORDER_PROPERTY = "ShotOrderNumber"
SUPPORTED_EXTENSION_TYPES = {"mp4", "mov"}
EXCLUDED_SEQUENCE_NAMES = {"ZZZ"}


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _normalize_extension_type(extension_type):
    """
    Normalize extension values such as "mp4", ".mp4", "MOV", or ".MOV".
    Only MP4 and MOV are supported.
    """
    normalized = str(extension_type or "").strip().lower().lstrip(".")

    if normalized not in SUPPORTED_EXTENSION_TYPES:
        supported_values = ", ".join(sorted(SUPPORTED_EXTENSION_TYPES))
        _log_error(
            f"Unsupported extension_type {extension_type!r}. "
            f"Expected one of: {supported_values}."
        )
        return ""

    return normalized


def _coerce_sequence_names(sequence_names):
    """
    Accepts an Unreal Blueprint string array, a Python list/tuple, or a single string.
    Returns sanitized, uppercase, de-duplicated sequence names.
    """
    if sequence_names is None:
        return []

    if isinstance(sequence_names, str):
        raw_values = [sequence_names]
    else:
        try:
            raw_values = list(sequence_names)
        except TypeError:
            raw_values = [sequence_names]

    clean_names = []
    seen = set()

    for raw_value in raw_values:
        clean_name = active_beauty._sanitize_sequence_name(raw_value)
        if not clean_name:
            _log_warning(f"Ignoring invalid sequence name: {raw_value!r}")
            continue

        if clean_name in EXCLUDED_SEQUENCE_NAMES:
            _log(f"Skipping excluded dev/test sequence: {clean_name}")
            continue

        if clean_name in seen:
            _log_warning(f"Ignoring duplicate sequence name: {clean_name}")
            continue

        seen.add(clean_name)
        clean_names.append(clean_name)

    return clean_names


def _normalize_show_sequences_output_root(output_root, sequence_names):
    """
    We want the show-level sequences output root:
        <show file server path>/sequences

    Usually OutputPath is already:
        <show file server path>/sequences

    This also protects against OutputPath being accidentally saved as:
        <show file server path>/sequences/<SEQ>
    or:
        <show file server path>/sequences/_output
    """
    normalized_root = os.path.normpath(output_root)
    base_name_upper = os.path.basename(normalized_root).upper()

    if base_name_upper == "_OUTPUT":
        show_sequences_root = os.path.dirname(normalized_root)
        _log_warning(
            f"OutputPath appears to point at a show _output folder. "
            f"Using parent as show sequences root: {show_sequences_root}"
        )
        return os.path.normpath(show_sequences_root)

    clean_sequence_names = set(_coerce_sequence_names(sequence_names))
    if base_name_upper in clean_sequence_names:
        show_sequences_root = os.path.dirname(normalized_root)
        _log_warning(
            f"OutputPath appears to point at sequence '{base_name_upper}'. "
            f"Using parent as show sequences root: {show_sequences_root}"
        )
        return os.path.normpath(show_sequences_root)

    return normalized_root


def _get_shot_order_number(shot_data_asset, shot_name):
    if not shot_data_asset:
        _log_warning(f"Shot data asset missing for '{shot_name}'. Using ShotOrderNumber 0.")
        return 0

    try:
        value = shot_data_asset.get_editor_property(SHOT_ORDER_PROPERTY)
    except Exception as exc:
        _log_warning(f"Shot data asset for '{shot_name}' did not expose {SHOT_ORDER_PROPERTY}. Using 0. Error: {exc}")
        return 0

    if isinstance(value, bool):
        _log_warning(f"Invalid {SHOT_ORDER_PROPERTY} for '{shot_name}': got bool {value!r}. Using 0.")
        return 0

    try:
        return int(str(value).strip())
    except Exception as exc:
        _log_warning(f"Invalid {SHOT_ORDER_PROPERTY} for '{shot_name}': {value!r}. Using 0. Error: {exc}")
        return 0


def _get_active_shot_rows(show_name, sequence_name):
    """
    Returns active shot rows from BP_ShotDataAsset data, including ShotOrderNumber.
    """
    sanitized_show_name = active_beauty._sanitize_show_name(show_name)
    sanitized_sequence_name = active_beauty._sanitize_sequence_name(sequence_name)

    if not sanitized_show_name:
        _log_error("Sanitized show_name is empty.")
        return []

    if not sanitized_sequence_name:
        _log_error("Sanitized sequence_name is empty.")
        return []

    sequence_folder_path = f"/Game/_{sanitized_show_name}/Sequences/{sanitized_sequence_name}"
    sequenceholder_path = f"{sequence_folder_path}/_sequenceholder"

    if not unreal.EditorAssetLibrary.does_directory_exist(sequence_folder_path):
        _log_error(f"Sequence folder does not exist: {sequence_folder_path}")
        return []

    if not unreal.EditorAssetLibrary.does_asset_exist(sequenceholder_path):
        _log_error(f"Missing _sequenceholder: {sequenceholder_path}")
        return []

    asset_paths = unreal.EditorAssetLibrary.list_assets(
        sequence_folder_path,
        recursive=False,
        include_folder=False,
    )

    active_rows = []

    for asset_path in asset_paths:
        asset_name = active_beauty._extract_asset_name(asset_path)

        if asset_name == "_sequenceholder":
            continue

        parsed = active_beauty._parse_shot_name(asset_name)
        if not parsed:
            continue

        if parsed["sequence_prefix"] != sanitized_sequence_name:
            continue

        asset_obj = unreal.EditorAssetLibrary.load_asset(asset_path)
        if not asset_obj or not isinstance(asset_obj, unreal.LevelSequence):
            continue

        shot_data_asset = active_beauty._load_data_asset_for_shot(sequence_folder_path, asset_name)
        is_active = active_beauty._get_is_active_for_shot(shot_data_asset)
        shot_order_number = _get_shot_order_number(shot_data_asset, asset_name)

        if is_active:
            active_rows.append(
                {
                    "sequence_name": sanitized_sequence_name,
                    "shot_name": asset_name,
                    "shot_number": parsed["shot_number"],
                    "shot_order_number": shot_order_number,
                }
            )

    active_rows.sort(
        key=lambda row: (
            row["shot_order_number"],
            row["sequence_name"].lower(),
            row["shot_number"],
            row["shot_name"].lower(),
        )
    )
    _log(f"{sanitized_sequence_name}: Found {len(active_rows)} active shot row(s): {active_rows}")
    return active_rows


def _is_beauty_file(file_name, extension_type):
    lower_name = file_name.lower()
    return lower_name.endswith(f".{extension_type}") and "beauty" in lower_name


def _find_latest_beauty_file(output_folder, shot_name, extension_type):
    if not os.path.isdir(output_folder):
        _log_warning(f"Output folder missing for active shot '{shot_name}': {output_folder}")
        return ""

    candidates = []

    try:
        for entry in os.scandir(output_folder):
            if not entry.is_file():
                continue

            if not _is_beauty_file(entry.name, extension_type):
                continue

            try:
                modified_time = entry.stat().st_mtime
            except Exception as exc:
                _log_warning(
                    f"Could not read modified time for '{entry.path}': {exc}"
                )
                continue

            candidates.append((modified_time, entry.path))
    except Exception as exc:
        _log_error(f"Failed scanning output folder '{output_folder}': {exc}")
        return ""

    if not candidates:
        return ""

    candidates.sort(key=lambda item: item[0], reverse=True)
    latest_path = os.path.normpath(candidates[0][1])
    _log(f"Latest beauty {extension_type} for '{shot_name}': {latest_path}")
    return latest_path


def _build_prefixed_file_name(file_name, shot_order_number):
    return f"{shot_order_number:03d}_{file_name}"


def _build_unique_dest_path(dump_folder, file_name, sequence_name, shot_name):
    """
    Keep the requested filename unless there is a collision in the show-level dump folder.
    Shot filenames should usually already be unique because they include the sequence prefix.
    """
    dest_path = os.path.join(dump_folder, file_name)
    if not os.path.exists(dest_path):
        return dest_path

    stem, ext = os.path.splitext(file_name)

    prefixed_name = f"{sequence_name}_{shot_name}_{file_name}"
    prefixed_path = os.path.join(dump_folder, prefixed_name)
    if not os.path.exists(prefixed_path):
        _log_warning(f"Destination exists. Using unique name: {prefixed_name}")
        return prefixed_path

    index = 2
    while True:
        numbered_name = f"{sequence_name}_{shot_name}_{stem}_{index}{ext}"
        numbered_path = os.path.join(dump_folder, numbered_name)
        if not os.path.exists(numbered_path):
            _log_warning(f"Destination exists. Using unique name: {numbered_name}")
            return numbered_path
        index += 1


def _open_folder_in_file_browser(folder_path):
    """
    Open the completed dump folder in Windows File Explorer.
    A failure to open Explorer is logged but does not fail the gather operation.
    """
    normalized_folder = os.path.normpath(folder_path)

    if not os.path.isdir(normalized_folder):
        _log_warning(f"Cannot open missing folder: {normalized_folder}")
        return False

    if os.name != "nt":
        _log_warning(
            f"Automatic folder opening is only configured for Windows: {normalized_folder}"
        )
        return False

    try:
        os.startfile(normalized_folder)
        _log(f"Opened folder in Windows File Explorer: {normalized_folder}")
        return True
    except Exception as exc:
        _log_warning(
            f"Could not open folder in Windows File Explorer '{normalized_folder}': {exc}"
        )
        return False


def run(sequence_names, extension_type="mp4"):
    """
    Build a timestamped review folder containing the latest beauty MP4 or MOV
    for all ACTIVE shots across multiple sequences, then open the completed
    folder in Windows File Explorer.

    Active state and order are read from each shot's BP_ShotDataAsset:
        IsActive
        ShotOrderNumber

    Input:
        sequence_names: array/list of sequence names, example ["BSH", "MNF", "ABC"]
        extension_type: string containing "mp4" or "mov". Defaults to "mp4".

    Output:
        Returns the created show-level dump folder path on success, or "" on failure.

    Example output:
        F:/Defect Dropbox/defect/s3bishop/sequences/_output/20260707_0906_heroMOVs
    """
    _log("----- run() called -----")
    _log(f"Raw sequence_names: {sequence_names!r}")
    _log(f"Raw extension_type: {extension_type!r}")

    clean_extension_type = _normalize_extension_type(extension_type)
    if not clean_extension_type:
        return ""

    clean_sequence_names = _coerce_sequence_names(sequence_names)
    if not clean_sequence_names:
        _log_error("sequence_names did not contain any valid sequence names.")
        return ""

    show_name = active_beauty._find_current_show_name()
    if not show_name:
        return ""

    output_root = active_beauty._get_saved_output_root()
    if not output_root:
        return ""

    show_sequences_output_root = _normalize_show_sequences_output_root(
        output_root,
        clean_sequence_names,
    )
    _log(f"Show sequences output root: {show_sequences_output_root}")

    show_dump_root = active_beauty._ensure_directory(
        os.path.join(show_sequences_output_root, "_output")
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    extension_label = clean_extension_type.upper()
    dump_folder = os.path.join(show_dump_root, f"{timestamp}_hero{extension_label}s")
    active_beauty._ensure_directory(dump_folder)

    _log(f"Show dump folder: {dump_folder}")

    copied_count = 0
    total_active_shot_count = 0
    sequences_with_no_active_shots = []
    missing_output_folders = []
    missing_beauty_files = []
    copied_files = []
    active_shot_rows = []

    for clean_sequence_name in clean_sequence_names:
        _log("--------------------------------------------------")
        _log(f"Gathering active shot rows from BP_ShotDataAsset assets for sequence: {clean_sequence_name}")

        sequence_output_root = active_beauty._normalize_sequence_output_root(
            show_sequences_output_root,
            clean_sequence_name,
        )
        sequence_output_root = os.path.normpath(sequence_output_root)
        _log(f"{clean_sequence_name}: Sequence output root: {sequence_output_root}")

        sequence_active_rows = _get_active_shot_rows(show_name, clean_sequence_name)
        total_active_shot_count += len(sequence_active_rows)

        if not sequence_active_rows:
            _log_warning(f"{clean_sequence_name}: No active shots found.")
            sequences_with_no_active_shots.append(clean_sequence_name)
            continue

        for shot_row in sequence_active_rows:
            shot_row["sequence_output_root"] = sequence_output_root
            active_shot_rows.append(shot_row)

    active_shot_rows.sort(
        key=lambda row: (
            row["shot_order_number"],
            row["sequence_name"].lower(),
            row["shot_number"],
            row["shot_name"].lower(),
        )
    )

    for shot_row in active_shot_rows:
        clean_sequence_name = shot_row["sequence_name"]
        shot_name = shot_row["shot_name"]
        shot_order_number = shot_row["shot_order_number"]
        sequence_output_root = shot_row["sequence_output_root"]

        shot_output_folder = active_beauty._build_shot_output_folder_path(
            sequence_output_root,
            shot_name,
        )
        shot_output_folder = os.path.normpath(shot_output_folder)

        if not os.path.isdir(shot_output_folder):
            _log_warning(
                f"Output folder missing for active shot '{shot_name}': "
                f"{shot_output_folder}"
            )
            missing_output_folders.append(f"{clean_sequence_name}:{shot_name}")
            continue

        latest_file_path = _find_latest_beauty_file(
            shot_output_folder,
            shot_name,
            clean_extension_type,
        )
        if not latest_file_path:
            _log_warning(
                f"No beauty {clean_extension_type} found for active shot '{shot_name}'."
            )
            missing_beauty_files.append(f"{clean_sequence_name}:{shot_name}")
            continue

        file_name = os.path.basename(latest_file_path)
        ordered_file_name = _build_prefixed_file_name(file_name, shot_order_number)
        dest_path = _build_unique_dest_path(
            dump_folder,
            ordered_file_name,
            clean_sequence_name,
            shot_name,
        )

        if active_beauty._safe_copy_file(latest_file_path, dest_path):
            copied_count += 1
            copied_files.append(os.path.basename(dest_path))

    _log("==================================================")
    _log(f"Show: {show_name}")
    _log(f"Sequences requested: {clean_sequence_names}")
    _log(f"Extension requested: {clean_extension_type}")
    _log(f"Total active shots found: {total_active_shot_count}")
    _log(f"{extension_label}s copied: {copied_count}")
    _log(f"Sequences with no active shots: {sequences_with_no_active_shots}")
    _log(f"Missing output folders: {missing_output_folders}")
    _log(f"Missing beauty {clean_extension_type}s: {missing_beauty_files}")
    _log(f"Copied files: {copied_files}")
    _log(f"Final show dump folder: {dump_folder}")
    _log("==================================================")

    if copied_count == 0:
        _log_warning(f"No beauty {clean_extension_type}s were copied.")
        return ""

    final_dump_folder = os.path.normpath(dump_folder)
    _open_folder_in_file_browser(final_dump_folder)
    return final_dump_folder
