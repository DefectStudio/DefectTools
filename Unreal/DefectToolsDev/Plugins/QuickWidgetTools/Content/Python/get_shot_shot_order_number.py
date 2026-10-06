import unreal


_LOG_PREFIX = "[GetShotShotOrderNumber]"
_PROPERTY_NAME = "ShotOrderNumber"
_FAILURE_VALUE = -1


def _log_error(message):
    unreal.log_error(f"{_LOG_PREFIX} {message}")


def _sanitize_name(value, label):
    if not isinstance(value, str):
        _log_error(f"Invalid {label}: expected string, got {type(value).__name__}")
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


def _build_shot_data_asset_path(show_name, sequence_name, shot_name):
    normalized_show_name = show_name[1:] if show_name.startswith("_") else show_name

    shot_folder_path = (
        f"/Game/_{normalized_show_name}/Sequences/"
        f"{sequence_name}/{shot_name}"
    )

    asset_name = f"{shot_name}_Data"
    return f"{shot_folder_path}/{asset_name}.{asset_name}"


def run(show_name, sequence_name, shot_name):
    clean_show_name = _sanitize_name(show_name, "show_name")
    clean_sequence_name = _sanitize_name(sequence_name, "sequence_name")
    clean_shot_name = _sanitize_name(shot_name, "shot_name")

    if (
        clean_show_name is None
        or clean_sequence_name is None
        or clean_shot_name is None
    ):
        _log_error("Input validation failed.")
        return _FAILURE_VALUE

    asset_object_path = _build_shot_data_asset_path(
        clean_show_name,
        clean_sequence_name,
        clean_shot_name,
    )

    shot_data_asset = unreal.load_asset(asset_object_path)

    if not shot_data_asset:
        _log_error(f"Asset not found or failed to load: {asset_object_path}")
        return _FAILURE_VALUE

    try:
        shot_order_number = shot_data_asset.get_editor_property(_PROPERTY_NAME)
    except Exception as exc:
        _log_error(f"Asset does not expose {_PROPERTY_NAME} property: {exc}")
        return _FAILURE_VALUE

    if isinstance(shot_order_number, bool):
        _log_error(
            f"{_PROPERTY_NAME} value is bool, expected int. Value: {shot_order_number!r}"
        )
        return _FAILURE_VALUE

    try:
        return int(shot_order_number)
    except Exception as exc:
        _log_error(
            f"{_PROPERTY_NAME} value could not be converted to int. "
            f"Type: {type(shot_order_number).__name__}, Value: {shot_order_number!r}, Error: {exc}"
        )
        return _FAILURE_VALUE
