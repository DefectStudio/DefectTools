"""Natron-independent EXR discovery for Smart Read."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable, Sequence


OUTPUT_RELATIVE_PATH = Path("lite") / "unreal" / "_output"


@dataclass(frozen=True)
class ExrVersion:
    version: int
    label: str
    directory: Path
    sequence_path: Path
    first_frame: int
    last_frame: int


def project_directory_from_paths(
    project_paths: Iterable[Sequence[str]],
) -> Path | None:
    """Return Natron's named Project directory from its project-path table."""

    for row in project_paths:
        if len(row) >= 2 and str(row[0]).strip().casefold() == "project":
            value = str(row[1]).strip()
            return Path(value) if value else None
    return None


def shot_root_from_project_directory(project_directory: str | Path) -> Path:
    """Resolve ``SHOT`` from the required ``SHOT/comp/natron`` layout."""

    directory = Path(project_directory)
    if (
        directory.name.casefold() != "natron"
        or directory.parent.name.casefold() != "comp"
    ):
        raise ValueError(
            "The Natron project must be saved inside a shot's comp/natron folder."
        )
    return directory.parent.parent


def _exr_sequence_for_version(
    version_directory: Path,
    version_pattern: re.Pattern[str],
) -> ExrVersion | None:
    version_match = version_pattern.match(version_directory.name)
    if version_match is None:
        return None

    expected_file = re.compile(
        r"^{0}\.(?P<frame>\d+)\.exr$".format(re.escape(version_directory.name)),
        re.IGNORECASE,
    )
    frames: list[tuple[int, int]] = []
    for candidate in version_directory.iterdir():
        if not candidate.is_file():
            continue
        match = expected_file.match(candidate.name)
        if match is not None:
            frame_text = match.group("frame")
            frames.append((int(frame_text), len(frame_text)))

    if not frames:
        return None

    frames.sort()
    frame_padding = frames[0][1]
    version = int(version_match.group("version"))
    return ExrVersion(
        version=version,
        label="v{0:03d}".format(version),
        directory=version_directory,
        sequence_path=(
            version_directory
            / "{0}.{1}.exr".format(version_directory.name, "#" * frame_padding)
        ),
        first_frame=frames[0][0],
        last_frame=frames[-1][0],
    )


def find_exr_versions(
    project_directory: str | Path,
    element: str = "beauty",
) -> tuple[ExrVersion, ...]:
    """Find valid EXR versions for one element relative to the Natron project."""

    shot_root = shot_root_from_project_directory(project_directory)
    output_directory = shot_root / OUTPUT_RELATIVE_PATH
    element_name = str(element).strip()
    if not element_name or not output_directory.is_dir():
        return ()

    shot_name = shot_root.name
    version_pattern = re.compile(
        r"^{0}_{1}_v(?P<version>\d+)$".format(
            re.escape(shot_name),
            re.escape(element_name),
        ),
        re.IGNORECASE,
    )
    versions = []
    for candidate in output_directory.iterdir():
        if not candidate.is_dir():
            continue
        exr_version = _exr_sequence_for_version(candidate, version_pattern)
        if exr_version is not None:
            versions.append(exr_version)
    return tuple(sorted(versions, key=lambda item: item.version))


def latest_exr_version(versions: Sequence[ExrVersion]) -> ExrVersion | None:
    return max(versions, key=lambda item: item.version, default=None)
