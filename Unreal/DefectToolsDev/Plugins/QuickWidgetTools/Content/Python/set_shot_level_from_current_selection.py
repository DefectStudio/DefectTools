import unreal


_LOG_PREFIX = "[SetShotLevelFromCurrentSelection]"
_PATH_STRING_PROPERTY_NAME = "AssociatedLevelPathString"


def _log(message):
    unreal.log(f"{_LOG_PREFIX} {message}")


def _log_error(message):
    unreal.log_error(f"{_LOG_PREFIX} {message}")


def _sanitize_show_name(show_name):
    return "".join(ch for ch in str(show_name or "") if ch.isalnum())


def _sanitize_sequence_name(sequence_name):
    cleaned = "".join(
        ch for ch in str(sequence_name or "").strip().strip("/") if ch.isalnum() or ch == "_"
    )
    return cleaned.upper()


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


def _to_package_path(path_value):
    value = _clean_path_text(path_value)
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


def _get_single_selected_asset():
    selected_assets = unreal.EditorUtilityLibrary.get_selected_assets()
    count = len(selected_assets)
    _log(f"Selection count: {count}")

    if count != 1:
        _log_error("Expected exactly one selected asset in Content Browser.")
        return None

    return selected_assets[0]


def _convert_selected_asset_to_path(selected_asset):
    if not selected_asset:
        return ""

    for getter_name in ("get_path_name", "get_soft_object_path"):
        getter = getattr(selected_asset, getter_name, None)
        if callable(getter):
            try:
                raw_value = getter()
                if isinstance(raw_value, str):
                    cleaned = raw_value.strip()
                    if cleaned:
                        return cleaned
                else:
                    as_text = str(raw_value).strip()
                    if as_text:
                        return as_text
            except Exception:
                pass

    try:
        path_name = unreal.SystemLibrary.get_path_name(selected_asset)
        if isinstance(path_name, str) and path_name.strip():
            return path_name.strip()
    except Exception:
        pass

    return ""


def _is_valid_level_selection(selected_asset, selected_asset_path):
    if not selected_asset:
        _log_error("Selected asset is invalid.")
        return False

    asset_class = None
    class_name = "Unknown"

    try:
        asset_class = selected_asset.get_class()
        class_name = asset_class.get_name()
    except Exception:
        try:
            class_name = type(selected_asset).__name__
        except Exception:
            class_name = "Unknown"

    _log(f"Selected asset class: {class_name}")

    is_world_class = False
    try:
        world_class = unreal.World.static_class()
        if asset_class and unreal.SystemLibrary.is_valid_class(asset_class):
            is_world_class = unreal.SystemLibrary.class_is_child_of(asset_class, world_class)
    except Exception:
        is_world_class = isinstance(selected_asset, unreal.World)

    if is_world_class:
        return True

    path_lower = (selected_asset_path or "").lower()
    if path_lower.endswith(".umap") or "/maps/" in path_lower:
        _log(
            "Selected asset is not a World object instance, but path looks map-like; allowing as practical fallback."
        )
        return True

    _log_error(f"Selected asset is not a World/map asset. Class: {class_name}")
    return False


def _find_fallback_data_asset_in_folder(shot_folder_path, shot_name):
    if not unreal.EditorAssetLibrary.does_directory_exist(shot_folder_path):
        _log_error(f"Shot folder does not exist: {shot_folder_path}")
        return None, ""

    asset_paths = unreal.EditorAssetLibrary.list_assets(
        shot_folder_path,
        recursive=False,
        include_folder=False,
    )

    if not asset_paths:
        _log_error(f"No assets found in shot folder for fallback search: {shot_folder_path}")
        return None, ""

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
        _log_error(f"No *_Data asset candidate found in shot folder: {shot_folder_path}")
        return None, ""

    loaded = unreal.load_asset(selected_path)
    if not loaded:
        _log_error(f"Failed to load fallback data asset: {selected_path}")
        return None, ""

    _log(f"Loaded fallback data asset: {selected_path}")
    return loaded, selected_path


def _load_target_data_asset(shot_folder_path, shot_name):
    expected_path = _build_expected_data_asset_path(shot_folder_path, shot_name)
    _log(f"Resolved data asset path: {expected_path}")

    if unreal.EditorAssetLibrary.does_asset_exist(expected_path):
        loaded = unreal.load_asset(expected_path)
        if loaded:
            _log(f"Loaded expected data asset: {expected_path}")
            return loaded, expected_path

        _log_error(f"Expected data asset exists but failed to load: {expected_path}")
    else:
        _log(f"Expected data asset does not exist: {expected_path}")

    _log("Attempting fallback data asset lookup in shot folder.")
    return _find_fallback_data_asset_in_folder(shot_folder_path, shot_name)


