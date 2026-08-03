from __future__ import annotations

from pathlib import Path

from portable_pipe_tools.render_farm.queue import (
    create_directory_with_retry,
    read_json_object,
    write_json_atomic,
)


SETTINGS_SCHEMA_VERSION = 1
SETTINGS_FILENAME = "render_worker_local_save.json"


def get_default_settings_path() -> Path:
    repository_root = Path(__file__).resolve().parents[3]
    return repository_root / "LocalSaveFiles" / SETTINGS_FILENAME


def load_local_settings(settings_path: Path | None = None) -> dict:
    path = settings_path or get_default_settings_path()
    try:
        return read_json_object(path)
    except (FileNotFoundError, OSError, ValueError):
        return {}


def update_local_settings(
    settings_path: Path | None = None,
    **updates: str | Path,
) -> Path:
    path = settings_path or get_default_settings_path()
    data = load_local_settings(path)
    data["schema_version"] = SETTINGS_SCHEMA_VERSION
    for key, value in updates.items():
        data[key] = str(value)

    create_directory_with_retry(path.parent, parents=True, exist_ok=True)
    write_json_atomic(path, data)
    return path


def load_saved_render_farm_root(settings_path: Path | None = None) -> str:
    data = load_local_settings(settings_path)
    return str(data.get("show_render_farm_root") or "").strip()


def load_saved_animation_sprite_folder(settings_path: Path | None = None) -> str:
    data = load_local_settings(settings_path)
    return str(data.get("animation_sprite_folder") or "").strip()


def load_saved_unreal_editor_cmd(settings_path: Path | None = None) -> str:
    data = load_local_settings(settings_path)
    return str(data.get("unreal_editor_cmd") or "").strip()


def save_render_farm_root(
    farm_root: str | Path,
    settings_path: Path | None = None,
) -> Path:
    return update_local_settings(
        settings_path,
        show_render_farm_root=farm_root,
    )


def save_animation_sprite_folder(
    sprite_folder: str | Path,
    settings_path: Path | None = None,
) -> Path:
    return update_local_settings(
        settings_path,
        animation_sprite_folder=sprite_folder,
    )


def save_unreal_editor_cmd(
    unreal_editor_cmd: str | Path,
    settings_path: Path | None = None,
) -> Path:
    return update_local_settings(
        settings_path,
        unreal_editor_cmd=unreal_editor_cmd,
    )
