"""Discover Unreal EXR renders and manually promote one to its shot's _hero.

The filename conversion intentionally matches QuickWidgetTools' MRGHero callback.
This module has no Unreal dependency and never moves the versioned source frames.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import stat
from typing import Callable


SHOT_PATTERN = re.compile(r"^[A-Za-z0-9]+_\d+_\d+$")
SEQUENCE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_-]*$")
VERSION_PATTERN = re.compile(r"_v(\d+)$", re.IGNORECASE)
Progress = Callable[[int, int, str], None]


@dataclass(frozen=True)
class RenderVersion:
    path: Path
    version: int
    frame_count: int

    @property
    def label(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class ShotRenders:
    path: Path
    versions: tuple[RenderVersion, ...]
    error: str = ""

    @property
    def name(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class PromotionResult:
    hero_path: Path
    source_path: Path
    copied_count: int
    warnings: tuple[str, ...] = ()


def _natural_key(value: str) -> tuple:
    return tuple(int(part) if part.isdigit() else part.lower()
                 for part in re.split(r"(\d+)", value))


def _is_redirect(path: Path) -> bool:
    """Reject links/junctions without rejecting Dropbox cloud placeholders."""
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_reparse_tag", 0) & 0x20000000
    )


def _require_no_redirects(path: Path) -> None:
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            if _is_redirect(part):
                raise ValueError(f"Linked folders/files are not supported: {part}")


def _directories(folder: Path) -> list[Path]:
    return sorted((path for path in folder.iterdir()
                   if path.is_dir() and not _is_redirect(path)),
                  key=lambda path: _natural_key(path.name))


def discover_shows(root: Path) -> list[Path]:
    root = Path(root).expanduser()
    _require_no_redirects(root)
    return [path for path in _directories(root)
            if (path / "sequences").is_dir()
            and not _is_redirect(path / "sequences")]


def discover_sequences(show: Path) -> list[Path]:
    sequences = Path(show) / "sequences"
    _require_no_redirects(sequences)
    result = []
    for path in _directories(sequences):
        if path.name.startswith(("_", ".")):
            continue
        if SEQUENCE_PATTERN.fullmatch(path.name) or any(
            SHOT_PATTERN.fullmatch(shot.name) for shot in _directories(path)
        ):
            result.append(path)
    return result


def _render_versions(shot: Path) -> tuple[RenderVersion, ...]:
    output = shot / "lite" / "unreal" / "_output"
    _require_no_redirects(output)
    if not output.is_dir():
        return ()
    versions = []
    for folder in _directories(output):
        match = VERSION_PATTERN.search(folder.name)
        if not match or not folder.name.lower().startswith(shot.name.lower() + "_"):
            continue
        count = sum(path.is_file() and path.suffix.lower() == ".exr"
                    and not _is_redirect(path) for path in folder.iterdir())
        if count:
            versions.append(RenderVersion(folder, int(match.group(1)), count))
    return tuple(sorted(versions, key=lambda item: (
        -item.version, "_beauty_v" not in item.path.name.lower(),
        _natural_key(item.path.name))))


def discover_shots(sequence: Path) -> list[ShotRenders]:
    sequence = Path(sequence)
    _require_no_redirects(sequence)
    rows = []
    for path in _directories(sequence):
        if not SHOT_PATTERN.fullmatch(path.name):
            continue
        try:
            rows.append(ShotRenders(path, _render_versions(path)))
        except (OSError, ValueError) as exc:
            rows.append(ShotRenders(path, (), str(exc)))
    return rows


def make_hero_filename(file_name: str) -> str:
    """Mirror MRGHero._make_hero_filename, including frame padding/case."""
    stem, extension = os.path.splitext(file_name)
    match = re.match(r"^(.*)\.(\d+)$", stem)
    if not match:
        return file_name
    tokens = match.group(1).split("_")
    if len(tokens) < 3:
        return file_name
    return f"{'_'.join(tokens[:3])}.{match.group(2)}{extension}"


def _signature(path: Path) -> tuple[int, int]:
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"Not a regular file: {path}")
    return info.st_size, info.st_mtime_ns


def _source_frames(source: Path, shot_name: str) -> dict[str, tuple[int, int]]:
    frames = {}
    destinations = set()
    for path in sorted(source.iterdir(), key=lambda item: _natural_key(item.name)):
        if path.suffix.lower() != ".exr":
            continue
        _require_no_redirects(path)
        name = make_hero_filename(path.name)
        if not re.fullmatch(re.escape(shot_name) + r"\.\d+\.[Ee][Xx][Rr]", name):
            raise ValueError(f"EXR filename does not match this shot/frame pattern: {path.name}")
        if name.lower() in destinations:
            raise ValueError(f"Multiple EXRs would overwrite the same hero frame: {name}")
        destinations.add(name.lower())
        signature = _signature(path)
        if signature[0] == 0:
            raise ValueError(f"EXR is empty; the render may still be writing: {path.name}")
        frames[path.name] = signature
    if not frames:
        raise ValueError(f"No EXR frames found in {source}")
    return frames


def _clear_hero(hero: Path) -> None:
    """Only clear entries directly beneath the already validated _hero."""
    if hero.name != "_hero":
        raise ValueError(f"Refusing to clear a folder other than _hero: {hero}")
    _require_no_redirects(hero)
    for path in hero.iterdir():
        _require_no_redirects(path)
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def promote_render(
    source: Path,
    *,
    progress: Progress | None = None,
) -> PromotionResult:
    """Clear _hero and copy source EXRs directly to their unversioned names."""
    source = Path(os.path.abspath(Path(source).expanduser()))
    _require_no_redirects(source)
    if len(source.parents) < 4:
        raise ValueError("Select a render under SHOT/lite/unreal/_output.")
    output, unreal, lite, shot = source.parents[:4]
    if (output.name != "_output" or unreal.name != "unreal" or lite.name != "lite"
            or not SHOT_PATTERN.fullmatch(shot.name)
            or not source.name.lower().startswith(shot.name.lower() + "_")
            or not VERSION_PATTERN.search(source.name)):
        raise ValueError("Select a versioned render under SHOT/lite/unreal/_output.")
    if not source.is_dir():
        raise ValueError(f"Render folder is unavailable: {source}")
    hero = output / "_hero"
    _require_no_redirects(hero)
    if hero.exists() and not hero.is_dir():
        raise ValueError(f"The hero path is not a folder: {hero}")
    frames = _source_frames(source, shot.name)
    total = len(frames)

    def report(done: int, message: str) -> None:
        if progress is not None:
            progress(done, total, message)

    report(0, "Clearing the current hero...")
    hero.mkdir(exist_ok=True)
    _clear_hero(hero)
    copied = 0
    try:
        for index, (name, signature) in enumerate(frames.items(), 1):
            report(copied, f"Copying hero {index}/{total}: {name}")
            destination = hero / make_hero_filename(name)
            shutil.copy2(source / name, destination)
            if _signature(destination) != signature or _signature(source / name) != signature:
                raise RuntimeError(f"Source changed or did not copy completely: {name}")
            copied += 1
    except Exception as exc:
        raise RuntimeError(
            f"Hero copy stopped after {copied}/{total} frames: {exc}\n"
            "The previous hero was cleared; _hero contains the files copied so far."
        ) from exc
    report(total, f"Hero updated: {total} frames")
    return PromotionResult(hero, source, copied)