def _get_current_path_string_value(shot_data_asset):
    try:
        value = shot_data_asset.get_editor_property(_PATH_STRING_PROPERTY_NAME)
    except Exception:
        return None

    return str(value or "").strip()


def _set_path_string_value(shot_data_asset, package_path):
    try:
        shot_data_asset.set_editor_property(_PATH_STRING_PROPERTY_NAME, package_path)
        _log(f"Set {_PATH_STRING_PROPERTY_NAME}: {package_path}")
        return True
    except Exception as exc:
        _log_error(f"Failed to set {_PATH_STRING_PROPERTY_NAME}: {exc}")
        return False


def run(show_name, sequence_name, shot_name):
    _log("----- run() called -----")
    _log(f"Raw input show_name: {show_name!r}")
    _log(f"Raw input sequence_name: {sequence_name!r}")
    _log(f"Raw input shot_name: {shot_name!r}")

    try:
        clean_show_name = _sanitize_show_name(show_name)
        clean_sequence_name = _sanitize_sequence_name(sequence_name)
        clean_shot_name = _sanitize_shot_name(shot_name)

        _log(f"Sanitized show_name: {clean_show_name!r}")
        _log(f"Sanitized sequence_name: {clean_sequence_name!r}")
        _log(f"Sanitized shot_name: {clean_shot_name!r}")

        if not clean_show_name or not clean_sequence_name or not clean_shot_name:
            _log_error("Input sanitization produced empty required value(s).")
            _log("Returned path: ''")
            return ""

        selected_asset = _get_single_selected_asset()
        if not selected_asset:
            _log("Returned path: ''")
            return ""

        selected_asset_path = _convert_selected_asset_to_path(selected_asset)
        selected_package_path = _to_package_path(selected_asset_path)
        _log(f"Selected asset path: {selected_asset_path!r}")
        _log(f"Selected package path: {selected_package_path!r}")

        if not selected_asset_path or not selected_package_path:
            _log_error("Failed to convert selected asset to a usable level path string.")
            _log("Returned path: ''")
            return ""

        if not _is_valid_level_selection(selected_asset, selected_asset_path):
            _log("Returned path: ''")
            return ""

        shot_folder_path = _build_shot_folder_path(
            clean_show_name,
            clean_sequence_name,
            clean_shot_name,
        )
        _log(f"Resolved shot folder path: {shot_folder_path}")

        shot_data_asset, resolved_data_asset_path = _load_target_data_asset(
            shot_folder_path,
            clean_shot_name,
        )

        if not shot_data_asset:
            _log_error("Unable to load target shot data asset.")
            _log("Returned path: ''")
            return ""

        _log(f"Resolved data asset path: {resolved_data_asset_path}")

        current_path_string = _get_current_path_string_value(shot_data_asset)
        if current_path_string is None:
            _log_error(f"Shot data asset does not expose {_PATH_STRING_PROPERTY_NAME}.")
            _log("Returned path: ''")
            return ""

        current_package_path = _to_package_path(current_path_string)
        _log(f"Current {_PATH_STRING_PROPERTY_NAME}: {current_path_string!r}")
        _log(f"Current package path: {current_package_path!r}")
        _log(f"Incoming package path: {selected_package_path!r}")

        if current_package_path == selected_package_path:
            _log("Path compare result: matched")
            _log(f"Update skipped: existing {_PATH_STRING_PROPERTY_NAME} already matches.")
            _log(f"Returned path: {selected_package_path!r}")
            return selected_package_path

        if not _set_path_string_value(shot_data_asset, selected_package_path):
            _log("Returned path: ''")
            return ""

        save_result = unreal.EditorAssetLibrary.save_loaded_asset(shot_data_asset)
        _log(f"Save result: {save_result!r}")

        if not save_result:
            _log_error("Failed to save shot data asset after setting level path string.")
            _log("Returned path: ''")
            return ""

        _log(f"Returned path: {selected_package_path!r}")
        return selected_package_path

    except Exception as exc:
        _log_error(f"Unhandled error in run(): {exc}")
        _log("Returned path: ''")
        return ""


if __name__ == "__main__":
    _log("Module loaded. Call run(show_name, sequence_name, shot_name).")
