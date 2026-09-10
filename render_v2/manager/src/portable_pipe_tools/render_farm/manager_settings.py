from __future__ import annotations

from pathlib import Path

from portable_pipe_tools.render_farm.auto_refresh_interval import (
    AUTO_REFRESH_INTERVAL_MINUTES,
    DEFAULT_AUTO_REFRESH_INTERVAL_MINUTES,
)
from portable_pipe_tools.render_farm.queue import (
    create_directory_with_retry,
    read_json_object,
    write_json_atomic,
)


SETTINGS_SCHEMA_VERSION = 3
SETTINGS_FILENAME = "farm_render_manager_local_save.json"


def get_default_manager_settings_path() -> Path:
    repository_root = Path(__file__).resolve().parents[3]
    return repository_root / "LocalSaveFiles" / SETTINGS_FILENAME


def load_manager_settings(settings_path: Path | None = None) -> dict:
    path = settings_path or get_default_manager_settings_path()
    try:
        return read_json_object(path)
    except (FileNotFoundError, OSError, ValueError):
        return {}


def load_saved_dropbox_folder(settings_path: Path | None = None) -> str:
    settings = load_manager_settings(settings_path)
    return str(settings.get("dropbox_folder") or "").strip()


def load_saved_auto_refresh_enabled(settings_path: Path | None = None) -> bool:
    settings = load_manager_settings(settings_path)
    value = settings.get("auto_refresh_enabled", True)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    normalized = str(value).strip().lower()
    if normalized in {"false", "no", "off", "0"}:
        return False
    if normalized in {"true", "yes", "on", "1"}:
        return True
    return True


def load_saved_auto_refresh_interval_minutes(
    settings_path: Path | None = None,
) -> int:
    settings = load_manager_settings(settings_path)
    value = settings.get(
        "auto_refresh_interval_minutes",
        DEFAULT_AUTO_REFRESH_INTERVAL_MINUTES,
    )
    if isinstance(value, bool):
        return DEFAULT_AUTO_REFRESH_INTERVAL_MINUTES
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return DEFAULT_AUTO_REFRESH_INTERVAL_MINUTES
    if minutes not in AUTO_REFRESH_INTERVAL_MINUTES:
        return DEFAULT_AUTO_REFRESH_INTERVAL_MINUTES
    return minutes


def save_dropbox_folder(
    dropbox_folder: str | Path,
    settings_path: Path | None = None,
) -> Path:
    path = settings_path or get_default_manager_settings_path()
    settings = load_manager_settings(path)
    settings["schema_version"] = SETTINGS_SCHEMA_VERSION
    settings["dropbox_folder"] = str(dropbox_folder)

    create_directory_with_retry(path.parent, parents=True, exist_ok=True)
    write_json_atomic(path, settings)
    return path


def save_auto_refresh_enabled(
    enabled: bool,
    settings_path: Path | None = None,
) -> Path:
    path = settings_path or get_default_manager_settings_path()
    settings = load_manager_settings(path)
    settings["schema_version"] = SETTINGS_SCHEMA_VERSION
    settings["auto_refresh_enabled"] = bool(enabled)

    create_directory_with_retry(path.parent, parents=True, exist_ok=True)
    write_json_atomic(path, settings)
    return path


def save_auto_refresh_interval_minutes(
    minutes: int,
    settings_path: Path | None = None,
) -> Path:
    if isinstance(minutes, bool) or minutes not in AUTO_REFRESH_INTERVAL_MINUTES:
        raise ValueError(f"Unsupported auto-refresh interval: {minutes}")

    path = settings_path or get_default_manager_settings_path()
    settings = load_manager_settings(path)
    settings["schema_version"] = SETTINGS_SCHEMA_VERSION
    settings["auto_refresh_interval_minutes"] = minutes

    create_directory_with_retry(path.parent, parents=True, exist_ok=True)
    write_json_atomic(path, settings)
    return path
