import unreal


_LOG_PREFIX = "[GetShotLevelAssociation]"
_LEVEL_PATH_STRING_PROPERTY_NAME = "AssociatedLevelPathString"


def _log(message):
    unreal.log(f"{_LOG_PREFIX} {message}")


def _log_error(message):
    unreal.log_error(f"{_LOG_PREFIX} {message}")


def _sanitize_show_name(show_name):
    if not isinstance(show_name, str):
        _log_error(
            f"Invalid show_name: expected string, got {type(show_name).__name__}"
        )
        return ""

    cleaned = show_name.strip().strip("/")
    if cleaned.startswith("_"):
        cleaned = cleaned[1:]

    if not cleaned:
        _log_error("Invalid show_name: value is empty after sanitization")
        return ""

    return cleaned


def _sanitize_sequence_name(sequence_name):
    if not isinstance(sequence_name, str):
        _log_error(
            f"Invalid sequence_name: expected string, got {type(sequence_name).__name__}"
        )
        return ""

    cleaned = sequence_name.strip().strip("/")
    if not cleaned:
        _log_error("Invalid sequence_name: value is empty after sanitization")
        return ""

    return cleaned


def _sanitize_shot_name(shot_name):
    if not isinstance(shot_name, str):
        _log_error(
            f"Invalid shot_name: expected string, got {type(shot_name).__name__}"
        )
        return ""

    cleaned = shot_name.strip().strip("/")
    if not cleaned:
        _log_error("Invalid shot_name: value is empty after sanitization")
        return ""

    return cleaned


def _build_shot_folder_path(show_name, sequence_name, shot_name):
    return f"/Game/_{show_name}/Sequences/{sequence_name}/{shot_name}"


def _build_expected_data_asset_path(shot_folder_path, shot_name):
    asset_name = f"{shot_name}_Data"
    return f"{shot_folder_path}/{asset_name}.{asset_name}"


def _load_data_asset(data_asset_object_path):
    if not unreal.EditorAssetLibrary.does_asset_exist(data_asset_object_path):
        _log(f"Expected shot data asset does not exist: {data_asset_object_path}")
        return None

    loaded = unreal.load_asset(data_asset_object_path)
    if not loaded:
        _log_error(f"Failed to load expected shot data asset: {data_asset_object_path}")
        return None

    _log(f"Loaded expected shot data asset: {data_asset_object_path}")
    return loaded


def _find_fallback_data_asset_in_folder(shot_folder_path, shot_name):
    if not unreal.EditorAssetLibrary.does_directory_exist(shot_folder_path):
        _log_error(f"Shot folder does not exist: {shot_folder_path}")
        return None

    asset_paths = unreal.EditorAssetLibrary.list_assets(
        shot_folder_path,
        recursive=False,
        include_folder=False,
    )

    if not asset_paths:
        _log(f"No assets found in shot folder: {shot_folder_path}")
        return None

    preferred_name = f"{shot_name}_Data"
    exact_match_path = None
    fallback_candidate_path = None

    for asset_path in asset_paths:
        leaf = asset_path.rsplit("/", 1)[-1]
        asset_name = leaf.split(".", 1)[0]

        if asset_name == preferred_name:
            exact_match_path = asset_path
            break

        if asset_name.endswith("_Data") and fallback_candidate_path is None:
            fallback_candidate_path = asset_path

    selected_path = exact_match_path or fallback_candidate_path
    if not selected_path:
        _log(
            "No fallback shot data asset candidates found in folder. "
            f"Expected naming like '{preferred_name}'."
        )
        return None

    _log(f"Using fallback shot data asset candidate: {selected_path}")

    loaded = unreal.load_asset(selected_path)
    if not loaded:
        _log_error(f"Failed to load fallback shot data asset candidate: {selected_path}")
        return None

    return loaded


def _get_level_path_string_value(shot_data_asset):
    try:
        value = shot_data_asset.get_editor_property(_LEVEL_PATH_STRING_PROPERTY_NAME)
    except Exception as exc:
        _log_error(
            f"Shot data asset does not expose {_LEVEL_PATH_STRING_PROPERTY_NAME}: {exc}"
        )
        return None

    _log(f"Read level association using property '{_LEVEL_PATH_STRING_PROPERTY_NAME}'.")
    return value


def _convert_level_value_to_asset_path(level_value):
    if level_value is None:
        _log("Level path string value is unset (None).")
        return ""

    cleaned = str(level_value or "").strip().strip("\"'")
    if not cleaned or cleaned in ("None", "null"):
        _log("Level path string is empty.")
        return ""

    if cleaned.startswith("SoftObjectPath(") and cleaned.endswith(")"):
        cleaned = cleaned[len("SoftObjectPath(") : -1].strip().strip("\"'")

    cleaned = cleaned.replace("\\", "/")
    while "//" in cleaned:
        cleaned = cleaned.replace("//", "/")

    if cleaned.endswith(".umap"):
        cleaned = cleaned[:-5]

    return cleaned


def run(show_name, sequence_name, shot_name):
    _log("----- run() called -----")
    _log(f"Input show_name: {show_name!r}")
    _log(f"Input sequence_name: {sequence_name!r}")
    _log(f"Input shot_name: {shot_name!r}")

    clean_show_name = _sanitize_show_name(show_name)
    clean_sequence_name = _sanitize_sequence_name(sequence_name)
    clean_shot_name = _sanitize_shot_name(shot_name)

    _log(f"Sanitized show_name: {clean_show_name!r}")
    _log(f"Sanitized sequence_name: {clean_sequence_name!r}")
    _log(f"Sanitized shot_name: {clean_shot_name!r}")

    if not clean_show_name or not clean_sequence_name or not clean_shot_name:
        _log_error("Input validation failed. Returning empty string.")
        return ""

    try:
        shot_folder_path = _build_shot_folder_path(
            clean_show_name,
            clean_sequence_name,
            clean_shot_name,
        )
        expected_data_asset_path = _build_expected_data_asset_path(
            shot_folder_path,
            clean_shot_name,
        )

        _log(f"Resolved shot folder path: {shot_folder_path}")
        _log(f"Resolved expected data asset path: {expected_data_asset_path}")

        shot_data_asset = _load_data_asset(expected_data_asset_path)

        if not shot_data_asset:
            _log("Trying fallback search in shot folder.")
            shot_data_asset = _find_fallback_data_asset_in_folder(
                shot_folder_path,
                clean_shot_name,
            )

        if not shot_data_asset:
            _log_error("No valid shot data asset found. Returning empty string.")
            return ""

        level_value = _get_level_path_string_value(shot_data_asset)
        if level_value is None:
            return ""

        level_path = _convert_level_value_to_asset_path(level_value)
        if not level_path:
            _log("Level path string is unset or invalid. Returning empty string.")
            return ""

        _log(f"Returning level path: {level_path}")
        return level_path

    except Exception as exc:
        _log_error(f"Unexpected error while reading level path string: {exc}")
        return ""


if __name__ == "__main__":
    _log("Module loaded. Call run(show_name, sequence_name, shot_name).")
