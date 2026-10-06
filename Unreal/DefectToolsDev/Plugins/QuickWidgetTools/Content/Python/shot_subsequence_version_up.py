import os
import re
import unreal


LOG_PREFIX = "[ShotSubsequenceVersionUp]"

ALLOWED_SUBSEQUENCES = {"PREVIS", "LVL", "LGT", "FX", "ENV", "CAM", "ANM"}

# Public module state for Blueprint Execute Python Script nodes.
# After run(...) succeeds, these are populated with useful paths.
new_subsequence_file = ""
new_subsequence_asset = ""
master_sequence_file = ""
master_sequence_asset = ""
changed_files = []


class VersionedSubsequence(object):
    def __init__(self, asset_path, asset_name, folder_path, version_number, version_digits):
        self.asset_path = asset_path
        self.asset_name = asset_name
        self.folder_path = folder_path
        self.version_number = version_number
        self.version_digits = version_digits


def _reset_outputs():
    global new_subsequence_file
    global new_subsequence_asset
    global master_sequence_file
    global master_sequence_asset
    global changed_files

    new_subsequence_file = ""
    new_subsequence_asset = ""
    master_sequence_file = ""
    master_sequence_asset = ""
    changed_files = []


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


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
    if value is None:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", str(value))
    return cleaned.upper()


def _sanitize_subsequence_name(value):
    if value is None:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9]", "", str(value))
    return cleaned.upper()


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
    """
    Convert /Game/Folder/Asset to the filesystem path for the .uasset file.
    Example:
        /Game/_Show/Sequences/ABC/ABC_000_0050
        -> D:/Project/Content/_Show/Sequences/ABC/ABC_000_0050.uasset
    """
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


def _find_current_show_name():
    asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
    sub_paths = asset_registry.get_sub_paths("/Game", recurse=False)

    candidate_folders = sorted(
        _clean_game_path(path)
        for path in sub_paths
        if path.split("/")[-1].startswith("_")
    )

    for folder_path in candidate_folders:
        folder_name = folder_path.rsplit("/", 1)[-1]
        showholder_asset_path = f"{folder_path}/_showholder"

        if unreal.EditorAssetLibrary.does_asset_exist(showholder_asset_path):
            show_name = folder_name[1:] if folder_name.startswith("_") else folder_name
            _log(f"Current show resolved from _showholder: {show_name}")
            return show_name

    return ""


def _load_level_sequence(asset_path):
    package_path = _asset_package_path(asset_path)

    if not unreal.EditorAssetLibrary.does_asset_exist(package_path):
        return None

    loaded_asset = unreal.EditorAssetLibrary.load_asset(package_path)
    if loaded_asset and isinstance(loaded_asset, unreal.LevelSequence):
        return loaded_asset

    return None


def _find_master_sequence(shot_name):
    sequence_name = shot_name.split("_", 1)[0]
    candidate_paths = []

    show_name = _find_current_show_name()
    if show_name and sequence_name:
        sequence_folder = f"/Game/_{show_name}/Sequences/{sequence_name}"
        candidate_paths.append(f"{sequence_folder}/{shot_name}")
        candidate_paths.append(f"{sequence_folder}/{shot_name}/{shot_name}")

    seen = set()
    for candidate_path in candidate_paths:
        package_path = _asset_package_path(candidate_path)
        if package_path in seen:
            continue
        seen.add(package_path)

        loaded_sequence = _load_level_sequence(package_path)
        if loaded_sequence:
            _log(f"Master sequence found by expected path: {package_path}")
            return loaded_sequence, package_path

    _log_warning("Master sequence not found by expected show path. Scanning /Game recursively.")

    matching_paths = []
    for asset_path in unreal.EditorAssetLibrary.list_assets("/Game", recursive=True, include_folder=False):
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


def _build_version_pattern(shot_name, subsequence_name):
    return re.compile(
        rf"^{re.escape(shot_name)}_{re.escape(subsequence_name)}_v(\d+)$",
        re.IGNORECASE,
    )


def _unique_existing_directories(paths):
    unique_paths = []
    seen = set()

    for path in paths:
        cleaned = _clean_game_path(path)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)

        if unreal.EditorAssetLibrary.does_directory_exist(cleaned):
            unique_paths.append(cleaned)

    return unique_paths


def _get_subsequence_search_roots(master_asset_path, shot_name):
    master_folder = _parent_directory(master_asset_path)
    parent_folder = _parent_directory(master_folder)

    roots = [master_folder]

    shot_folder_candidate = f"{master_folder}/{shot_name}"
    roots.append(shot_folder_candidate)

    if _asset_name(master_folder).upper() == shot_name:
        roots.append(parent_folder)

    return _unique_existing_directories(roots)


