import unreal


_LOG_PREFIX = "[SetShotShotOrderNumber]"
_PROPERTY_NAME = "ShotOrderNumber"
_FAILURE_VALUE = -1


def _log(message):
    unreal.log(f"{_LOG_PREFIX} {message}")


def _log_error(message):
    unreal.log_error(f"{_LOG_PREFIX} {message}")


def _log_return(value):
    _log(f"Returning value: {value!r}")
    return value


def _sanitize_name(value, label):
    if not isinstance(value, str):
        _log_error(
            f"Invalid {label}: expected string, got {type(value).__name__}"
        )
        return None

    cleaned = value.strip()
    if not cleaned:
        _log_error(f"Invalid {label}: value is empty")
        return None

    if "/" in cleaned or "\\" in cleaned or "." in cleaned:
        _log_error(
            f"Invalid {label}: contains unsupported path characters: {cleaned!r}"
        )
        return None

    return cleaned


def _coerce_shot_order_number(value):
    if isinstance(value, bool):
        _log_error(
            f"Invalid {_PROPERTY_NAME}: expected int, got bool ({value!r})"
        )
        return None

    try:
        return int(str(value).strip())
    except Exception as exc:
        _log_error(
            f"Invalid {_PROPERTY_NAME}: expected int-compatible value, "
            f"got {value!r}. Error: {exc}"
        )
        return None


def _build_shot_data_asset_path(show_name, sequence_name, shot_name):
    normalized_show_name = show_name[1:] if show_name.startswith("_") else show_name

    shot_folder_path = (
        f"/Game/_{normalized_show_name}/Sequences/"
        f"{sequence_name}/{shot_name}"
    )

    asset_name = f"{shot_name}_Data"
    return f"{shot_folder_path}/{asset_name}.{asset_name}"


def run(show_name, sequence_name, shot_name, shot_order_number):
    _log("----- run() called -----")
    _log(f"Input show_name: {show_name!r}")
    _log(f"Input sequence_name: {sequence_name!r}")
    _log(f"Input shot_name: {shot_name!r}")
    _log(f"Input shot_order_number: {shot_order_number!r}")

    clean_show_name = _sanitize_name(show_name, "show_name")
    clean_sequence_name = _sanitize_name(sequence_name, "sequence_name")
    clean_shot_name = _sanitize_name(shot_name, "shot_name")
    clean_shot_order_number = _coerce_shot_order_number(shot_order_number)

    _log(f"Sanitized show_name: {clean_show_name!r}")
    _log(f"Sanitized sequence_name: {clean_sequence_name!r}")
    _log(f"Sanitized shot_name: {clean_shot_name!r}")
    _log(f"Sanitized shot_order_number: {clean_shot_order_number!r}")

    if (
        clean_show_name is None
        or clean_sequence_name is None
        or clean_shot_name is None
        or clean_shot_order_number is None
    ):
        _log_error("Input validation failed.")
        return _log_return(_FAILURE_VALUE)

    normalized_show_name = (
        clean_show_name[1:] if clean_show_name.startswith("_") else clean_show_name
    )

    _log(f"Normalized show_name for path building: {normalized_show_name!r}")

    asset_path = _build_shot_data_asset_path(
        clean_show_name,
        clean_sequence_name,
        clean_shot_name,
    )

    _log(f"Resolved data asset object path: {asset_path}")

    shot_data_asset = unreal.load_asset(asset_path)

    if not shot_data_asset:
        _log_error(f"Asset not found or failed to load: {asset_path}")
        return _log_return(_FAILURE_VALUE)

    _log(f"Loaded asset object: {shot_data_asset}")

    try:
        loaded_asset_path = shot_data_asset.get_path_name()
    except Exception as exc:
        loaded_asset_path = None
        _log_error(f"Could not query loaded asset path: {exc}")

    _log(f"Loaded data asset file location: {loaded_asset_path!r}")

    try:
        current_shot_order_number = shot_data_asset.get_editor_property(_PROPERTY_NAME)
        _log(f"Current asset {_PROPERTY_NAME} before set: {current_shot_order_number!r}")
    except Exception as exc:
        _log_error(f"Asset does not expose {_PROPERTY_NAME} property: {exc}")
        return _log_return(_FAILURE_VALUE)

    try:
        shot_data_asset.set_editor_property(_PROPERTY_NAME, clean_shot_order_number)
        _log(f"Set {_PROPERTY_NAME} to: {clean_shot_order_number!r}")
    except Exception as exc:
        _log_error(f"Failed to set {_PROPERTY_NAME}: {exc}")
        return _log_return(_FAILURE_VALUE)

    try:
        updated_shot_order_number = shot_data_asset.get_editor_property(_PROPERTY_NAME)
        _log(f"Asset {_PROPERTY_NAME} after set, before save: {updated_shot_order_number!r}")
    except Exception as exc:
        _log_error(f"Failed reading {_PROPERTY_NAME} after set: {exc}")
        return _log_return(_FAILURE_VALUE)

    save_ok = unreal.EditorAssetLibrary.save_loaded_asset(shot_data_asset)
    _log(f"Save result: {save_ok!r}")

    if not save_ok:
        _log_error(f"Failed to save asset: {asset_path}")
        return _log_return(_FAILURE_VALUE)

    try:
        final_shot_order_number = int(
            shot_data_asset.get_editor_property(_PROPERTY_NAME)
        )
        _log(f"Final asset {_PROPERTY_NAME} after save: {final_shot_order_number!r}")
    except Exception as exc:
        _log_error(f"Failed reading final {_PROPERTY_NAME} after save: {exc}")
        return _log_return(_FAILURE_VALUE)

    return _log_return(final_shot_order_number)


if __name__ == "__main__":
    _log("Module loaded. Call run(show_name, sequence_name, shot_name, shot_order_number).")
