"""Find existing project repositories before allocating another checkout."""

from __future__ import annotations

from collections import deque
import os
from pathlib import Path
import re
import string
from urllib.parse import urlsplit


def _ini_project_entries(path: Path):
    """Read only project-location arrays; Unreal INI files allow repeated keys."""
    try:
        with path.open("rb") as stream:
            raw = stream.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            return
        encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        text = raw.decode(encoding, errors="replace")
    except OSError:
        return
    section = ""
    arrays = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].casefold()
            continue
        if section not in {"/script/unrealed.editorsettings", "launcher"} or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        operation = key[:1] if key[:1] in "+-.!" else ""
        key = key.lstrip("+-.!").casefold()
        if key not in {"recentlyopenedprojectfiles", "createdprojectpaths"}:
            continue
        entries = arrays.setdefault(key, [])
        if operation == "!":
            entries.clear()
        elif operation == "-":
            entries[:] = [entry for entry in entries if entry != value]
        else:
            entries.append(value)
    for key, entries in arrays.items():
        for value in entries:
            yield key, value


def _metadata_path(value: str, *, escaped: bool = False) -> Path | None:
    value = value.strip().strip('"')
    if escaped:
        value = re.sub(r'\\(["\\])', r'\1', value)
    if not value or "\x00" in value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else None


def editor_project_candidates(local_app_data: Path | None = None, *, excluded=(), check_cancelled=lambda: None):
    """Read fresh Editor/Launcher history each time; never modify their settings."""
    if local_app_data is None:
        location = os.environ.get("LOCALAPPDATA")
        if not location:
            return
        local_app_data = Path(location)
    recent = []
    roots = []
    patterns = (
        "UnrealEngine/*/Saved/Config/*/EditorSettings.ini",
        "EpicGamesLauncher/Saved/Config/*/GameUserSettings.ini",
    )
    for pattern in patterns:
        for settings in sorted(local_app_data.glob(pattern)):
            check_cancelled()
            for key, value in _ini_project_entries(settings):
                if key == "createdprojectpaths":
                    path = _metadata_path(value)
                    if path is not None:
                        roots.append(path)
                else:
                    match = re.search(r'\bProjectName\s*=\s*"((?:\\.|[^"\\])*)"', value)
                    path = _metadata_path(match.group(1) if match else value, escaped=match is not None)
                    opened = re.search(r'\bLastOpenTime\s*=\s*([^,)]+)', value)
                    if path is not None:
                        recent.append((opened.group(1).strip('"') if opened else "", path))
    excluded = tuple(Path(root).resolve() for root in excluded)
    seen = set()
    for _, project in sorted(recent, key=lambda item: item[0], reverse=True):
        check_cancelled()
        try:
            if project.suffix.casefold() != ".uproject" or not project.is_file():
                continue
            # A project remembered by Unreal can live below the repository root.
            for candidate in project.resolve().parents:
                if (candidate / ".git").exists():
                    if candidate not in seen and not any(candidate.is_relative_to(root) for root in excluded):
                        seen.add(candidate)
                        yield candidate
                    break
        except OSError:
            continue
    for candidate in repository_candidates(roots, excluded=excluded, check_cancelled=check_cancelled):
        if candidate not in seen:
            seen.add(candidate)
            yield candidate


def repository_identity(location: str) -> str:
    location = location.strip()
    if Path(location).is_absolute():
        return os.path.normcase(str(Path(location).resolve()))
    if "://" not in location and "@" in location and ":" in location:
        host, path = location.split("@", 1)[1].split(":", 1)
    else:
        parsed = urlsplit(location)
        host, path = parsed.hostname or "", parsed.path
    return host.casefold() + "/" + path.strip("/").removesuffix(".git")


def default_search_roots() -> tuple[Path, ...]:
    home = Path.home()
    roots = [Path.cwd(), home / "Projects", home / "source/repos", home / "Documents"]
    drives = []
    if os.name == "nt":
        import ctypes
        for letter in string.ascii_uppercase:
            drive = Path(f"{letter}:/")
            if ctypes.windll.kernel32.GetDriveTypeW(f"{letter}:\\") == 3:
                drives.append(drive)
    else:
        drives = [home]
    roots.extend(drive / name for drive in drives for name in ("Projects", "Repos", "dev"))
    roots.extend(drives)
    return tuple(roots)


def repository_candidates(roots, *, excluded=(), check_cancelled=lambda: None):
    """Breadth-first, bounded discovery; do not descend into project asset trees."""
    skipped = {".git", ".staging", "interrupted-pre-shallow", "node_modules", "windows",
               "program files", "program files (x86)", "programdata", "appdata", "$recycle.bin",
               "system volume information", "saved", "intermediate", "content"}
    queue = deque((Path(root), 0) for root in roots)
    seen = set()
    excluded = tuple(Path(root).resolve() for root in excluded)
    while queue and len(seen) < 5000:
        check_cancelled()
        candidate, depth = queue.popleft()
        try:
            candidate = candidate.resolve()
            if candidate in seen or any(candidate.is_relative_to(root) for root in excluded):
                continue
            seen.add(candidate)
            if not candidate.is_dir():
                continue
            if (candidate / ".git").exists():
                yield candidate
                continue
            if depth >= 4:
                continue
            with os.scandir(candidate) as entries:
                children = sorted((Path(entry.path) for entry in entries
                                   if entry.name.casefold() not in skipped and entry.is_dir(follow_symlinks=False)),
                                  key=lambda path: path.name.casefold())
            queue.extend((child, depth + 1) for child in children)
        except OSError:
            continue
