from __future__ import annotations

import json
from pathlib import Path


SETTINGS_SCHEMA_VERSION = 2
SETTINGS_FILENAME = "auto_comp_natron_local_save.json"


def get_default_settings_path() -> Path:
    repository_root = Path(__file__).resolve().parents[3]
    return repository_root / "LocalSaveFiles" / SETTINGS_FILENAME


def load_settings(settings_path: Path | None = None) -> dict:
    path = settings_path or get_default_settings_path()
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return {}
    return settings if isinstance(settings, dict) else {}


def load_saved_repository_folder(settings_path: Path | None = None) -> str:
    settings = load_settings(settings_path)
    return str(settings.get("repository_folder") or "").strip()


def load_saved_browser_selection(
    settings_path: Path | None = None,
) -> tuple[str, str, str]:
    settings = load_settings(settings_path)
    return (
        str(settings.get("selected_show") or "").strip(),
        str(settings.get("selected_sequence") or "").strip(),
        str(settings.get("selected_shot") or "").strip(),
    )


def _write_settings(path: Path, settings: dict) -> Path:
    settings["schema_version"] = SETTINGS_SCHEMA_VERSION
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(settings, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)
    return path


def save_repository_folder(
    repository_folder: str | Path,
    settings_path: Path | None = None,
) -> Path:
    path = settings_path or get_default_settings_path()
    settings = load_settings(path)
    settings["repository_folder"] = str(repository_folder)
    return _write_settings(path, settings)


def save_browser_selection(
    show_name: str,
    sequence_name: str,
    shot_name: str,
    settings_path: Path | None = None,
) -> Path:
    path = settings_path or get_default_settings_path()
    settings = load_settings(path)
    settings["selected_show"] = show_name
    settings["selected_sequence"] = sequence_name
    settings["selected_shot"] = shot_name
    return _write_settings(path, settings)
