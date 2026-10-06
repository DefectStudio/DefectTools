"""
Load the render output folder for the current Unreal project.

Reads from:
    <Project>/Saved/Config/WindowsEditor/QuickWidgetToolsSettings.ini

Preferred source:
    ShowFileServerPath + "/sequences"

If ShowFileServerPath is set, this script returns that derived render output path
and synchronizes OutputPath to the same value. If ShowFileServerPath is missing,
it falls back to the saved OutputPath value.

Intended for use from an Execute Python Script node.

Blueprint usage:
    import get_outputFolder
    import importlib
    importlib.reload(get_outputFolder)
    output_path = get_outputFolder.run()

Returns:
    The resolved output path as a string, or "" if not found.
"""

import os
import unreal


_LOG_PREFIX = "[GetOutputFolder]"
_SETTINGS_FILE_NAME = "QuickWidgetToolsSettings.ini"
_SECTION = "/Script/QuickWidgetTools.RenderToolSettings"
_OUTPUT_KEY = "OutputPath"
_SHOW_FILE_SERVER_PATH_KEY = "ShowFileServerPath"


def _log(message):
    unreal.log(f"{_LOG_PREFIX} {message}")


def _log_warning(message):
    unreal.log_warning(f"{_LOG_PREFIX} Warning: {message}")


def _log_error(message):
    unreal.log_error(f"{_LOG_PREFIX} Error: {message}")


def _normalize_path(path_value):
    value = str(path_value or "").strip()
    if not value:
        return ""

    value = value.replace("\\", "/")
    while "//" in value:
        value = value.replace("//", "/")

    return value.rstrip("/")


def _derive_output_path_from_show_file_server_path(show_file_server_path):
    base_path = _normalize_path(show_file_server_path)
    if not base_path:
        return ""

    return f"{base_path}/sequences"


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
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_text_file(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _collect_section_headers(lines, max_count=20):
    headers = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            headers.append(stripped)
            if len(headers) >= max_count:
                break
    return headers


def _find_section_bounds(lines, section_name):
    section_header = f"[{section_name}]"
    section_start = -1
    section_end = len(lines)

    for i, line in enumerate(lines):
        if line.strip() == section_header:
            section_start = i
            break

    if section_start == -1:
        return -1, -1

    for i in range(section_start + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section_end = i
            break

    return section_start, section_end


def _get_section_value(text, section_name, key):
    lines = text.splitlines()
    section_start, section_end = _find_section_bounds(lines, section_name)
    if section_start == -1:
        return "", -1, -1

    prefix = f"{key}="
    for i in range(section_start + 1, section_end):
        stripped = lines[i].strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip(), section_start, i

    return "", section_start, -1


def _upsert_section_key(existing_text, section_name, key, value):
    lines = existing_text.splitlines()
    section_header = f"[{section_name}]"
    new_key_line = f"{key}={value}"

    section_start, section_end = _find_section_bounds(lines, section_name)

    if section_start == -1:
        _log(f"Section not found. Appending new section: {section_header}")
        if existing_text and not existing_text.endswith("\n"):
            existing_text += "\n"
        if existing_text and not existing_text.endswith("\n\n"):
            existing_text += "\n"
        existing_text += f"{section_header}\n{new_key_line}\n"
        return existing_text

    prefix = f"{key}="
    for i in range(section_start + 1, section_end):
        stripped = lines[i].strip()
        if stripped.startswith(prefix):
            if lines[i] != new_key_line:
                _log(f"Updating {key} on line {i + 1}.")
                lines[i] = new_key_line
            return "\n".join(lines) + "\n"

    _log(f"Adding {key} inside existing section before line {section_end + 1}.")
    lines.insert(section_end, new_key_line)
    return "\n".join(lines) + "\n"


def _find_key_anywhere(text, key):
    prefix = f"{key}="
    lines = text.splitlines()
    matches = []

    current_section = "<no section yet>"
    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped
            continue

        if stripped.startswith(prefix):
            matches.append((i + 1, current_section, stripped))

    return matches


def run():
    try:
        settings_path = _get_settings_file_path()
        if not os.path.exists(settings_path):
            _log_warning("Settings file does not exist yet.")
            return ""

        text = _read_text_file(settings_path)
        _log(f"Read {len(text)} characters from settings file.")

        lines = text.splitlines()
        _log(f"Settings file contains {len(lines)} lines.")

        show_file_server_path, show_section_line_index, show_key_line_index = _get_section_value(
            text,
            _SECTION,
            _SHOW_FILE_SERVER_PATH_KEY,
        )
        if show_file_server_path:
            derived_output_path = _derive_output_path_from_show_file_server_path(show_file_server_path)
            if derived_output_path:
                _log(f"Found target section at line {show_section_line_index + 1}")
                _log(f"Found {_SHOW_FILE_SERVER_PATH_KEY} at line {show_key_line_index + 1}")
                _log(
                    f"Derived {_OUTPUT_KEY} from {_SHOW_FILE_SERVER_PATH_KEY}: "
                    f"{derived_output_path}"
                )

                saved_output_path, _, _ = _get_section_value(text, _SECTION, _OUTPUT_KEY)
                saved_output_path = _normalize_path(saved_output_path)
                if saved_output_path != derived_output_path:
                    _log(
                        f"Synchronizing {_OUTPUT_KEY}. Previous='{saved_output_path}', "
                        f"New='{derived_output_path}'"
                    )
                    updated_text = _upsert_section_key(text, _SECTION, _OUTPUT_KEY, derived_output_path)
                    _write_text_file(settings_path, updated_text)
                    _log(f"Wrote synchronized {_OUTPUT_KEY} to settings file: {settings_path}")

                return derived_output_path

        value, section_line_index, key_line_index = _get_section_value(text, _SECTION, _OUTPUT_KEY)

        if value:
            value = _normalize_path(value)
            _log(f"Found target section at line {section_line_index + 1}")
            _log(f"Found {_OUTPUT_KEY} at line {key_line_index + 1}")
            _log(f"Loaded {_OUTPUT_KEY}='{value}'")
            return value

        _log_warning(
            f"Target section/key not found: [{_SECTION}] "
            f"{_SHOW_FILE_SERVER_PATH_KEY} or {_OUTPUT_KEY}"
        )

        headers = _collect_section_headers(lines, max_count=15)
        if headers:
            _log("Section headers in settings file:")
            for header in headers:
                _log(f"  {header}")

        for key in (_SHOW_FILE_SERVER_PATH_KEY, _OUTPUT_KEY):
            global_matches = _find_key_anywhere(text, key)
            if global_matches:
                _log_warning(f"Found {key} elsewhere in settings file:")
                for line_no, section_name, line_text in global_matches[:10]:
                    _log_warning(f"  line {line_no} section {section_name}: {line_text}")
            else:
                _log_warning(f"No '{key}=' key found anywhere in the settings file.")

        return ""

    except Exception as exc:
        _log_error(str(exc))
        return ""