def _find_highest_subsequence(master_asset_path, shot_name, subsequence_name):
    version_pattern = _build_version_pattern(shot_name, subsequence_name)
    search_roots = _get_subsequence_search_roots(master_asset_path, shot_name)

    _log(f"Subsequence search roots: {search_roots}")

    found = []
    for root in search_roots:
        asset_paths = unreal.EditorAssetLibrary.list_assets(root, recursive=True, include_folder=False)
        for asset_path in asset_paths:
            package_path = _asset_package_path(asset_path)
            asset_name = _asset_name(package_path)
            match = version_pattern.fullmatch(asset_name)
            if not match:
                continue

            loaded_sequence = _load_level_sequence(package_path)
            if not loaded_sequence:
                continue

            version_text = match.group(1)
            found.append(
                VersionedSubsequence(
                    asset_path=package_path,
                    asset_name=asset_name,
                    folder_path=_parent_directory(package_path),
                    version_number=int(version_text),
                    version_digits=max(3, len(version_text)),
                )
            )

    if not found:
        return None

    found.sort(key=lambda item: (item.version_number, item.version_digits, item.asset_path))
    highest = found[-1]
    _log(f"Highest subsequence found: {highest.asset_path}")
    return highest


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
    """
    Different Unreal versions expose Sequencer tracks in different places.
    Try several paths so the tool survives API drift between 5.x builds.
    """
    tracks = []
    source_counts = []

    # Some versions expose these directly on LevelSequence.
    for method_name in ("get_master_tracks", "get_tracks"):
        direct_tracks = _call_no_arg_method(master_sequence, method_name)
        _add_unique_tracks(
            tracks,
            direct_tracks,
            f"LevelSequence.{method_name}",
            source_counts,
        )

    # Sequencer Scripting often exposes them through MovieSceneSequenceExtensions.
    sequence_extensions = getattr(unreal, "MovieSceneSequenceExtensions", None)
    if sequence_extensions:
        for method_name in ("get_master_tracks", "get_tracks"):
            method = getattr(sequence_extensions, method_name, None)
            if not callable(method):
                continue

            try:
                extension_tracks = method(master_sequence)
                _add_unique_tracks(
                    tracks,
                    extension_tracks,
                    f"MovieSceneSequenceExtensions.{method_name}",
                    source_counts,
                )
            except Exception as exc:
                _log_warning(f"MovieSceneSequenceExtensions.{method_name} failed: {exc}")

    # Other versions expose them on the underlying MovieScene.
    movie_scene = _get_movie_scene(master_sequence)
    if movie_scene:
        for method_name in ("get_master_tracks", "get_tracks"):
            movie_scene_tracks = _call_no_arg_method(movie_scene, method_name)
            _add_unique_tracks(
                tracks,
                movie_scene_tracks,
                f"MovieScene.{method_name}",
                source_counts,
            )

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


def _find_sections_to_replace(master_sequence, highest_subsequence, shot_name, subsequence_name):
    version_pattern = _build_version_pattern(shot_name, subsequence_name)
    exact_matches = []
    family_matches = []
    found_section_paths = []

    for section in _get_subsequence_sections(master_sequence):
        current_sequence = _get_section_sequence(section)
        current_path = _get_sequence_asset_path(current_sequence)
        current_name = _asset_name(current_path)
        if current_path:
            found_section_paths.append(current_path)

        if current_path == highest_subsequence.asset_path:
            exact_matches.append(section)
            continue

        if version_pattern.fullmatch(current_name):
            family_matches.append(section)

    if found_section_paths:
        _log("Subsequence section sequence paths discovered:")
        for path in sorted(set(found_section_paths)):
            _log(f"  {path}")
    else:
        _log_warning("No readable sequence paths were found on the discovered subsequence sections.")

    if exact_matches:
        return exact_matches, "exact"

    if family_matches:
        return family_matches, "family"

    return [], "none"


def _duplicate_subsequence(highest_subsequence, shot_name, subsequence_name):
    next_version = highest_subsequence.version_number + 1
    new_asset_name = f"{shot_name}_{subsequence_name}_v{next_version:0{highest_subsequence.version_digits}d}"
    new_asset_path = f"{highest_subsequence.folder_path}/{new_asset_name}"

    if unreal.EditorAssetLibrary.does_asset_exist(new_asset_path):
        _log_error(f"Target version already exists, aborting: {new_asset_path}")
        return None, ""

    _log("Duplicating subsequence:")
    _log(f"  Source: {highest_subsequence.asset_path}")
    _log(f"  Target: {new_asset_path}")

    new_asset = unreal.EditorAssetLibrary.duplicate_asset(highest_subsequence.asset_path, new_asset_path)
    if not new_asset:
        _log_error("duplicate_asset returned None.")
        return None, ""

    if not isinstance(new_asset, unreal.LevelSequence):
        new_asset = _load_level_sequence(new_asset_path)

    if not new_asset or not isinstance(new_asset, unreal.LevelSequence):
        _log_error(f"Duplicated asset is not a Level Sequence: {new_asset_path}")
        return None, ""

    return new_asset, new_asset_path


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


