import os
import re
import traceback

import unreal


LOG_PREFIX = "[CreateSequence]"

_SETTINGS_FILE_NAME = "QuickWidgetToolsSettings.ini"
_SECTION = "/Script/QuickWidgetTools.RenderToolSettings"
_SHOW_FILE_SERVER_PATH_KEY = "ShowFileServerPath"

_ERROR_DIALOG_TITLE = "Unable to Create Sequence"
_MISSING_SHOW_FOLDER_MESSAGE = (
    "The project show folder has not been configured.\n\n"
    "Open the Initialize Project widget, select the show folder, and then try "
    "creating the sequence again."
)
_GENERIC_CREATION_FAILURE_MESSAGE = (
    "The sequence could not be created.\n\n"
    "Check the Output Log for details and then try again."
)

FILE_SERVER_SEQUENCE_RELATIVE_FOLDER_TEMPLATES = (
    "sequences",
    "sequences/{sequence_name}",
    "sequences/{sequence_name}/_output",
)


def _log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message: str) -> None:
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _show_error_dialog(message: str) -> None:
    try:
        unreal.EditorDialog.show_message(
            _ERROR_DIALOG_TITLE,
            message,
            unreal.AppMsgType.OK,
        )
    except Exception as exc:
        _log_error(f"Could not display the sequence creation error dialog: {exc}")


def _fail(user_message: str, log_message: str = "") -> str:
    if log_message:
        _log_error(log_message)
    _show_error_dialog(user_message)
    return ""


def _sanitize_show_name(show_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", show_name or "")


def _sanitize_sequence_name(sequence_name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9]", "", sequence_name or "")
    return sanitized.upper()


def _normalize_file_path(path_value) -> str:
    value = str(path_value or "").strip()
    if not value:
        return ""
    return value.replace("\\", "/").rstrip("/")


def _find_config_dir(project_dir: str) -> str:
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


def _get_settings_file_path() -> str:
    project_dir = unreal.Paths.project_dir()
    _log(f"Project dir: {project_dir}")

    config_dir = _find_config_dir(project_dir)
    settings_path = os.path.join(config_dir, _SETTINGS_FILE_NAME)
    settings_path = os.path.normpath(settings_path)

    _log(f"Resolved settings file path: {settings_path}")
    return settings_path


def _read_text_file(path: str) -> str:
    if not os.path.exists(path):
        return ""

    with open(path, "r", encoding="utf-8") as file_handle:
        return file_handle.read()


def _find_section_bounds(lines, section_name: str):
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


def _get_section_value(text: str, section_name: str, key: str) -> str:
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


def _get_saved_show_file_server_path() -> str:
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


def _build_file_server_sequence_folders(sequence_name: str):
    relative_folders = []

    for template in FILE_SERVER_SEQUENCE_RELATIVE_FOLDER_TEMPLATES:
        relative_folders.append(template.format(sequence_name=sequence_name))

    return relative_folders


def _create_file_server_folder(path: str) -> str:
    normalized_path = os.path.normpath(path)

    if os.path.isdir(normalized_path):
        _log(f"File-server folder already exists: {normalized_path}")
        return "exists"

    os.makedirs(normalized_path, exist_ok=True)

    if os.path.isdir(normalized_path):
        _log(f"Created file-server folder: {normalized_path}")
        return "created"

    raise RuntimeError(f"Failed to create file-server folder: {normalized_path}")


def _create_file_server_sequence_folders(sequence_name: str, show_root: str) -> str:
    relative_folders = _build_file_server_sequence_folders(sequence_name)

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

    _log(f"File-server folders created: {created_count}")
    _log(f"File-server folders already existing: {existing_count}")
    _log(f"File-server folders missing after create: {len(missing_folders)}")

    if missing_folders:
        for folder_path in missing_folders[:25]:
            _log_error(f"Missing file-server folder: {folder_path}")
        return ""

    sequence_root = os.path.normpath(os.path.join(show_root, "sequences", sequence_name))
    return sequence_root.replace("\\", "/")


def _ensure_folder(folder_path: str) -> bool:
    if unreal.EditorAssetLibrary.does_directory_exist(folder_path):
        _log(f"Folder already exists: {folder_path}")
        return True

    created = unreal.EditorAssetLibrary.make_directory(folder_path)
    if created:
        _log(f"Created folder: {folder_path}")
        return True

    if unreal.EditorAssetLibrary.does_directory_exist(folder_path):
        _log(f"Folder exists after create attempt: {folder_path}")
        return True

    _log_error(f"Failed to create folder: {folder_path}")
    return False


def _create_placeholder_if_missing(sequence_folder: str) -> bool:
    asset_name = "_sequenceholder"
    asset_path = f"{sequence_folder}/{asset_name}"

    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        _log(f"Placeholder already exists: {asset_path}")
        return True

    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.Object)

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    created_asset = asset_tools.create_asset(asset_name, sequence_folder, unreal.Blueprint, factory)

    if created_asset:
        _log(f"Created placeholder Blueprint: {asset_path}")
        return True

    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        _log(f"Placeholder exists after create attempt: {asset_path}")
        return True

    _log_error(f"Failed to create placeholder Blueprint: {asset_path}")
    return False


