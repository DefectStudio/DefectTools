import re
import unreal


LOG_PREFIX = "[GatherAllShotsAndFrameRanges]"

_START_FRAME_PROPERTY_NAME = "StartFrame"
_END_FRAME_PROPERTY_NAME = "EndFrame"
_LEVEL_PATH_STRING_PROPERTY_NAME = "AssociatedLevelPathString"
_VERBOSE_LOGS = False


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_verbose(message):
    if _VERBOSE_LOGS:
        _log(message)


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _sanitize_show_name(show_name):
    return "".join(ch for ch in str(show_name or "") if ch.isalnum())


def _sanitize_selected_sequence(selected_sequence):
    cleaned = "".join(ch for ch in str(selected_sequence or "") if ch.isalnum() or ch == "_")
    return cleaned.upper()


def _extract_asset_name(asset_path):
    leaf = str(asset_path).rstrip("/").rsplit("/", 1)[-1]
    return leaf.split(".", 1)[0]


def _parse_shot_name(asset_name):
    match = re.fullmatch(r"([A-Za-z0-9]+)_(\d{3})_(\d{4,})", asset_name)
    if not match:
        return None

    return {
        "sequence_prefix": match.group(1),
        "shot_number": int(match.group(3)),
    }


def _join_game_path(*parts):
    cleaned_parts = []

    for part in parts:
        text = str(part or "").strip().replace("\\", "/")
        while "//" in text:
            text = text.replace("//", "/")
        text = text.strip("/")

        if not text:
            continue

        cleaned_parts.append(text)

    if not cleaned_parts:
        return ""

    if cleaned_parts[0] == "Game":
        return "/" + "/".join(cleaned_parts)

    if cleaned_parts[0].startswith("Game"):
        return "/" + "/".join(cleaned_parts)

    if str(parts[0] or "").strip().startswith("/"):
        return "/" + "/".join(cleaned_parts)

    return "/".join(cleaned_parts)


def _build_shot_folder_path(target_folder, shot_name):
    return _join_game_path(target_folder, shot_name)


def _build_expected_data_asset_path(shot_folder_path, shot_name):
    data_asset_name = f"{shot_name}_Data"
    package_path = _join_game_path(shot_folder_path, data_asset_name)
    return f"{package_path}.{data_asset_name}"


def _find_asset_data(asset_path):
    try:
        return unreal.EditorAssetLibrary.find_asset_data(asset_path)
    except Exception:
        return None


def _is_valid_asset_data(asset_data):
    if asset_data is None:
        return False

    is_valid = getattr(asset_data, "is_valid", None)
    if callable(is_valid):
        try:
            return bool(is_valid())
        except Exception:
            pass

    for property_name in ("asset_name", "package_name", "object_path"):
        try:
            value = getattr(asset_data, property_name)
        except Exception:
            continue

        if value and str(value).strip() not in ("None", "null"):
            return True

    return False


def _get_asset_data_class_text(asset_data):
    if not _is_valid_asset_data(asset_data):
        return ""

    class_parts = []
    for property_name in (
        "asset_class_path",
        "asset_class",
        "class_path_name",
        "class_name",
    ):
        try:
            value = getattr(asset_data, property_name)
        except Exception:
            continue

        if value:
            class_parts.append(str(value))

    return " ".join(class_parts)


def _is_level_sequence_asset_path(asset_path, asset_name):
    """Return True for LevelSequence assets without loading the sequence package.

    Loading every LevelSequence here is expensive and can make the UI feel like it is
    preloading shots/levels. AssetData class metadata is enough for this validation.
    If class metadata is unavailable, trust the already-validated shot naming pattern
    instead of falling back to load_asset().
    """

    asset_data = _find_asset_data(asset_path)
    class_text = _get_asset_data_class_text(asset_data)

    if not class_text:
        _log_verbose(
            "Could not read AssetData class metadata for "
            f"'{asset_name}'. Accepting by shot naming pattern without loading asset."
        )
        return True

    if "LevelSequence" in class_text:
        return True

    _log_verbose(
        f"Skipping non-LevelSequence asset by AssetData class: {asset_name} ({class_text})"
    )
    return False


def _find_fallback_data_asset_in_shot_folder(shot_folder_path, shot_name):
    editor_asset_lib = unreal.EditorAssetLibrary

    if not editor_asset_lib.does_directory_exist(shot_folder_path):
        _log_verbose(f"Shot folder does not exist for '{shot_name}': {shot_folder_path}")
        return None

    asset_paths = editor_asset_lib.list_assets(
        shot_folder_path,
        recursive=False,
        include_folder=False,
    )

    if not asset_paths:
        _log_verbose(f"No assets in shot folder for fallback data asset lookup: {shot_folder_path}")
        return None

    preferred_name = f"{shot_name}_Data"
    fallback_candidate_path = None

    for asset_path in asset_paths:
        asset_name = _extract_asset_name(asset_path)
        if asset_name == preferred_name:
            fallback_candidate_path = asset_path
            break

        if asset_name.endswith("_Data") and fallback_candidate_path is None:
            fallback_candidate_path = asset_path

    if not fallback_candidate_path:
        _log_verbose(f"No fallback shot data asset candidates found in folder: {shot_folder_path}")
        return None

    loaded = unreal.load_asset(fallback_candidate_path)
    if not loaded:
        _log_error(f"Failed to load fallback shot data asset: {fallback_candidate_path}")
        return None

    _log_verbose(f"Loaded fallback shot data asset for '{shot_name}': {fallback_candidate_path}")
    return loaded


