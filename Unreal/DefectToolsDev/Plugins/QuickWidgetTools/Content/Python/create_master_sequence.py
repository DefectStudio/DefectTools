# -*- coding: utf-8 -*-
"""
create_master_sequence.py

Create a sequence-level review master containing every active shot for one
sequence, ordered by BP_ShotDataAsset.ShotOrderNumber.

Blueprint Execute Python Script example:

    import importlib
    import create_master_sequence

    importlib.invalidate_caches()
    importlib.reload(create_master_sequence)

    master_sequence_path = create_master_sequence.run(sequence_name)

Input:
    sequence_name: Sequence identifier, for example "JNG".

Returns:
    str: The created master Level Sequence asset path, or "" on failure.

Created asset example:
    /Game/_S3Bishop/Sequences/JNG/JNG_Master
"""

import os
import re

import unreal


LOG_PREFIX = "[CreateMasterSequence]"

SETTINGS_FILE_NAME = "QuickWidgetToolsSettings.ini"
SETTINGS_SECTION = "/Script/QuickWidgetTools.RenderToolSettings"
SHOW_NAME_SETTINGS_KEY = "show_name"

IS_ACTIVE_PROPERTY_CANDIDATES = (
    "IsActive",
    "is_active",
)
SHOT_ORDER_PROPERTY_CANDIDATES = (
    "ShotOrderNumber",
    "shot_order_number",
)

SHOT_NAME_PATTERN = re.compile(
    r"^(?P<sequence>[A-Za-z0-9]+)_(?P<unit>\d{3})_(?P<shot>\d{4,})$",
    re.IGNORECASE,
)

# Public module outputs for Blueprint Execute Python Script nodes.
master_sequence_asset = ""
active_shot_count = 0
added_shots = []


def _reset_outputs():
    global master_sequence_asset
    global active_shot_count
    global added_shots

    master_sequence_asset = ""
    active_shot_count = 0
    added_shots = []


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _sanitize_sequence_name(value):
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", str(value or ""))
    return cleaned.upper()


def _sanitize_show_name(value):
    return "".join(ch for ch in str(value or "") if ch.isalnum())


def _asset_package_path(asset_path):
    text = str(asset_path or "").strip().replace("\\", "/")
    if "." in text:
        text = text.split(".", 1)[0]
    return text.rstrip("/")


def _asset_name(asset_path):
    return _asset_package_path(asset_path).rsplit("/", 1)[-1]


def _find_config_dir(project_dir):
    candidates = (
        os.path.join(project_dir, "Saved", "Config", "WindowsEditor"),
        os.path.join(project_dir, "Saved", "Config", "Windows"),
        os.path.join(project_dir, "Saved", "Config"),
    )

    for folder in candidates:
        if os.path.isdir(folder):
            return folder

    return candidates[0]


def _get_section_value(text, section_name, key):
    section_header = f"[{section_name}]"
    in_section = False
    key_prefix = f"{key}="

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if line.startswith("[") and line.endswith("]"):
            in_section = line == section_header
            continue

        if in_section and line.startswith(key_prefix):
            return line[len(key_prefix):].strip()

    return ""


