# -*- coding: utf-8 -*-
"""
update_master_shot_sequence_subsequences.py

Update a shot master Level Sequence so its existing subsequence sections point to
latest available versioned subsequences on disk.

Example:
    Master:
        /Game/_S3Bishop/Sequences/ZZZ/ZZZ_000_0150

    Subsequence root:
        /Game/_S3Bishop/Sequences/ZZZ/ZZZ_000_0150/SubSequences

    If the master references:
        ZZZ_000_0150_LGT_v001

    and the folders contain:
        ZZZ_000_0150_LGT_v003

    the master section is switched to v003.

Blueprint Execute Python Script usage:
    import importlib
    import update_master_shot_sequence_subsequences

    importlib.invalidate_caches()
    importlib.reload(update_master_shot_sequence_subsequences)

    success = update_master_shot_sequence_subsequences.run("ZZZ_000_0150")

Returns:
    "true" when the scan completes successfully, including when nothing needed updating.
    "" on failure.

Module outputs after run:
    master_sequence_asset
    master_sequence_file
    changed_files
    updated_sections
    skipped_sections
"""

import os
import re

import unreal


LOG_PREFIX = "[UpdateMasterShotSequenceSubsequences]"

SETTINGS_FILE_NAME = "QuickWidgetToolsSettings.ini"
SETTINGS_SECTION = "/Script/QuickWidgetTools.RenderToolSettings"
SHOW_NAME_SETTINGS_KEY = "show_name"

VERSIONED_SUBSEQUENCE_PATTERN_TEMPLATE = r"^{shot_name}_([A-Za-z0-9]+)_v(\d+)$"

# Optional guardrail. Empty set means all families matching SHOT_FAMILY_v### are allowed.
ALLOWED_SUBSEQUENCES = {"PREVIS", "LVL", "LGT", "FX", "ENV", "CAM", "ANM"}

# Public module state for Blueprint Execute Python Script nodes.
master_sequence_asset = ""
master_sequence_file = ""
changed_files = []
updated_sections = []
skipped_sections = []


class VersionedSubsequence(object):
    def __init__(self, family, asset_path, asset_name, version_number, version_digits):
        self.family = family
        self.asset_path = asset_path
        self.asset_name = asset_name
        self.version_number = version_number
        self.version_digits = version_digits


def _reset_outputs():
    global master_sequence_asset
    global master_sequence_file
    global changed_files
    global updated_sections
    global skipped_sections

    master_sequence_asset = ""
    master_sequence_file = ""
    changed_files = []
    updated_sections = []
    skipped_sections = []


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


# -----------------------------------------------------------------------------
# Path / name helpers
# -----------------------------------------------------------------------------

def _clean_game_path(path):
    text = str(path or "").strip().replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")
    if len(text) > 1:
        text = text.rstrip("/")
    return text


def _clean_file_path(path):
    text = str(path or "").strip().replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")
    return text


def _asset_package_path(asset_path):
    """Return /Game/Folder/Asset from either package or object path."""
    text = _clean_game_path(asset_path)
    if "." in text:
        text = text.split(".", 1)[0]
    return text


def _asset_name(asset_path):
    package_path = _asset_package_path(asset_path)
    return package_path.rsplit("/", 1)[-1]


def _parent_directory(asset_path):
    package_path = _asset_package_path(asset_path)
    if "/" not in package_path:
        return ""
    return package_path.rsplit("/", 1)[0]


def _sanitize_shot_name(value):
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", str(value or ""))
    return cleaned.upper()


def _sanitize_family_name(value):
    cleaned = re.sub(r"[^A-Za-z0-9]", "", str(value or ""))
    return cleaned.upper()


def _shot_sequence_name(shot_name):
    return str(shot_name or "").split("_", 1)[0].upper()