def _load_data_asset_for_shot(shot_folder_path, shot_name):
    editor_asset_lib = unreal.EditorAssetLibrary
    expected_data_asset_path = _build_expected_data_asset_path(shot_folder_path, shot_name)

    if editor_asset_lib.does_asset_exist(expected_data_asset_path):
        loaded = unreal.load_asset(expected_data_asset_path)
        if loaded:
            _log_verbose(f"Loaded expected shot data asset for '{shot_name}': {expected_data_asset_path}")
            return loaded
        _log_error(f"Failed to load expected shot data asset for '{shot_name}': {expected_data_asset_path}")

    return _find_fallback_data_asset_in_shot_folder(shot_folder_path, shot_name)


def _normalize_level_object_path(level_value):
    text = str(level_value or "").strip().strip("\"'")

    if not text or text in ("None", "null"):
        return ""

    if text.startswith("SoftObjectPath(") and text.endswith(")"):
        text = text[len("SoftObjectPath("):-1].strip().strip("\"'")

    text = text.replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")

    if text.endswith(".umap"):
        text = text[:-5]

    # AssociatedLevelPathString is stored as a package path, for example:
    # /Game/_S3Bishop/Maps/MyMap
    # WBP_02/WBP_03 expect the returned level_paths array to remain usable as an object path.
    if text.startswith("/Game/") and "." not in text:
        asset_name = text.rstrip("/").rsplit("/", 1)[-1]
        text = f"{text}.{asset_name}"

    return text


def _read_int_property(asset, property_name, shot_name):
    try:
        raw_value = asset.get_editor_property(property_name)
    except Exception as exc:
        _log_error(
            f"Shot data asset for '{shot_name}' does not expose {property_name}: {exc}"
        )
        return None

    if isinstance(raw_value, bool):
        _log_error(
            f"Shot data asset property {property_name} for '{shot_name}' is bool, expected int."
        )
        return None

    try:
        return int(raw_value)
    except Exception as exc:
        _log_error(
            f"Shot data asset property {property_name} for '{shot_name}' could not be converted to int. "
            f"Value={raw_value!r}, Error={exc}"
        )
        return None


def _read_level_object_path(shot_data_asset, shot_name):
    try:
        raw_value = shot_data_asset.get_editor_property(_LEVEL_PATH_STRING_PROPERTY_NAME)
    except Exception as exc:
        _log_error(
            f"Shot data asset for '{shot_name}' does not expose {_LEVEL_PATH_STRING_PROPERTY_NAME}: {exc}"
        )
        return ""

    object_path = _normalize_level_object_path(raw_value)
    if object_path:
        _log_verbose(f"Read level association using property '{_LEVEL_PATH_STRING_PROPERTY_NAME}': {object_path}")
        return object_path

    _log_verbose(f"{_LEVEL_PATH_STRING_PROPERTY_NAME} is unset or invalid for '{shot_name}'.")
    return ""


def _get_cached_shot_data(target_folder, shot_name):
    shot_folder_path = _build_shot_folder_path(target_folder, shot_name)
    shot_data_asset = _load_data_asset_for_shot(shot_folder_path, shot_name)

    if not shot_data_asset:
        return None

    start_frame = _read_int_property(
        shot_data_asset,
        _START_FRAME_PROPERTY_NAME,
        shot_name,
    )
    if start_frame is None:
        return None

    end_frame = _read_int_property(
        shot_data_asset,
        _END_FRAME_PROPERTY_NAME,
        shot_name,
    )
    if end_frame is None:
        return None

    level_object_path = _read_level_object_path(shot_data_asset, shot_name)

    return {
        "start_frame": start_frame,
        "end_frame": end_frame,
        "level_path": level_object_path,
    }


def _empty_result():
    return [], [], [], [], 0


