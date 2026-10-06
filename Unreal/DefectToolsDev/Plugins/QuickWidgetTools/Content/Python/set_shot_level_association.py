import unreal


_LOG_PREFIX = "[SetShotLevelAssociation]"
_PATH_STRING_PROPERTY_NAME = "AssociatedLevelPathString"


def _log(message):
    unreal.log(f"{_LOG_PREFIX} {message}")


def _log_error(message):
    unreal.log_error(f"{_LOG_PREFIX} {message}")


def _sanitize_show_name(show_name):
    cleaned = "".join(ch for ch in str(show_name or "").strip().strip("/") if ch.isalnum())
    if cleaned.startswith("_"):
        cleaned = cleaned[1:]
    return cleaned


def _sanitize_sequence_name(sequence_name):
    return "".join(
        ch for ch in str(sequence_name or "").strip().strip("/") if ch.isalnum() or ch == "_"
    )


def _sanitize_shot_name(shot_name):
    return "".join(
        ch for ch in str(shot_name or "").strip().strip("/") if ch.isalnum() or ch == "_"
    )


def _clean_path_text(path_value):
    value = str(path_value or "").strip().strip("\"'")
    if not value or value in ("None", "null"):
        return ""

    for prefix in ("SoftObjectPath(", "TopLevelAssetPath("):
        if value.startswith(prefix) and value.endswith(")"):
            value = value[len(prefix): -1].strip().strip("\"'")
            break

    value = value.replace("\\", "/")
    while "//" in value:
        value = value.replace("//", "/")

    if value.endswith(".umap"):
        value = value[:-5]

    if ":" in value:
        value = value.split(":", 1)[0]

    if len(value) > 1:
        value = value.rstrip("/")

    return value


def _to_package_path(level_path):
    value = _clean_path_text(level_path)
    if not value:
        return ""

    # Convert a full object path like /Game/Maps/MyMap.MyMap to the package path
    # stored in AssociatedLevelPathString: /Game/Maps/MyMap
    parent_path, separator, leaf = value.rpartition("/")
    if "." in leaf:
        leaf = leaf.split(".", 1)[0]
        value = f"{parent_path}{separator}{leaf}" if parent_path else leaf

    return value


def _build_shot_folder_path(show_name, sequence_name, shot_name):
    return f"/Game/_{show_name}/Sequences/{sequence_name}/{shot_name}"


def _build_expected_data_asset_path(shot_folder_path, shot_name):
    asset_name = f"{shot_name}_Data"
    return f"{shot_folder_path}/{asset_name}.{asset_name}"


def _load_data_asset(data_asset_object_path):
    if not unreal.EditorAssetLibrary.does_asset_exist(data_asset_object_path):
        return None

    return unreal.load_asset(data_asset_object_path)


def _find_fallback_data_asset_in_folder(shot_folder_path, shot_name):
    if not unreal.EditorAssetLibrary.does_directory_exist(shot_folder_path):
        return None

    asset_paths = unreal.EditorAssetLibrary.list_assets(
        shot_folder_path,
        recursive=False,
        include_folder=False,
    )

    preferred_name = f"{shot_name}_Data"
    exact_match_path = ""
    fallback_candidate_path = ""

    for asset_path in asset_paths:
        leaf = asset_path.rsplit("/", 1)[-1]
        asset_name = leaf.split(".", 1)[0]

        if asset_name == preferred_name:
            exact_match_path = asset_path
            break

        if asset_name.endswith("_Data") and not fallback_candidate_path:
            fallback_candidate_path = asset_path

    selected_path = exact_match_path or fallback_candidate_path
    if not selected_path:
        return None

    return unreal.load_asset(selected_path)


def _get_current_path_string_value(shot_data_asset):
    try:
        value = shot_data_asset.get_editor_property(_PATH_STRING_PROPERTY_NAME)
    except Exception:
        return None

    return str(value or "").strip()


def _set_path_string_value(shot_data_asset, package_path):
    try:
        shot_data_asset.set_editor_property(_PATH_STRING_PROPERTY_NAME, package_path)
        return True
    except Exception as exc:
        _log_error(
            f"Failed to set {_PATH_STRING_PROPERTY_NAME}: {exc}"
        )
        return False


def run(show_name, sequence_name, shot_name, level_path):
    _log("----- run() called -----")
    _log(
        "Raw inputs: "
        f"show_name={show_name!r}, sequence_name={sequence_name!r}, "
        f"shot_name={shot_name!r}, level_path={level_path!r}"
    )

    try:
        clean_show_name = _sanitize_show_name(show_name)
        clean_sequence_name = _sanitize_sequence_name(sequence_name)
        clean_shot_name = _sanitize_shot_name(shot_name)
        clean_level_package_path = _to_package_path(level_path)

        _log(
            "Sanitized inputs: "
            f"show_name={clean_show_name!r}, sequence_name={clean_sequence_name!r}, "
            f"shot_name={clean_shot_name!r}, "
            f"level_package_path={clean_level_package_path!r}"
        )

        if not clean_show_name or not clean_sequence_name or not clean_shot_name:
            _log_error("Required sanitized identifiers are empty.")
            _log("Final return value: False")
            return False

        shot_folder_path = _build_shot_folder_path(
            clean_show_name,
            clean_sequence_name,
            clean_shot_name,
        )
        expected_data_asset_path = _build_expected_data_asset_path(
            shot_folder_path,
            clean_shot_name,
        )

        _log(f"Resolved data asset path: {expected_data_asset_path}")

        shot_data_asset = _load_data_asset(expected_data_asset_path)
        if not shot_data_asset:
            _log("Direct data asset load failed. Trying fallback search in shot folder.")
            shot_data_asset = _find_fallback_data_asset_in_folder(
                shot_folder_path,
                clean_shot_name,
            )

        if not shot_data_asset:
            _log_error("Failed to load shot data asset from expected path or fallback search.")
            _log("Final return value: False")
            return False

        current_path_string = _get_current_path_string_value(shot_data_asset)
        if current_path_string is None:
            _log_error(f"Shot data asset does not expose {_PATH_STRING_PROPERTY_NAME}.")
            _log("Final return value: False")
            return False

        current_package_path = _to_package_path(current_path_string)

        _log(f"Current {_PATH_STRING_PROPERTY_NAME}: {current_path_string!r}")
        _log(f"Current package path: {current_package_path!r}")
        _log(f"Incoming package path: {clean_level_package_path!r}")

        if current_package_path == clean_level_package_path:
            _log("Path compare result: matched")
            _log(f"Update skipped: existing {_PATH_STRING_PROPERTY_NAME} already matches.")
            _log("Final return value: True")
            return True

        if not _set_path_string_value(shot_data_asset, clean_level_package_path):
            _log("Final return value: False")
            return False

        _log(f"Update applied: {_PATH_STRING_PROPERTY_NAME} updated.")

        save_result = unreal.EditorAssetLibrary.save_loaded_asset(shot_data_asset)
        _log(f"Save result: {save_result}")

        if not save_result:
            _log_error("Failed to save shot data asset after update.")
            _log("Final return value: False")
            return False

        _log("Final return value: True")
        return True

    except Exception as exc:
        _log_error(f"Unexpected failure: {exc}")
        _log("Final return value: False")
        return False