def _read_show_name_from_settings():
    settings_path = os.path.join(
        _find_config_dir(unreal.Paths.project_dir()),
        SETTINGS_FILE_NAME,
    )

    if not os.path.isfile(settings_path):
        return ""

    try:
        with open(settings_path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except Exception as exc:
        _log_warning(f"Could not read settings file '{settings_path}': {exc}")
        return ""

    return _sanitize_show_name(
        _get_section_value(
            text,
            SETTINGS_SECTION,
            SHOW_NAME_SETTINGS_KEY,
        )
    )


def _candidate_show_folders():
    candidates = []

    settings_show_name = _read_show_name_from_settings()
    if settings_show_name:
        candidates.append(f"/Game/_{settings_show_name}")

    try:
        asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
        root_sub_paths = asset_registry.get_sub_paths("/Game", recurse=False)
    except Exception as exc:
        _log_error(f"Could not query show folders under /Game: {exc}")
        return candidates

    for folder_path in sorted(str(path) for path in root_sub_paths):
        folder_name = folder_path.rsplit("/", 1)[-1]
        if not folder_name.startswith("_"):
            continue

        showholder_path = f"{folder_path}/_showholder"
        if unreal.EditorAssetLibrary.does_asset_exist(showholder_path):
            candidates.append(folder_path)

    result = []
    seen = set()

    for folder_path in candidates:
        cleaned = str(folder_path).replace("\\", "/").rstrip("/")
        key = cleaned.lower()

        if not cleaned or key in seen:
            continue

        seen.add(key)
        result.append(cleaned)

    return result


def _find_show_folder_for_sequence(sequence_name):
    matches = []

    for show_folder in _candidate_show_folders():
        sequence_folder = f"{show_folder}/Sequences/{sequence_name}"
        sequenceholder_path = f"{sequence_folder}/_sequenceholder"

        if not unreal.EditorAssetLibrary.does_directory_exist(sequence_folder):
            continue

        if not unreal.EditorAssetLibrary.does_asset_exist(sequenceholder_path):
            _log_warning(
                f"Ignoring sequence folder missing _sequenceholder: {sequence_folder}"
            )
            continue

        matches.append(show_folder)

    if not matches:
        _log_error(
            f"Could not find a show containing sequence folder '{sequence_name}' "
            "and its required _sequenceholder asset."
        )
        return ""

    if len(matches) > 1:
        _log_warning(
            f"Multiple shows contain sequence '{sequence_name}'. "
            f"Using first resolved show folder: {matches[0]}"
        )
        for match in matches:
            _log_warning(f"Sequence show candidate: {match}")

    return matches[0]


def _load_level_sequence(asset_path):
    package_path = _asset_package_path(asset_path)

    if not unreal.EditorAssetLibrary.does_asset_exist(package_path):
        return None

    loaded_asset = unreal.EditorAssetLibrary.load_asset(package_path)
    if loaded_asset and isinstance(loaded_asset, unreal.LevelSequence):
        return loaded_asset

    return None


def _find_data_asset_for_shot(sequence_folder, shot_name):
    shot_folder = f"{sequence_folder}/{shot_name}"
    expected_name = f"{shot_name}_Data"
    expected_path = f"{shot_folder}/{expected_name}"

    if unreal.EditorAssetLibrary.does_asset_exist(expected_path):
        loaded_asset = unreal.EditorAssetLibrary.load_asset(expected_path)
        if loaded_asset:
            return loaded_asset, expected_path

    if not unreal.EditorAssetLibrary.does_directory_exist(shot_folder):
        return None, ""

    fallback_paths = unreal.EditorAssetLibrary.list_assets(
        shot_folder,
        recursive=False,
        include_folder=False,
    )

    for asset_path in fallback_paths:
        candidate_name = _asset_name(asset_path)
        if candidate_name == expected_name:
            loaded_asset = unreal.EditorAssetLibrary.load_asset(asset_path)
            if loaded_asset:
                return loaded_asset, _asset_package_path(asset_path)

    for asset_path in fallback_paths:
        candidate_name = _asset_name(asset_path)
        if not candidate_name.endswith("_Data"):
            continue

        loaded_asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        if loaded_asset:
            _log_warning(
                f"Using fallback shot data asset for '{shot_name}': "
                f"{_asset_package_path(asset_path)}"
            )
            return loaded_asset, _asset_package_path(asset_path)

    return None, ""


def _get_first_editor_property(asset_object, property_names):
    for property_name in property_names:
        try:
            return True, asset_object.get_editor_property(property_name)
        except Exception:
            continue

    return False, None


def _get_is_active(shot_data_asset, shot_name):
    found, value = _get_first_editor_property(
        shot_data_asset,
        IS_ACTIVE_PROPERTY_CANDIDATES,
    )

    if not found:
        _log_warning(
            f"Shot data asset for '{shot_name}' does not expose IsActive. "
            "Treating the shot as inactive."
        )
        return False

    return bool(value)


def _get_shot_order_number(shot_data_asset, shot_name):
    found, value = _get_first_editor_property(
        shot_data_asset,
        SHOT_ORDER_PROPERTY_CANDIDATES,
    )

    if not found:
        _log_warning(
            f"Shot data asset for '{shot_name}' does not expose "
            "ShotOrderNumber. Using 0."
        )
        return 0

    if isinstance(value, bool):
        _log_warning(
            f"Invalid ShotOrderNumber for '{shot_name}': {value!r}. Using 0."
        )
        return 0

    try:
        return int(str(value).strip())
    except Exception as exc:
        _log_warning(
            f"Invalid ShotOrderNumber for '{shot_name}': {value!r}. "
            f"Using 0. Error: {exc}"
        )
        return 0


def _discover_active_shots(sequence_folder, sequence_name):
    asset_paths = unreal.EditorAssetLibrary.list_assets(
        sequence_folder,
        recursive=False,
        include_folder=False,
    )

    rows = []

    for asset_path in asset_paths:
        shot_name = _asset_name(asset_path)
        match = SHOT_NAME_PATTERN.fullmatch(shot_name)

        if not match:
            continue

        if match.group("sequence").upper() != sequence_name:
            continue

        shot_sequence = _load_level_sequence(asset_path)
        if not shot_sequence:
            continue

        shot_data_asset, shot_data_path = _find_data_asset_for_shot(
            sequence_folder,
            shot_name,
        )

        if not shot_data_asset:
            _log_warning(
                f"Skipping '{shot_name}': no shot data asset was found in "
                f"'{sequence_folder}/{shot_name}'."
            )
            continue

        if not _get_is_active(shot_data_asset, shot_name):
            _log(f"Inactive shot skipped: {shot_name}")
            continue

        playback_start = int(shot_sequence.get_playback_start())
        playback_end = int(shot_sequence.get_playback_end())
        duration = playback_end - playback_start

        if duration <= 0:
            _log_warning(
                f"Skipping active shot '{shot_name}': invalid playback range "
                f"{playback_start}-{playback_end}."
            )
            continue

        rows.append(
            {
                "shot_name": shot_name,
                "shot_number": int(match.group("shot")),
                "shot_order_number": _get_shot_order_number(
                    shot_data_asset,
                    shot_name,
                ),
                "sequence_asset": shot_sequence,
                "sequence_path": _asset_package_path(asset_path),
                "data_asset_path": shot_data_path,
                "playback_start": playback_start,
                "playback_end": playback_end,
                "duration": duration,
            }
        )

    rows.sort(
        key=lambda row: (
            row["shot_order_number"],
            row["shot_number"],
            row["shot_name"].lower(),
        )
    )

    return rows


def _close_master_if_open(master_asset_path):
    try:
        current_sequence = (
            unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
        )
    except Exception:
        current_sequence = None

    if not current_sequence:
        return

    try:
        current_path = _asset_package_path(current_sequence.get_path_name())
    except Exception:
        current_path = ""

    if current_path.lower() != master_asset_path.lower():
        return

    try:
        unreal.LevelSequenceEditorBlueprintLibrary.close_level_sequence()
        _log(f"Closed currently open master before replacement: {master_asset_path}")
    except Exception as exc:
        _log_warning(f"Could not close existing master sequence: {exc}")


def _delete_existing_master(master_asset_path):
    if not unreal.EditorAssetLibrary.does_asset_exist(master_asset_path):
        return True

    _close_master_if_open(master_asset_path)
    _log(f"Deleting existing master sequence: {master_asset_path}")

    if unreal.EditorAssetLibrary.delete_asset(master_asset_path):
        return True

    _log_error(f"Failed to delete existing master sequence: {master_asset_path}")
    return False


def _create_master_asset(sequence_folder, master_name):
    created_asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name=master_name,
        package_path=sequence_folder,
        asset_class=unreal.LevelSequence,
        factory=unreal.LevelSequenceFactoryNew(),
    )

    if not created_asset:
        return None

    if isinstance(created_asset, unreal.LevelSequence):
        return created_asset

    return _load_level_sequence(f"{sequence_folder}/{master_name}")


