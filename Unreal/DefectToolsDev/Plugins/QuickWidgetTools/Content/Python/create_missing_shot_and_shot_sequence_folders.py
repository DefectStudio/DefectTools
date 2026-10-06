"""
Repair missing file-server sequence and shot folders from the Unreal project structure.

This script scans Unreal sequence folders under:

    /Game/_S3Bishop/Sequences

Then ensures matching file-server folders exist under ShowFileServerPath:

    [ShowFileServerPath]/sequences/[SEQUENCE]
    [ShowFileServerPath]/sequences/[SEQUENCE]/_output
    [ShowFileServerPath]/sequences/[SEQUENCE]/[SHOT]/...

It uses create_shot_file_server_folders.py for the per-shot scaffold so the
repair process stays aligned with the production folder template.

Blueprint / Python usage:

    import create_missing_shot_and_shot_sequence_folders
    import importlib

    importlib.reload(create_missing_shot_and_shot_sequence_folders)

    # Preview only. Does not create folders.
    success = create_missing_shot_and_shot_sequence_folders.run(show_name, True)

    # Create missing folders.
    success = create_missing_shot_and_shot_sequence_folders.run(show_name, False)

Returns:
    "true" on success, or "" on failure.
"""

import os
import re
import traceback

import unreal

import create_shot_file_server_folders


LOG_PREFIX = "[CreateMissingShotAndShotSequenceFolders]"

DEFAULT_SHOW_NAME = "S3Bishop"
DEFAULT_SEQUENCES_ROOT = "/Game/_S3Bishop/Sequences"

_SETTINGS_FILE_NAME = "QuickWidgetToolsSettings.ini"
_SECTION = "/Script/QuickWidgetTools.RenderToolSettings"
_SHOW_FILE_SERVER_PATH_KEY = "ShowFileServerPath"

SHOT_NAME_PATTERN = re.compile(r"^[A-Z0-9]+_\d{3}_\d{4}$")

FILE_SERVER_SEQUENCE_RELATIVE_FOLDER_TEMPLATES = (
    "sequences",
    "sequences/{sequence_name}",
    "sequences/{sequence_name}/_output",
)


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _normalize_file_path(path_value):
    value = str(path_value or "").strip()
    if not value:
        return ""
    return value.replace("\\", "/").rstrip("/")


def _sanitize_show_name(value):
    if value is None:
        return ""
    return str(value).strip()


def _normalize_bool(value):
    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()
    if text in ("false", "0", "no", "off"):
        return False

    return True


def _find_config_dir(project_dir):
    candidates = [
        os.path.join(project_dir, "Saved", "Config", "WindowsEditor"),
        os.path.join(project_dir, "Saved", "Config", "Windows"),
        os.path.join(project_dir, "Saved", "Config"),
    ]

    for folder in candidates:
        _log(f"Checking config folder candidate: {folder}")
        if os.path.isdir(folder):
            _log(f"Using existing config folder: {folder}")
            return folder

    fallback = os.path.join(project_dir, "Saved", "Config", "WindowsEditor")
    _log_warning(f"No candidate config folder existed. Falling back to: {fallback}")
    return fallback


def _get_settings_file_path():
    project_dir = unreal.Paths.project_dir()
    _log(f"Project dir: {project_dir}")

    config_dir = _find_config_dir(project_dir)
    settings_path = os.path.join(config_dir, _SETTINGS_FILE_NAME)
    settings_path = os.path.normpath(settings_path)

    _log(f"Resolved settings file path: {settings_path}")
    return settings_path


def _read_text_file(path):
    if not os.path.exists(path):
        return ""

    with open(path, "r", encoding="utf-8") as file_handle:
        return file_handle.read()


