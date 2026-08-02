from __future__ import annotations

from pathlib import Path

from portable_pipe_tools.render_farm.queue import read_json_object, write_json_atomic


SETTINGS_SCHEMA_VERSION = 1
SETTINGS_FILENAME = "render_worker_local_save.json"


def get_default_settings_path() -> Path:
    repository_root = Path(__file__).resolve().parents[3]
    return repository_root / "LocalSaveFiles" / SETTINGS_FILENAME


def load_saved_render_farm_root(settings_path: Path | None = None) -> str:
    path = settings_path or get_default_settings_path()
    if not path.exists():
        return ""
    try:
        data = read_json_object(path)
    except Exception:
        return ""
    return str(data.get("show_render_farm_root") or "").strip()


def save_render_farm_root(
    farm_root: str | Path,
    settings_path: Path | None = None,
) -> Path:
    path = settings_path or get_default_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        path,
        {
            "schema_version": SETTINGS_SCHEMA_VERSION,
            "show_render_farm_root": str(farm_root),
        },
    )
    return path