def run(show_name, sequence_name):
    """
    Create /Game/_[sanitized_show_name]/Sequences/[sanitized_sequence_name]
    and [ShowFileServerPath]/sequences/[sanitized_sequence_name].

    Also creates a Blueprint placeholder named _sequenceholder in the Unreal folder.

    Returns:
        str: Final Unreal sequence folder path on success, or "" on failure.
    """
    try:
        sanitized_show_name = _sanitize_show_name(show_name)
        sanitized_sequence_name = _sanitize_sequence_name(sequence_name)

        if not sanitized_show_name:
            return _fail(
                _GENERIC_CREATION_FAILURE_MESSAGE,
                "Sanitized show name is empty. Aborting.",
            )

        if not sanitized_sequence_name:
            return _fail(
                _GENERIC_CREATION_FAILURE_MESSAGE,
                "Sanitized sequence name is empty. Aborting.",
            )

        show_folder = f"/Game/_{sanitized_show_name}"
        sequences_folder = f"{show_folder}/Sequences"
        sequence_folder = f"{sequences_folder}/{sanitized_sequence_name}"

        _log(f"Resolved show folder: {show_folder}")
        _log(f"Resolved sequence folder: {sequence_folder}")

        show_root = _get_saved_show_file_server_path()
        if not show_root:
            return _fail(_MISSING_SHOW_FOLDER_MESSAGE)

        if not os.path.isdir(show_root):
            return _fail(
                _MISSING_SHOW_FOLDER_MESSAGE,
                f"Saved show file server path does not exist or is not a folder: {show_root}",
            )

        file_server_sequence_folder = _create_file_server_sequence_folders(
            sanitized_sequence_name,
            show_root,
        )
        if not file_server_sequence_folder:
            return _fail(
                _GENERIC_CREATION_FAILURE_MESSAGE,
                "Failed to create file-server sequence folders. Aborting Unreal sequence creation.",
            )

        _log(f"Resolved file-server sequence folder: {file_server_sequence_folder}")

        if not _ensure_folder(show_folder):
            return _fail(_GENERIC_CREATION_FAILURE_MESSAGE)

        if not _ensure_folder(sequences_folder):
            return _fail(_GENERIC_CREATION_FAILURE_MESSAGE)

        if not _ensure_folder(sequence_folder):
            return _fail(_GENERIC_CREATION_FAILURE_MESSAGE)

        if not _create_placeholder_if_missing(sequence_folder):
            return _fail(_GENERIC_CREATION_FAILURE_MESSAGE)

        _log(f"Done Unreal sequence folder: {sequence_folder}")
        _log(f"Done file-server sequence folder: {file_server_sequence_folder}")
        return sequence_folder

    except Exception as exc:
        return _fail(
            _GENERIC_CREATION_FAILURE_MESSAGE,
            f"{exc}\n{traceback.format_exc()}",
        )