def _get_target_sequence_folders(sequences_root, sanitized_selected_sequence):
    editor_asset_lib = unreal.EditorAssetLibrary

    if sanitized_selected_sequence != "ALL":
        target_folder = _join_game_path(sequences_root, sanitized_selected_sequence)

        if not editor_asset_lib.does_directory_exist(target_folder):
            _log_error(f"Target folder does not exist: {target_folder}")
            return []

        sequenceholder_path = _join_game_path(target_folder, "_sequenceholder")
        if not editor_asset_lib.does_asset_exist(sequenceholder_path):
            _log_error(f"Missing required '_sequenceholder' in folder: {sequenceholder_path}")
            return []

        return [(target_folder, sanitized_selected_sequence)]

    asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
    sub_paths = asset_registry.get_sub_paths(sequences_root, recurse=False)
    target_sequences = []

    for sub_path in sorted(str(path) for path in sub_paths):
        sequence_name = sub_path.rstrip("/").rsplit("/", 1)[-1]
        sanitized_sequence_name = _sanitize_selected_sequence(sequence_name)

        if not sanitized_sequence_name:
            _log_verbose(f"Skipping invalid sequence folder name: {sub_path}")
            continue

        sequenceholder_path = _join_game_path(sub_path, "_sequenceholder")
        if not editor_asset_lib.does_asset_exist(sequenceholder_path):
            _log_verbose(
                f"Skipping folder without required '_sequenceholder': {sub_path}"
            )
            continue

        target_sequences.append((sub_path, sanitized_sequence_name))

    _log(f"ALL mode found {len(target_sequences)} valid sequence folder(s).")
    return target_sequences


def run(show_name, selected_sequence):
    shot_names = []
    start_frames = []
    end_frames = []
    level_paths = []
    has_any_shots = 0

    sanitized_show_name = _sanitize_show_name(show_name)
    sanitized_selected_sequence = _sanitize_selected_sequence(selected_sequence)

    _log(f"Input show_name: '{show_name}'")
    _log(f"Input selected_sequence: '{selected_sequence}'")
    _log(f"Sanitized show_name: '{sanitized_show_name}'")
    _log(f"Sanitized selected_sequence: '{sanitized_selected_sequence}'")

    if not sanitized_show_name:
        _log_error(f"Invalid show_name after sanitizing: '{show_name}'")
        return _empty_result()

    if not sanitized_selected_sequence:
        _log_error(f"Invalid selected_sequence after sanitizing: '{selected_sequence}'")
        return _empty_result()

    sequences_root = _join_game_path(
        "/Game",
        f"_{sanitized_show_name}",
        "Sequences",
    )
    _log(f"Sequences root: {sequences_root}")

    editor_asset_lib = unreal.EditorAssetLibrary

    if not editor_asset_lib.does_directory_exist(sequences_root):
        _log_error(f"Sequences root does not exist: {sequences_root}")
        return _empty_result()

    target_sequences = _get_target_sequence_folders(
        sequences_root,
        sanitized_selected_sequence,
    )
    if not target_sequences:
        _log_error(
            f"No valid sequence folders found for selection '{sanitized_selected_sequence}'."
        )
        return _empty_result()

    valid_rows = []

    for target_folder, expected_sequence_prefix in target_sequences:
        _log(f"Scanning target folder: {target_folder}")

        asset_paths = editor_asset_lib.list_assets(
            target_folder,
            recursive=False,
            include_folder=False,
        )
        _log(f"Found {len(asset_paths)} direct asset(s) in target folder.")

        for asset_path in asset_paths:
            asset_name = _extract_asset_name(asset_path)

            if asset_name == "_sequenceholder":
                continue

            parsed = _parse_shot_name(asset_name)
            if not parsed:
                _log_verbose(f"Skipping asset with non-shot naming pattern: {asset_name}")
                continue

            if parsed["sequence_prefix"].upper() != expected_sequence_prefix:
                _log_verbose(
                    "Skipping shot with mismatched sequence prefix: "
                    f"{asset_name} (prefix='{parsed['sequence_prefix']}', "
                    f"expected='{expected_sequence_prefix}')"
                )
                continue

            if not _is_level_sequence_asset_path(asset_path, asset_name):
                continue

            cached_data = _get_cached_shot_data(target_folder, asset_name)
            if cached_data is None:
                continue

            valid_rows.append(
                (
                    expected_sequence_prefix,
                    parsed["shot_number"],
                    asset_name,
                    cached_data["start_frame"],
                    cached_data["end_frame"],
                    cached_data["level_path"],
                )
            )

    if not valid_rows:
        _log(
            f"No valid shot Level Sequences found for selection "
            f"'{sanitized_selected_sequence}' under {sequences_root}"
        )
        return _empty_result()

    valid_rows.sort(key=lambda row: (row[0], row[1], row[2]))

    for _, _, asset_name, start_frame, end_frame, level_path in valid_rows:
        shot_names.append(asset_name)
        start_frames.append(start_frame)
        end_frames.append(end_frame)
        level_paths.append(level_path)

    has_any_shots = 1

    _log(
        f"Returning {len(shot_names)} shot(s) from "
        f"{len(target_sequences)} sequence folder(s)."
    )
    return shot_names, start_frames, end_frames, level_paths, has_any_shots
