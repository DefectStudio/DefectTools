"""Read show names from an explicitly selected Dropbox root.

All immediate folders qualify, including shows without renderFarm. Never searches for
Unreal checkouts, creates folders, or contacts a registry.
"""

from pathlib import Path


def list_dropbox_projects(root: str | Path) -> dict[str, Path]:
    """Map each exact folder name to its existing or expected renderFarm path."""
    directory = Path(root).expanduser()
    if not directory.is_dir():
        raise FileNotFoundError(f"Dropbox project root is unavailable: {directory}")
    projects = {}
    for show in sorted(directory.iterdir(), key=lambda path: path.name.casefold()):
        if not show.is_dir():
            continue
        farms = [path for path in show.iterdir()
                 if path.name.casefold() == "renderfarm" and path.is_dir()]
        if len(farms) > 1:
            raise ValueError(f"Multiple renderFarm folders in {show}")
        projects[show.name] = farms[0] if farms else show / "renderFarm"
    return projects