def _project_content_dir():
    try:
        path = unreal.Paths.project_content_dir()
        if path:
            return _clean_file_path(unreal.Paths.convert_relative_path_to_full(path))
    except Exception:
        pass

    try:
        path = unreal.SystemLibrary.get_project_content_directory()
        if path:
            return _clean_file_path(path)
    except Exception:
        pass

    return ""


def _asset_package_to_file_path(asset_path):
    package_path = _asset_package_path(asset_path)
    if not package_path.startswith("/Game/"):
        return ""

    content_dir = _project_content_dir()
    if not content_dir:
        return ""

    relative_path = package_path[len("/Game/"):] + ".uasset"
    return _clean_file_path(os.path.join(content_dir, relative_path))


def _dedupe_file_paths(paths):
    result = []
    seen = set()

    for path in paths:
        cleaned = _clean_file_path(path)
        if not cleaned:
            continue

        key = cleaned.lower()
        if key in seen:
            continue

        seen.add(key)
        result.append(cleaned)

    return result


# -----------------------------------------------------------------------------
# Settings / show lookup
# -----------------------------------------------------------------------------

def _find_config_dir(project_dir):
    candidates = [
        os.path.join(project_dir, "Saved", "Config", "WindowsEditor"),
        os.path.join(project_dir, "Saved", "Config", "Windows"),
        os.path.join(project_dir, "Saved", "Config"),
    ]

    for folder in candidates:
        if os.path.isdir(folder):
            return folder

    return os.path.join(project_dir, "Saved", "Config", "WindowsEditor")


def _get_settings_file_path():
    project_dir = unreal.Paths.project_dir()
    config_dir = _find_config_dir(project_dir)
    return os.path.normpath(os.path.join(config_dir, SETTINGS_FILE_NAME))


