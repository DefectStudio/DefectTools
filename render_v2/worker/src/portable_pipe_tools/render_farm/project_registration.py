"""Projects explicitly registered on this machine; no project discovery."""

from dataclasses import asdict, dataclass
from pathlib import Path
import re

from portable_pipe_tools.render_farm.project_catalog import repository_location


@dataclass(frozen=True)
class ProjectRegistration:
    project_id: str
    name: str
    local_uproject: str
    render_farm_root: str
    allow_downloads: bool = False
    repository: str = ""
    branch: str = "main"

    @classmethod
    def from_dict(cls, value: dict) -> "ProjectRegistration":
        if not isinstance(value, dict):
            raise ValueError("Project registration must be an object")
        fields = {}
        for key in ("project_id", "name", "local_uproject", "render_farm_root", "repository", "branch"):
            item = value.get(key, "main" if key == "branch" else "")
            if not isinstance(item, str):
                raise ValueError(f"{key} must be text")
            fields[key] = item.strip()
        if not fields["name"]:
            raise ValueError("Enter a project name.")
        identifier = fields["project_id"]
        if (not identifier or identifier in (".", "..")
                or re.search(r'[<>:"/\\|?*\x00-\x1f]', identifier)):
            raise ValueError("Project ID must be a single Dropbox show folder name.")
        project = Path(fields["local_uproject"]).expanduser()
        if not project.is_absolute() or project.suffix.lower() != ".uproject":
            raise ValueError("Choose an absolute path to a .uproject file.")
        farm = Path(fields["render_farm_root"]).expanduser()
        if not farm.is_absolute() or farm.name.casefold() != "renderfarm":
            raise ValueError("Choose the show's folder named RenderFarm.")
        fields["local_uproject"] = str(project)
        fields["render_farm_root"] = str(farm)
        downloads = value.get("allow_downloads", False)
        if type(downloads) is not bool:
            raise ValueError("Allow project downloads must be a checkbox value.")
        if downloads:
            fields["repository"] = repository_location(fields["repository"])
            branch = fields["branch"]
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]*", branch) or ".." in branch:
                raise ValueError("Enter a valid Git branch for project downloads.")
        return cls(**fields, allow_downloads=downloads)

    def to_dict(self) -> dict:
        return asdict(self)

    def location_status(self) -> str:
        if not Path(self.local_uproject).is_file():
            return "Missing project"
        if not Path(self.render_farm_root).is_dir():
            return "Missing RenderFarm folder"
        return "Local paths available"
