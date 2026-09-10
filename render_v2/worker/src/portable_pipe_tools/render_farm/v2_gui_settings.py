"""Persistent V2 GUI preferences, separate from the V1 settings file."""

from pathlib import Path

from portable_pipe_tools.app_runtime import default_settings_path
from portable_pipe_tools.render_farm.engine_discovery import find_installed_unreal_editor
from portable_pipe_tools.render_farm.queue import read_json_object, write_json_atomic
from portable_pipe_tools.render_farm.project_registration import ProjectRegistration


def _read_settings(path: Path) -> dict:
    try:
        return read_json_object(path)
    except FileNotFoundError:
        return {}


def load_or_detect_unreal_editor(settings_path: Path | None = None) -> str:
    path = settings_path or default_settings_path()
    settings = _read_settings(path)
    # Presence, not truthiness, records that first-time setup already ran.
    if "unreal_editor_cmd" in settings:
        return str(settings["unreal_editor_cmd"] or "")
    detected = find_installed_unreal_editor(["5.8"])
    value = str(detected) if detected else ""
    save_unreal_editor_preference(value, path)
    return value


def save_unreal_editor_preference(value: str | Path, settings_path: Path | None = None) -> None:
    path = settings_path or default_settings_path()
    settings = _read_settings(path)
    settings["unreal_editor_cmd"] = str(value).strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, settings)


def load_registered_projects(settings_path: Path | None = None) -> list[ProjectRegistration]:
    settings = _read_settings(settings_path or default_settings_path())
    return _validated_projects(settings.get("registered_projects", []))


def load_dropbox_root(settings_path: Path) -> str:
    return str(_read_settings(settings_path).get("dropbox_root", ""))


def save_dropbox_root(value: str, settings_path: Path) -> None:
    settings = _read_settings(settings_path)
    settings["dropbox_root"] = value
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(settings_path, settings)


def _validated_projects(values: list) -> list[ProjectRegistration]:
    if not isinstance(values, list):
        raise ValueError("Registered projects must be a list")
    projects = [ProjectRegistration.from_dict(value) for value in values]
    identifiers = [project.project_id.casefold() for project in projects]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("A project with that ID is already registered on this worker.")
    return projects


def save_registered_projects(projects: list[ProjectRegistration], settings_path: Path | None = None) -> None:
    values = [project.to_dict() for project in projects]
    _validated_projects(values)
    path = settings_path or default_settings_path()
    settings = _read_settings(path)
    settings["registered_projects"] = values
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, settings)