def _add_subsequence_track(master_sequence):
    for method_name in ("add_track", "add_master_track"):
        method = getattr(master_sequence, method_name, None)
        if not callable(method):
            continue

        try:
            track = method(unreal.MovieSceneSubTrack)
            if track:
                return track
        except Exception:
            continue

    return None


def _set_subsequence_reference(section, shot_sequence):
    set_sequence = getattr(section, "set_sequence", None)
    if callable(set_sequence):
        try:
            set_sequence(shot_sequence)
            return True
        except Exception:
            pass

    for property_name in ("sub_sequence", "sequence"):
        try:
            section.set_editor_property(property_name, shot_sequence)
            return True
        except Exception:
            continue

    return False


def _set_section_range(section, start_frame, end_frame):
    set_range = getattr(section, "set_range", None)
    if callable(set_range):
        try:
            set_range(start_frame, end_frame)
            return True
        except Exception:
            pass

    start_set = False
    end_set = False

    set_start_frame = getattr(section, "set_start_frame", None)
    if callable(set_start_frame):
        try:
            set_start_frame(start_frame)
            start_set = True
        except Exception:
            pass

    set_end_frame = getattr(section, "set_end_frame", None)
    if callable(set_end_frame):
        try:
            set_end_frame(end_frame)
            end_set = True
        except Exception:
            pass

    return start_set and end_set