def _find_section_bounds(lines, section_name):
    section_header = f"[{section_name}]"
    section_start = -1
    section_end = len(lines)

    for i, line in enumerate(lines):
        if line.strip() == section_header:
            section_start = i
            break

    if section_start == -1:
        return -1, -1

    for i in range(section_start + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section_end = i
            break

    return section_start, section_end


def _get_section_value(text, section_name, key):
    lines = text.splitlines()
    section_start, section_end = _find_section_bounds(lines, section_name)
    if section_start == -1:
        return ""

    prefix = f"{key}="
    for i in range(section_start + 1, section_end):
        stripped = lines[i].strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip()

    return ""


def _read_show_name_from_settings():
    settings_path = _get_settings_file_path()
    if not os.path.isfile(settings_path):
        return ""

    try:
        with open(settings_path, "r", encoding="utf-8") as handle:
            text = handle.read()
        return _get_section_value(text, SETTINGS_SECTION, SHOW_NAME_SETTINGS_KEY).strip()
    except Exception as exc:
        _log_warning(f"Could not read show_name from settings: {exc}")
        return ""


def _safe_show_folder_name(show_name):
    cleaned = re.sub(r"[^A-Za-z0-9]", "", str(show_name or "").strip())
    if not cleaned:
        return ""
    return "_" + cleaned


def _find_show_folders_from_registry():
    folders = []
    try:
        asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
        sub_paths = asset_registry.get_sub_paths("/Game", recurse=False)
    except Exception as exc:
        _log_warning(f"Could not query /Game sub paths: {exc}")
        return folders

    for folder_path in sorted(_clean_game_path(path) for path in sub_paths):
        folder_name = folder_path.rsplit("/", 1)[-1]
        if not folder_name.startswith("_"):
            continue

        showholder_asset_path = f"{folder_path}/_showholder"
        if unreal.EditorAssetLibrary.does_asset_exist(showholder_asset_path):
            folders.append(folder_path)

    return folders


def _candidate_show_folders():
    candidates = []

    settings_show_name = _read_show_name_from_settings()
    if settings_show_name:
        folder_name = _safe_show_folder_name(settings_show_name)
        if folder_name:
            candidates.append(f"/Game/{folder_name}")

    for folder_path in _find_show_folders_from_registry():
        candidates.append(folder_path)

    deduped = []
    seen = set()
    for path in candidates:
        clean = _clean_game_path(path)
        key = clean.lower()
        if not clean or key in seen:
            continue
        seen.add(key)
        deduped.append(clean)

    return deduped


# -----------------------------------------------------------------------------
# Level Sequence helpers
# -----------------------------------------------------------------------------

def _load_level_sequence(asset_path):
    package_path = _asset_package_path(asset_path)

    if not unreal.EditorAssetLibrary.does_asset_exist(package_path):
        return None

    loaded_asset = unreal.EditorAssetLibrary.load_asset(package_path)
    if loaded_asset and isinstance(loaded_asset, unreal.LevelSequence):
        return loaded_asset

    return None


def _find_master_sequence(shot_name):
    sequence_name = _shot_sequence_name(shot_name)
    candidate_paths = []

    for show_folder in _candidate_show_folders():
        sequence_folder = f"{show_folder}/Sequences/{sequence_name}"
        candidate_paths.append(f"{sequence_folder}/{shot_name}")
        candidate_paths.append(f"{sequence_folder}/{shot_name}/{shot_name}")

    seen = set()
    for candidate_path in candidate_paths:
        package_path = _asset_package_path(candidate_path)
        key = package_path.lower()
        if key in seen:
            continue
        seen.add(key)

        loaded_sequence = _load_level_sequence(package_path)
        if loaded_sequence:
            _log(f"Master sequence found by expected path: {package_path}")
            return loaded_sequence, package_path

    _log_warning("Master sequence not found by expected path. Scanning candidate sequence folders only.")

    matching_paths = []
    for show_folder in _candidate_show_folders():
        sequence_folder = f"{show_folder}/Sequences/{sequence_name}"
        if not unreal.EditorAssetLibrary.does_directory_exist(sequence_folder):
            continue

        for asset_path in unreal.EditorAssetLibrary.list_assets(sequence_folder, recursive=True, include_folder=False):
            package_path = _asset_package_path(asset_path)
            if _asset_name(package_path).upper() != shot_name:
                continue

            loaded_sequence = _load_level_sequence(package_path)
            if loaded_sequence:
                matching_paths.append(package_path)

    matching_paths = sorted(set(matching_paths))
    if not matching_paths:
        return None, ""

    if len(matching_paths) > 1:
        _log_warning(f"Multiple master sequences found for {shot_name}. Using first sorted match: {matching_paths[0]}")
        for path in matching_paths:
            _log_warning(f"Master candidate: {path}")

    master_path = matching_paths[0]
    return _load_level_sequence(master_path), master_path


def _build_any_version_pattern(shot_name):
    return re.compile(
        VERSIONED_SUBSEQUENCE_PATTERN_TEMPLATE.format(shot_name=re.escape(shot_name)),
        re.IGNORECASE,
    )


def _get_subsequence_root_candidates(master_asset_path, shot_name):
    master_folder = _parent_directory(master_asset_path)
    parent_folder = _parent_directory(master_folder)

    candidates = [
        f"{master_folder}/SubSequences",
        f"{master_folder}/{shot_name}/SubSequences",
    ]

    if _asset_name(master_folder).upper() == shot_name:
        candidates.append(f"{master_folder}/SubSequences")
        candidates.append(f"{parent_folder}/{shot_name}/SubSequences")

    existing = []
    seen = set()
    for candidate in candidates:
        clean = _clean_game_path(candidate)
        key = clean.lower()
        if not clean or key in seen:
            continue
        seen.add(key)

        if unreal.EditorAssetLibrary.does_directory_exist(clean):
            existing.append(clean)

    return existing


def _discover_latest_subsequences(master_asset_path, shot_name):
    roots = _get_subsequence_root_candidates(master_asset_path, shot_name)
    if not roots:
        _log_error(f"No SubSequences folder found near master: {master_asset_path}")
        return {}

    _log("Subsequence search roots:")
    for root in roots:
        _log(f"  {root}")

    pattern = _build_any_version_pattern(shot_name)
    latest_by_family = {}

    for root in roots:
        asset_paths = unreal.EditorAssetLibrary.list_assets(root, recursive=True, include_folder=False)
        for asset_path in asset_paths:
            package_path = _asset_package_path(asset_path)
            asset_name = _asset_name(package_path)
            match = pattern.fullmatch(asset_name)
            if not match:
                continue

            family = _sanitize_family_name(match.group(1))
            if ALLOWED_SUBSEQUENCES and family not in ALLOWED_SUBSEQUENCES:
                _log_warning(f"Ignoring unsupported subsequence family: {asset_name}")
                continue

            loaded_sequence = _load_level_sequence(package_path)
            if not loaded_sequence:
                continue

            version_text = match.group(2)
            item = VersionedSubsequence(
                family=family,
                asset_path=package_path,
                asset_name=asset_name,
                version_number=int(version_text),
                version_digits=max(3, len(version_text)),
            )

            current_latest = latest_by_family.get(family)
            if current_latest is None:
                latest_by_family[family] = item
                continue

            if (item.version_number, item.version_digits, item.asset_path) > (
                current_latest.version_number,
                current_latest.version_digits,
                current_latest.asset_path,
            ):
                latest_by_family[family] = item

    if latest_by_family:
        _log("Latest discovered subsequences:")
        for family in sorted(latest_by_family.keys()):
            item = latest_by_family[family]
            _log(f"  {family}: {item.asset_name} | {item.asset_path}")
    else:
        _log_warning(f"No versioned Level Sequence assets found under SubSequences for shot: {shot_name}")

    return latest_by_family


def _object_label(obj):
    if not obj:
        return "None"

    try:
        return obj.get_class().get_name()
    except Exception:
        return type(obj).__name__


def _call_no_arg_method(obj, method_name):
    method = getattr(obj, method_name, None)
    if not callable(method):
        return None

    try:
        return method()
    except Exception as exc:
        _log_warning(f"{_object_label(obj)}.{method_name} failed: {exc}")
        return None


def _add_unique_tracks(destination, tracks, source_label, source_counts):
    if not tracks:
        return

    added_count = 0
    seen_ids = {id(track) for track in destination}

    for track in tracks:
        if not track:
            continue
        track_id = id(track)
        if track_id in seen_ids:
            continue

        seen_ids.add(track_id)
        destination.append(track)
        added_count += 1

    if added_count:
        source_counts.append((source_label, added_count))


def _get_movie_scene(master_sequence):
    get_movie_scene_func = getattr(master_sequence, "get_movie_scene", None)
    if callable(get_movie_scene_func):
        try:
            movie_scene = get_movie_scene_func()
            if movie_scene:
                return movie_scene
        except Exception as exc:
            _log_warning(f"LevelSequence.get_movie_scene failed: {exc}")

    try:
        movie_scene = master_sequence.get_editor_property("movie_scene")
        if movie_scene:
            return movie_scene
    except Exception:
        pass

    return None


def _get_tracks_from_sequence(master_sequence):
    tracks = []
    source_counts = []

    for method_name in ("get_master_tracks", "get_tracks"):
        direct_tracks = _call_no_arg_method(master_sequence, method_name)
        _add_unique_tracks(tracks, direct_tracks, f"LevelSequence.{method_name}", source_counts)

    sequence_extensions = getattr(unreal, "MovieSceneSequenceExtensions", None)
    if sequence_extensions:
        for method_name in ("get_master_tracks", "get_tracks"):
            method = getattr(sequence_extensions, method_name, None)
            if not callable(method):
                continue
            try:
                extension_tracks = method(master_sequence)
                _add_unique_tracks(tracks, extension_tracks, f"MovieSceneSequenceExtensions.{method_name}", source_counts)
            except Exception as exc:
                _log_warning(f"MovieSceneSequenceExtensions.{method_name} failed: {exc}")

    movie_scene = _get_movie_scene(master_sequence)
    if movie_scene:
        for method_name in ("get_master_tracks", "get_tracks"):
            movie_scene_tracks = _call_no_arg_method(movie_scene, method_name)
            _add_unique_tracks(tracks, movie_scene_tracks, f"MovieScene.{method_name}", source_counts)

    if source_counts:
        source_text = ", ".join(f"{label}: {count}" for label, count in source_counts)
        _log(f"Master track sources found: {source_text}")
    else:
        _log_error(
            "Could not read any master tracks from the master sequence. "
            "Make sure the Sequencer Scripting plugin is enabled."
        )

    return tracks


def _is_subsequence_section(section):
    if not section:
        return False

    try:
        if isinstance(section, unreal.MovieSceneSubSection):
            return True
    except Exception:
        pass

    try:
        section_class_name = section.get_class().get_name()
    except Exception:
        section_class_name = ""

    return section_class_name == "MovieSceneSubSection"


def _get_subsequence_sections(master_sequence):
    sections = []
    tracks = _get_tracks_from_sequence(master_sequence)

    for track in tracks:
        try:
            track_sections = track.get_sections()
        except Exception as exc:
            _log_warning(f"Could not read sections from track {_object_label(track)!r}: {exc}")
            continue

        for section in track_sections:
            if _is_subsequence_section(section):
                sections.append(section)

    _log(f"Subsequence sections found in master sequence: {len(sections)}")
    return sections


def _get_section_sequence(section):
    get_sequence_func = getattr(section, "get_sequence", None)
    if callable(get_sequence_func):
        try:
            return get_sequence_func()
        except Exception:
            pass

    for property_name in ("sequence", "sub_sequence"):
        try:
            return section.get_editor_property(property_name)
        except Exception:
            continue

    return None


def _get_sequence_asset_path(sequence_asset):
    if not sequence_asset:
        return ""

    try:
        return _asset_package_path(sequence_asset.get_path_name())
    except Exception:
        return ""


def _set_section_sequence(section, new_sequence):
    try:
        section.modify()
    except Exception:
        pass

    set_sequence_func = getattr(section, "set_sequence", None)
    if callable(set_sequence_func):
        try:
            set_sequence_func(new_sequence)
            return True
        except Exception as exc:
            _log_warning(f"section.set_sequence failed, trying editor property fallback: {exc}")

    for property_name in ("sequence", "sub_sequence"):
        try:
            section.set_editor_property(property_name, new_sequence)
            return True
        except Exception:
            continue

    return False


def _mark_dirty(asset):
    if not asset:
        return

    try:
        asset.modify()
    except Exception:
        pass

    try:
        asset.mark_package_dirty()
    except Exception:
        pass


def _save_loaded_asset(asset, asset_path):
    if not asset:
        return False

    if unreal.EditorAssetLibrary.save_loaded_asset(asset):
        _log(f"Saved: {asset_path}")
        return True

    _log_error(f"Failed to save: {asset_path}")
    return False


def _refresh_sequencer_if_possible():
    try:
        unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Main update logic
# -----------------------------------------------------------------------------

def _evaluate_and_update_sections(master_sequence, latest_by_family, shot_name):
    pattern = _build_any_version_pattern(shot_name)
    replaced_count = 0

    for section in _get_subsequence_sections(master_sequence):
        current_sequence = _get_section_sequence(section)
        current_path = _get_sequence_asset_path(current_sequence)
        current_name = _asset_name(current_path)

        if not current_path:
            skipped_sections.append({
                "reason": "empty_section_sequence",
                "current_path": "",
            })
            continue

        match = pattern.fullmatch(current_name)
        if not match:
            skipped_sections.append({
                "reason": "not_a_matching_shot_subsequence",
                "current_path": current_path,
            })
            _log(f"Skipping non-matching subsequence section: {current_path}")
            continue

        family = _sanitize_family_name(match.group(1))
        current_version = int(match.group(2))
        latest = latest_by_family.get(family)

        if not latest:
            skipped_sections.append({
                "reason": "no_latest_version_found",
                "family": family,
                "current_path": current_path,
            })
            _log_warning(f"No latest asset found for family {family}. Current stays: {current_path}")
            continue

        if current_path == latest.asset_path:
            skipped_sections.append({
                "reason": "already_latest_asset",
                "family": family,
                "current_path": current_path,
            })
            _log(f"Already latest: {current_name}")
            continue

        if current_version >= latest.version_number:
            skipped_sections.append({
                "reason": "current_version_not_lower",
                "family": family,
                "current_path": current_path,
                "latest_path": latest.asset_path,
            })
            _log(f"Current {current_name} is not lower than latest {latest.asset_name}. Skipping.")
            continue

        latest_sequence = _load_level_sequence(latest.asset_path)
        if not latest_sequence:
            _log_error(f"Could not load latest subsequence: {latest.asset_path}")
            continue

        if not _set_section_sequence(section, latest_sequence):
            _log_error(f"Failed to set section sequence: {current_path} -> {latest.asset_path}")
            continue

        replaced_count += 1
        updated_sections.append({
            "family": family,
            "from_asset": current_path,
            "to_asset": latest.asset_path,
            "from_version": current_version,
            "to_version": latest.version_number,
        })
        _log(f"Updated {family}: {current_name} -> {latest.asset_name}")

    return replaced_count


def run(shot_name):
    """
    Update a shot master Level Sequence to use the highest versioned subsequences
    currently found in the shot's SubSequences folders.

    Args:
        shot_name (str): Shot name, for example ZZZ_000_0150.

    Returns:
        str: "true" if scan completed successfully, "" on failure.
    """
    global master_sequence_asset
    global master_sequence_file
    global changed_files

    _reset_outputs()

    _log("----- run() called -----")
    _log(f"Raw shot_name: {shot_name!r}")

    sanitized_shot_name = _sanitize_shot_name(shot_name)
    if not sanitized_shot_name:
        _log_error("shot_name is empty after sanitizing.")
        return ""

    master_sequence, master_asset_path = _find_master_sequence(sanitized_shot_name)
    if not master_sequence:
        _log_error(f"Could not find master Level Sequence for shot: {sanitized_shot_name}")
        return ""

    latest_by_family = _discover_latest_subsequences(master_asset_path, sanitized_shot_name)
    if not latest_by_family:
        _log_error(f"No latest subsequences were discovered for shot: {sanitized_shot_name}")
        return ""

    replaced_count = _evaluate_and_update_sections(
        master_sequence=master_sequence,
        latest_by_family=latest_by_family,
        shot_name=sanitized_shot_name,
    )

    master_sequence_asset = master_asset_path
    master_sequence_file = _asset_package_to_file_path(master_asset_path)

    if replaced_count > 0:
        _mark_dirty(master_sequence)
        saved_master = _save_loaded_asset(master_sequence, master_asset_path)
        _refresh_sequencer_if_possible()

        if not saved_master:
            return ""

        changed_files = _dedupe_file_paths([master_sequence_file])
    else:
        _log("No master subsequence references needed updating.")
        changed_files = []

    _log("Done.")
    _log(f"Master sequence asset: {master_sequence_asset}")
    if master_sequence_file:
        _log(f"Master sequence file: {master_sequence_file}")
    _log(f"Updated section count: {len(updated_sections)}")
    _log(f"Skipped section count: {len(skipped_sections)}")
    for item in updated_sections:
        _log(
            "  Updated {family}: v{from_version:03d} -> v{to_version:03d} | {from_asset} -> {to_asset}".format(
                family=item.get("family", ""),
                from_version=int(item.get("from_version", 0)),
                to_version=int(item.get("to_version", 0)),
                from_asset=item.get("from_asset", ""),
                to_asset=item.get("to_asset", ""),
            )
        )

    return "true"


if __name__ == "__main__":
    run("")
