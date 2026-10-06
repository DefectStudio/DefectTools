import unreal


_LOG_PREFIX = "[GetShotActiveState]"


def _log(message):
    unreal.log(f"{_LOG_PREFIX} {message}")


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


def _build_asset_object_path(sequence_folder_path, shot_name):
    shot_folder_path = f"{sequence_folder_path}/{shot_name}"
    asset_name = f"{shot_name}_Data"
    return f"{shot_folder_path}/{asset_name}.{asset_name}"


def _read_active_state(asset_object_path, log_missing=True):
    shot_data_asset = unreal.load_asset(asset_object_path)

    if not shot_data_asset:
        if log_missing:
            _log_error(f"Asset not found or failed to load: {asset_object_path}")
        return None

    try:
        is_active = shot_data_asset.get_editor_property("IsActive")
    except Exception as exc:
        _log_error(
            f"Asset does not expose IsActive property: {asset_object_path}: {exc}"
        )
        return None

    if not isinstance(is_active, bool):
        _log_error(
            "IsActive value is not bool. "
            f"Asset: {asset_object_path}, "
            f"Type: {type(is_active).__name__}, Value: {is_active!r}"
        )
        return None

    return is_active


def _get_all_sequence_folders(sequences_root):
    editor_asset_lib = unreal.EditorAssetLibrary
    asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
    sub_paths = asset_registry.get_sub_paths(sequences_root, recurse=False)
    sequence_folders = []

    for sub_path in sorted(str(path) for path in sub_paths):
        sequenceholder_path = f"{sub_path}/_sequenceholder"
        if not editor_asset_lib.does_asset_exist(sequenceholder_path):
            continue

        sequence_name = sub_path.rstrip("/").rsplit("/", 1)[-1]
        if sequence_name:
            sequence_folders.append((sub_path, sequence_name))

    return sequence_folders


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
        return False

    normalized_show_name = (
        clean_show_name[1:] if clean_show_name.startswith("_") else clean_show_name
    )
    sequences_root = f"/Game/_{normalized_show_name}/Sequences"

    if clean_sequence_name.upper() != "ALL":
        sequence_folder_path = f"{sequences_root}/{clean_sequence_name}"
        asset_object_path = _build_asset_object_path(
            sequence_folder_path,
            clean_shot_name,
        )
        is_active = _read_active_state(asset_object_path, log_missing=True)
        return is_active if is_active is not None else False

    editor_asset_lib = unreal.EditorAssetLibrary
    if not editor_asset_lib.does_directory_exist(sequences_root):
        _log_error(f"Sequences root does not exist: {sequences_root}")
        return False

    sequence_folders = _get_all_sequence_folders(sequences_root)
    _log(
        f"ALL mode searching {len(sequence_folders)} valid sequence folder(s) "
        f"for shot '{clean_shot_name}'."
    )

    for sequence_folder_path, found_sequence_name in sequence_folders:
        asset_object_path = _build_asset_object_path(
            sequence_folder_path,
            clean_shot_name,
        )
        is_active = _read_active_state(asset_object_path, log_missing=False)

        if is_active is not None:
            _log(
                f"Found shot '{clean_shot_name}' in sequence "
                f"'{found_sequence_name}'. IsActive={is_active}"
            )
            return is_active

    _log_error(
        f"Shot data asset for '{clean_shot_name}' was not found in any valid "
        f"sequence folder under {sequences_root}."
    )
    return False