def run(shot_name, subsequence_name):
    """
    Version up a shot subsequence and replace it in the shot's master Level Sequence.

    Args:
        shot_name (str): Shot name, for example ABC_000_0050.
        subsequence_name (str): One of previs, lvl, lgt, fx, env, cam, anm.

    Returns:
        str: New subsequence .uasset filesystem path on success, or "" on failure.
    """
    global new_subsequence_file
    global new_subsequence_asset
    global master_sequence_file
    global master_sequence_asset
    global changed_files

    _reset_outputs()

    _log("----- run() called -----")
    _log(f"Raw shot_name: {shot_name!r}")
    _log(f"Raw subsequence_name: {subsequence_name!r}")

    sanitized_shot_name = _sanitize_shot_name(shot_name)
    sanitized_subsequence_name = _sanitize_subsequence_name(subsequence_name)

    if not sanitized_shot_name:
        _log_error("shot_name is empty after sanitizing.")
        return ""

    if sanitized_subsequence_name not in ALLOWED_SUBSEQUENCES:
        allowed = ", ".join(sorted(ALLOWED_SUBSEQUENCES))
        _log_error(f"Invalid subsequence_name '{subsequence_name}'. Allowed values: {allowed}")
        return ""

    master_sequence, master_asset_path = _find_master_sequence(sanitized_shot_name)
    if not master_sequence:
        _log_error(f"Could not find master Level Sequence for shot: {sanitized_shot_name}")
        return ""

    highest_subsequence = _find_highest_subsequence(
        master_asset_path,
        sanitized_shot_name,
        sanitized_subsequence_name,
    )
    if not highest_subsequence:
        _log_error(
            "Could not find a versioned subsequence named "
            f"{sanitized_shot_name}_{sanitized_subsequence_name}_v### near master: {master_asset_path}"
        )
        return ""

    sections_to_replace, match_mode = _find_sections_to_replace(
        master_sequence,
        highest_subsequence,
        sanitized_shot_name,
        sanitized_subsequence_name,
    )

    if not sections_to_replace:
        _log_error(
            "Master sequence does not contain a matching subsequence section for "
            f"{sanitized_shot_name}_{sanitized_subsequence_name}_v###. No copy was made."
        )
        return ""

    if match_mode == "family":
        _log_warning(
            "Master sequence did not reference the highest version directly. "
            "Replacing matching family subsection(s) with the new highest version anyway."
        )

    new_sequence, new_asset_path = _duplicate_subsequence(
        highest_subsequence,
        sanitized_shot_name,
        sanitized_subsequence_name,
    )
    if not new_sequence:
        return ""

    replaced_count = 0
    for section in sections_to_replace:
        if _set_section_sequence(section, new_sequence):
            replaced_count += 1
        else:
            _log_error("Failed to set new sequence on a MovieSceneSubSection.")

    if replaced_count < 1:
        _log_error("No subsequence sections were replaced. New copied asset was left in place for inspection.")
        return ""

    _mark_dirty(new_sequence)
    _mark_dirty(master_sequence)

    saved_new = _save_loaded_asset(new_sequence, new_asset_path)
    saved_master = _save_loaded_asset(master_sequence, master_asset_path)

    _refresh_sequencer_if_possible()

    if not saved_new or not saved_master:
        return ""

    new_subsequence_asset = new_asset_path
    master_sequence_asset = master_asset_path
    new_subsequence_file = _asset_package_to_file_path(new_asset_path)
    master_sequence_file = _asset_package_to_file_path(master_asset_path)
    changed_files = _dedupe_file_paths([new_subsequence_file, master_sequence_file])

    if not new_subsequence_file:
        _log_error(f"Could not convert new subsequence asset path to filesystem path: {new_asset_path}")
        return ""

    _log(
        f"Version up complete. Replaced {replaced_count} subsection(s): "
        f"{highest_subsequence.asset_name} -> {_asset_name(new_asset_path)}"
    )
    _log(f"New subsequence asset: {new_subsequence_asset}")
    _log(f"New subsequence file: {new_subsequence_file}")

    if master_sequence_file:
        _log(f"Changed master sequence file: {master_sequence_file}")
    else:
        _log_warning(f"Could not convert master sequence asset path to filesystem path: {master_asset_path}")

    return new_subsequence_file


if __name__ == "__main__":
    run("", "")