def _open_master_sequence(master_sequence):
    try:
        opened = unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(
            master_sequence
        )
    except Exception as exc:
        _log_warning(f"Could not open new master sequence in Sequencer: {exc}")
        return False

    if not opened:
        _log_warning("Unreal reported that the new master sequence did not open.")
        return False

    try:
        unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
    except Exception:
        pass

    return True


def run(sequence_name):
    """
    Rebuild <SEQUENCE>_Master from active shots in ShotOrderNumber order.

    The master starts at frame 0. Each child section uses the duration of the
    source shot's playback range and is placed immediately after the previous
    shot. A subsequence section's zero Start Frame Offset means it begins at the
    child sequence's own playback start, so production ranges such as
    1001-1101 play correctly inside a 0-based review master.
    """
    global master_sequence_asset
    global active_shot_count
    global added_shots

    _reset_outputs()

    clean_sequence_name = _sanitize_sequence_name(sequence_name)
    if not clean_sequence_name:
        _log_error("Sanitized sequence_name is empty.")
        return ""

    _log("----- run() called -----")
    _log(f"Sequence name: {clean_sequence_name}")

    show_folder = _find_show_folder_for_sequence(clean_sequence_name)
    if not show_folder:
        return ""

    sequence_folder = f"{show_folder}/Sequences/{clean_sequence_name}"
    master_name = f"{clean_sequence_name}_Master"
    master_asset_path = f"{sequence_folder}/{master_name}"

    active_rows = _discover_active_shots(
        sequence_folder,
        clean_sequence_name,
    )

    if not active_rows:
        _log_error(
            f"No valid active shots were found for sequence '{clean_sequence_name}'. "
            "The existing master, if any, was left untouched."
        )
        return ""

    _log(f"Active shots resolved: {len(active_rows)}")
    for row in active_rows:
        _log(
            f"  Order {row['shot_order_number']}: {row['shot_name']} | "
            f"source {row['playback_start']}-{row['playback_end']} | "
            f"duration {row['duration']}"
        )

    if not _delete_existing_master(master_asset_path):
        return ""

    master_sequence = _create_master_asset(sequence_folder, master_name)
    if not master_sequence:
        _log_error(f"Failed to create master Level Sequence: {master_asset_path}")
        return ""

    sub_track = _add_subsequence_track(master_sequence)
    if not sub_track:
        _log_error(
            "Failed to create a subsequences track. "
            "Make sure the Sequencer Scripting plugin is enabled."
        )
        return ""

    cursor_frame = 0
    successfully_added = []

    for row in active_rows:
        section_start = cursor_frame
        section_end = section_start + row["duration"]

        try:
            section = sub_track.add_section()
        except Exception as exc:
            _log_error(
                f"Failed to add section for '{row['shot_name']}': {exc}"
            )
            return ""

        if not section:
            _log_error(f"Failed to add section for '{row['shot_name']}'.")
            return ""

        if not _set_subsequence_reference(section, row["sequence_asset"]):
            _log_error(
                f"Failed to assign shot sequence to section: "
                f"{row['sequence_path']}"
            )
            return ""

        if not _set_section_range(section, section_start, section_end):
            _log_error(
                f"Failed to set section range for '{row['shot_name']}' "
                f"to {section_start}-{section_end}."
            )
            return ""

        successfully_added.append(
            {
                "shot_name": row["shot_name"],
                "shot_order_number": row["shot_order_number"],
                "master_start": section_start,
                "master_end": section_end,
                "source_start": row["playback_start"],
                "source_end": row["playback_end"],
            }
        )
        cursor_frame = section_end

    master_sequence.set_playback_start(0)
    master_sequence.set_playback_end(cursor_frame)

    try:
        master_sequence.modify()
        master_sequence.mark_package_dirty()
    except Exception:
        pass

    if not unreal.EditorAssetLibrary.save_loaded_asset(master_sequence):
        _log_error(f"Failed to save master Level Sequence: {master_asset_path}")
        return ""

    _open_master_sequence(master_sequence)

    master_sequence_asset = master_asset_path
    active_shot_count = len(successfully_added)
    added_shots = successfully_added

    _log(
        f"Created master sequence successfully: {master_asset_path} | "
        f"shots: {active_shot_count} | playback: 0-{cursor_frame}"
    )

    return master_asset_path
