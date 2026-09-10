"""Versioned project definitions, independent of paths on a render machine."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit
from urllib.request import urlopen


def relative_path(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a relative path")
    value = value.replace("\\", "/")
    parts = PurePosixPath(value).parts
    if value.startswith("/") or ":" in value or ".." in parts or "\x00" in value:
        raise ValueError(f"{label} must stay inside the checkout")
    return str(PurePosixPath(value))


def repository_location(value: str) -> str:
    if not isinstance(value, str) or not value or value.startswith("-") or "\x00" in value:
        raise ValueError("Invalid repository location")
    if Path(value).is_absolute():
        return str(Path(value).resolve())
    parsed = urlsplit(value)
    if parsed.scheme in {"https", "ssh"} and parsed.hostname:
        if parsed.password or (parsed.scheme == "https" and parsed.username):
            raise ValueError("Store repository credentials in Git's credential manager, not the catalog")
        return value
    if re.fullmatch(r"[\w.-]+@[\w.-]+:[\w./-]+", value):
        return value
    raise ValueError("Repository must be an absolute local path, HTTPS URL, or SSH URL")


@dataclass(frozen=True)
class ProjectDefinition:
    project_id: str
    revision: int
    repository: str
    branch: str
    uproject: str
    lfs: bool = True
    submodules: bool = False
    render: dict = field(default_factory=dict)
    shot_aliases: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict) -> ProjectDefinition:
        if not isinstance(value, dict):
            raise ValueError("Project definition must be an object")
        project_id = value.get("project_id", "")
        if not isinstance(project_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", project_id):
            raise ValueError("project_id must contain lowercase letters, digits, underscores or hyphens")
        revision = value.get("revision", 1)
        if type(revision) is not int or revision < 1:
            raise ValueError("Project revision must be a positive integer")
        branch = value.get("branch", "")
        if not isinstance(branch, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]*", branch) or ".." in branch:
            raise ValueError("An explicit valid render branch is required")
        uproject = relative_path(value.get("uproject", ""), "uproject")
        if not uproject.endswith(".uproject"):
            raise ValueError("uproject must identify a .uproject file")
        for flag in ("lfs", "submodules"):
            if flag in value and type(value[flag]) is not bool:
                raise ValueError(f"{flag} must be a boolean")
        for field_name in ("render", "shot_aliases"):
            if not isinstance(value.get(field_name, {}), dict):
                raise ValueError(f"{field_name} must be an object")
        return cls(project_id, revision, repository_location(value.get("repository", "")),
                   branch, uproject, value.get("lfs", True), value.get("submodules", False),
                   value.get("render", {}), value.get("shot_aliases", {}))

    def canonical_shot(self, shot: str) -> str:
        aliases = {str(key).casefold(): value for key, value in self.shot_aliases.items()}
        selected = aliases.get(shot.casefold(), shot)
        if not isinstance(selected, str) or not re.fullmatch(r"[A-Za-z0-9_]+", selected):
            raise ValueError("Shot name must contain only letters, digits and underscores")
        return selected


def load_catalog(location: str | Path) -> dict[str, ProjectDefinition]:
    location = str(location)
    if location.startswith("https://"):
        parsed = urlsplit(location)
        if parsed.username or parsed.password:
            raise ValueError("Catalog URLs must not contain credentials")
        with urlopen(location, timeout=30) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
    else:
        raw = Path(location).read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Project catalog exceeds 2 MiB")
    document = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("Unsupported project catalog schema; expected schema_version 1")
    projects = document.get("projects")
    if not isinstance(projects, list):
        raise ValueError("Project catalog must contain a projects list")
    result = {}
    for value in projects:
        project = ProjectDefinition.from_dict(value)
        if project.project_id in result:
            raise ValueError(f"Duplicate project_id: {project.project_id}")
        result[project.project_id] = project
    return result
