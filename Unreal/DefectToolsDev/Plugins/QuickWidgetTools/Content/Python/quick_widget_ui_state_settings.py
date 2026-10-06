"""
Shared helper for saving and loading Editor Utility Widget UI state.

Writes to:
    <Project>/Saved/Config/WindowsEditor/QuickWidgetToolsSettings.ini

Section:
    [/Script/QuickWidgetTools.RenderToolSettings]

This is intentionally stored in Saved/Config so it behaves like local editor UI
state and can survive widget rebuilds, scroll-box repopulation, and editor restarts.
"""

import os
import traceback

import unreal


LOG_PREFIX = "[QuickWidgetUIStateSettings]"
_SETTINGS_FILE_NAME = "QuickWidgetToolsSettings.ini"
_SECTION = "/Script/QuickWidgetTools.RenderToolSettings"


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _normalize_value(value):
    return str(value or "").strip()


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


def _write_text_file(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as file_handle:
        file_handle.write(text)


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

    _log(f"Found section at lines {section_start + 1}-{section_end}")

    prefix = f"{key}="
    for index in range(section_start + 1, section_end):
        stripped = lines[index].strip()
        if stripped.startswith(prefix):
            _log(f"Existing key found on line {index + 1}. Replacing value.")
            lines[index] = new_key_line
            return "\n".join(lines) + "\n"

    _log(f"Key not found inside existing section. Inserting before line {section_end + 1}.")
    lines.insert(section_end, new_key_line)
    return "\n".join(lines) + "\n"


def set_value(key, value):
    """
    Save a string value into QuickWidgetToolsSettings.ini.

    Returns:
        "true" on success, or "" on failure.
    """
    try:
        key = _normalize_value(key)
        value = _normalize_value(value)

        if not key:
            _log_error("key was empty.")
            return ""

        settings_path = _get_settings_file_path()
        settings_dir = os.path.dirname(settings_path)

        _log(f"Ensuring settings directory exists: {settings_dir}")
        os.makedirs(settings_dir, exist_ok=True)

        before_text = _read_text_file(settings_path)
        _log(f"Read {len(before_text)} characters from settings file before write.")

        previous_value = _get_section_value(before_text, _SECTION, key)
        if previous_value:
            _log(f"Previous saved value for {key}: {previous_value}")
        else:
            _log(f"No previous saved value found for {key}.")

        updated_text = _upsert_section_key(before_text, _SECTION, key, value)
        _write_text_file(settings_path, updated_text)

        after_text = _read_text_file(settings_path)
        verified_value = _get_section_value(after_text, _SECTION, key)

        if verified_value != value:
            _log_error(
                f"Post-write verification failed for {key}. Expected '{value}' but found '{verified_value}'"
            )
            return ""

        _log(f"Post-write verification succeeded. {key}='{verified_value}'")
        _log(f"Wrote settings file: {settings_path}")
        return "true"

    except Exception as exc:
        _log_error(str(exc))
        _log_error(traceback.format_exc())
        return ""


def get_value(key):
    """
    Load a string value from QuickWidgetToolsSettings.ini.

    Returns:
        Saved string value, or "" if missing/failure.
    """
    try:
        key = _normalize_value(key)

        if not key:
            _log_error("key was empty.")
            return ""

        settings_path = _get_settings_file_path()

        if not os.path.exists(settings_path):
            _log_warning(f"Settings file does not exist yet: {settings_path}")
            return ""

        text = _read_text_file(settings_path)
        value = _get_section_value(text, _SECTION, key)

        if value:
            _log(f"Loaded {key}='{value}'")
        else:
            _log(f"No saved value found for {key}.")

        return value

    except Exception as exc:
        _log_error(str(exc))
        _log_error(traceback.format_exc())
        return ""