def _find_section_bounds(lines, section_name):
    section_header = f"[{section_name}]"
    section_start = -1
    section_end = len(lines)

    for index, line in enumerate(lines):
        if line.strip() == section_header:
            section_start = index
            break

    if section_start == -1:
        return -1, -1

    for index in range(section_start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section_end = index
            break

    return section_start, section_end


def _get_section_value(text, section_name, key):
    lines = text.splitlines()
    section_start, section_end = _find_section_bounds(lines, section_name)

    if section_start == -1:
        return ""

    prefix = f"{key}="

    for index in range(section_start + 1, section_end):
        stripped = lines[index].strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip()

    return ""


def _get_saved_show_file_server_path():
    settings_path = _get_settings_file_path()

    if not os.path.exists(settings_path):
        _log_error(f"Settings file does not exist yet: {settings_path}")
        return ""

    text = _read_text_file(settings_path)
    saved_path = _get_section_value(text, _SECTION, _SHOW_FILE_SERVER_PATH_KEY)
    saved_path = _normalize_file_path(saved_path)

    if not saved_path:
        _log_error(
            f"Could not find [{_SECTION}] {_SHOW_FILE_SERVER_PATH_KEY} in settings file: {settings_path}"
        )
        return ""

    _log(f"Loaded {_SHOW_FILE_SERVER_PATH_KEY}: {saved_path}")
    return saved_path


def _get_name(asset_path):
    return str(asset_path).rstrip("/").split("/")[-1]


def _get_sub_paths(asset_registry, parent_path):
    try:
        return list(asset_registry.get_sub_paths(parent_path, False))
    except Exception as exc:
        _log_error(f"Could not get sub paths for {parent_path}: {exc}")
        return []


def _is_valid_sequence_name(sequence_name):
    if not sequence_name:
        return False

    if sequence_name.startswith("_"):
        return False

    return bool(re.match(r"^[A-Z0-9]+$", sequence_name))


def _is_valid_shot_folder(sequence_name, shot_name):
    if not shot_name:
        return False

    if shot_name.startswith("_"):
        return False

    if not shot_name.startswith(sequence_name + "_"):
        return False

    return bool(SHOT_NAME_PATTERN.match(shot_name))


def _build_file_server_sequence_folders(sequence_name):
    relative_folders = []

    for template in FILE_SERVER_SEQUENCE_RELATIVE_FOLDER_TEMPLATES:
        relative_folders.append(template.format(sequence_name=sequence_name))

    return relative_folders


def _create_file_server_folder(path):
    normalized_path = os.path.normpath(path)

    if os.path.isdir(normalized_path):
        _log(f"File-server folder already exists: {normalized_path}")
        return "exists"

    os.makedirs(normalized_path, exist_ok=True)

    if os.path.isdir(normalized_path):
        _log(f"Created file-server folder: {normalized_path}")
        return "created"

    raise RuntimeError(f"Failed to create file-server folder: {normalized_path}")


def _ensure_file_server_sequence_folders(show_root, sequence_name, dry_run):
    relative_folders = _build_file_server_sequence_folders(sequence_name)

    if dry_run:
        for relative_folder in relative_folders:
            folder_path = os.path.normpath(os.path.join(show_root, relative_folder))
            _log(f"Would ensure file-server sequence folder: {folder_path}")
        return "true"

    created_count = 0
    existing_count = 0

    for relative_folder in relative_folders:
        folder_path = os.path.join(show_root, relative_folder)
        result = _create_file_server_folder(folder_path)

        if result == "created":
            created_count += 1
        else:
            existing_count += 1

    missing_folders = []

    for relative_folder in relative_folders:
        folder_path = os.path.normpath(os.path.join(show_root, relative_folder))
        if not os.path.isdir(folder_path):
            missing_folders.append(folder_path)

    _log(f"Sequence {sequence_name} file-server folders created: {created_count}")
    _log(f"Sequence {sequence_name} file-server folders already existing: {existing_count}")
    _log(f"Sequence {sequence_name} file-server folders missing after create: {len(missing_folders)}")

    if missing_folders:
        for folder_path in missing_folders[:25]:
            _log_error(f"Missing file-server sequence folder: {folder_path}")
        return ""

    return "true"


def _collect_unreal_sequences_and_shots(sequences_root):
    asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
    sequence_paths = sorted(_get_sub_paths(asset_registry, sequences_root))

    sequence_to_shots = {}

    for sequence_path in sequence_paths:
        sequence_name = _get_name(sequence_path).upper()

        if not _is_valid_sequence_name(sequence_name):
            _log(f"Skipping non-sequence folder: {sequence_path}")
            continue

        shot_names = []
        shot_paths = sorted(_get_sub_paths(asset_registry, sequence_path))

        for shot_path in shot_paths:
            shot_name = _get_name(shot_path).upper()

            if not _is_valid_shot_folder(sequence_name, shot_name):
                _log(f"Skipping non-shot folder: {shot_path}")
                continue

            shot_names.append(shot_name)

        sequence_to_shots[sequence_name] = shot_names

    return sequence_to_shots


def run(show_name=DEFAULT_SHOW_NAME, dry_run=True, sequences_root=DEFAULT_SEQUENCES_ROOT):
    """
    Repair missing file-server sequence folders and shot folders.

    Args:
        show_name (str): Show name to pass into create_shot_file_server_folders.
        dry_run (bool): True prints what would happen. False creates missing folders.
        sequences_root (str): Unreal content folder to scan.

    Returns:
        str: "true" on success, or "" on failure.
    """
    try:
        import importlib
        importlib.reload(create_shot_file_server_folders)

        sanitized_show_name = _sanitize_show_name(show_name)
        dry_run = _normalize_bool(dry_run)
        sequences_root = str(sequences_root or DEFAULT_SEQUENCES_ROOT).rstrip("/")

        if not sanitized_show_name:
            _log_error("show_name was empty after sanitizing.")
            return ""

        _log(f"Scanning Unreal sequence root: {sequences_root}")
        _log(f"Show name: {sanitized_show_name}")
        _log(f"DRY_RUN: {dry_run}")

        show_root = _get_saved_show_file_server_path()
        if not show_root:
            return ""

        if not os.path.isdir(show_root):
            _log_error(f"Saved show file server path does not exist or is not a folder: {show_root}")
            return ""

        sequence_to_shots = _collect_unreal_sequences_and_shots(sequences_root)

        if not sequence_to_shots:
            _log_error(f"No valid sequence folders found under: {sequences_root}")
            return ""

        sequence_count = len(sequence_to_shots)
        shot_count = sum(len(shot_names) for shot_names in sequence_to_shots.values())

        _log(f"Found sequence folders in Unreal: {sequence_count}")
        _log(f"Found shot folders in Unreal: {shot_count}")
        _log(f"Using show file server path: {show_root}")

        sequence_failures = []
        shot_failures = []

        for sequence_name in sorted(sequence_to_shots.keys()):
            _log(f"Ensuring sequence folder scaffold: {sequence_name}")

            sequence_result = _ensure_file_server_sequence_folders(
                show_root,
                sequence_name,
                dry_run,
            )

            if sequence_result != "true":
                sequence_failures.append(sequence_name)
                continue

            for shot_name in sorted(sequence_to_shots[sequence_name]):
                if dry_run:
                    _log(f"Would ensure file-server shot folders for: {sequence_name}/{shot_name}")
                    continue

                _log(f"Ensuring file-server shot folders for: {sequence_name}/{shot_name}")

                shot_result = create_shot_file_server_folders.run(
                    sanitized_show_name,
                    sequence_name,
                    shot_name,
                )

                if shot_result != "true":
                    shot_failures.append(f"{sequence_name}/{shot_name}")
                    _log_error(f"Failed shot folder repair: {sequence_name}/{shot_name}")

        _log(f"Sequence folders processed: {sequence_count}")
        _log(f"Shot folders processed: {shot_count}")
        _log(f"Sequence failures: {len(sequence_failures)}")
        _log(f"Shot failures: {len(shot_failures)}")

        if sequence_failures:
            for sequence_name in sequence_failures:
                _log_error(f"Failed sequence folder repair: {sequence_name}")

        if shot_failures:
            for shot_name in shot_failures:
                _log_error(f"Failed shot folder repair: {shot_name}")

        if dry_run:
            _log("Dry run complete. Run again with dry_run=False to create missing folders.")
            return "true"

        if sequence_failures or shot_failures:
            _log_error("Repair completed with failures.")
            return ""

        _log("Repair complete. Failures: 0")
        return "true"

    except Exception as exc:
        _log_error(str(exc))
        _log_error(traceback.format_exc())
        return ""
