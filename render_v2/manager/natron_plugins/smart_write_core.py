"""Natron-independent output path construction for Smart Write."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from smart_read_core import shot_root_from_project_directory


DEFAULT_ELEMENT = "beauty"
DEFAULT_FRAME_PADDING = 4


@dataclass(frozen=True)
class SmartWritePaths:
    version: int
    exr_sequence: Path
    mp4_file: Path
    mov_file: Path
    hero_sequence: Path


def existing_output_versions(
    project_directory: str | Path,
    element: str = DEFAULT_ELEMENT,
) -> tuple[int, ...]:
    """Return versions already claimed by EXR, MP4, or MOV beauty output."""

    element_name = str(element).strip()
    if not element_name:
        raise ValueError("The Smart Write element cannot be empty.")

    shot_root = shot_root_from_project_directory(project_directory)
    output_directory = shot_root / "comp" / "_output"
    if not output_directory.is_dir():
        return ()

    version_pattern = re.compile(
        r"^{0}_{1}_v(?P<version>\d+)(?P<extension>\.mp4|\.mov)?$".format(
            re.escape(shot_root.name),
            re.escape(element_name),
        ),
        re.IGNORECASE,
    )
    versions = set()
    for candidate in output_directory.iterdir():
        match = version_pattern.match(candidate.name)
        if match is None:
            continue
        extension = match.group("extension")
        if (extension is None and candidate.is_dir()) or (
            extension is not None and candidate.is_file()
        ):
            versions.add(int(match.group("version")))
    return tuple(sorted(versions))


def next_output_version(
    project_directory: str | Path,
    element: str = DEFAULT_ELEMENT,
) -> int:
    """Return one version above the highest existing version, starting at 1."""

    versions = existing_output_versions(project_directory, element)
    return max(versions, default=0) + 1


def build_output_paths(
    project_directory: str | Path,
    element: str = DEFAULT_ELEMENT,
    version: int | None = None,
    frame_padding: int = DEFAULT_FRAME_PADDING,
) -> SmartWritePaths:
    """Build Smart Write targets from a project saved in ``SHOT/comp/natron``."""

    element_name = str(element).strip()
    if not element_name:
        raise ValueError("The Smart Write element cannot be empty.")
    if version is not None and version < 1:
        raise ValueError("The Smart Write version must be at least 1.")
    if frame_padding < 1:
        raise ValueError("The Smart Write frame padding must be at least 1.")

    shot_root = shot_root_from_project_directory(project_directory)
    selected_version = (
        next_output_version(project_directory, element_name)
        if version is None
        else version
    )
    output_directory = shot_root / "comp" / "_output"
    version_name = "{0}_{1}_v{2:03d}".format(
        shot_root.name,
        element_name,
        selected_version,
    )
    frame_token = "#" * frame_padding

    return SmartWritePaths(
        version=selected_version,
        exr_sequence=(
            output_directory
            / version_name
            / "{0}.{1}.exr".format(version_name, frame_token)
        ),
        mp4_file=output_directory / "{0}.mp4".format(version_name),
        mov_file=output_directory / "{0}.mov".format(version_name),
        hero_sequence=(
            output_directory
            / "_hero"
            / "{0}.{1}.exr".format(shot_root.name, frame_token)
        ),
    )
