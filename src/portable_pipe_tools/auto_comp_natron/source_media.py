from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import re
import stat
import time


OUTPUT_RELATIVE_PATH = Path("lite") / "unreal" / "_output"
DEFAULT_ELEMENT = "beauty"
HydrationProgress = Callable[[int, int, Path], None]
_CLOUD_PLACEHOLDER_MASK = (
    getattr(stat, "FILE_ATTRIBUTE_OFFLINE", 0x00001000)
    | getattr(stat, "FILE_ATTRIBUTE_RECALL_ON_OPEN", 0x00040000)
    | getattr(stat, "FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS", 0x00400000)
)


class SourceHydrationError(OSError):
    def __init__(self, source_path: Path, message: str) -> None:
        self.source_path = source_path
        super().__init__(f"Could not download Dropbox source {source_path}: {message}")


@dataclass(frozen=True)
class SourceHydrationResult:
    sequence_directory: Path | None
    source_files: int
    hydrated_files: int


def _source_files_for_version(
    version_directory: Path,
) -> tuple[Path, ...]:
    filename_pattern = re.compile(
        r"^{0}\.(?P<frame>\d+)\.exr$".format(
            re.escape(version_directory.name),
        ),
        re.IGNORECASE,
    )
    frames: list[tuple[int, Path]] = []
    for candidate in version_directory.iterdir():
        if not candidate.is_file():
            continue
        match = filename_pattern.match(candidate.name)
        if match is not None:
            frames.append((int(match.group("frame")), candidate))
    return tuple(path for _frame, path in sorted(frames))


def find_latest_source_sequence(
    show_root: str | Path,
    sequence_name: str,
    shot_name: str,
    element: str = DEFAULT_ELEMENT,
) -> tuple[Path | None, tuple[Path, ...]]:
    output_directory = (
        Path(show_root)
        / "sequences"
        / sequence_name
        / shot_name
        / OUTPUT_RELATIVE_PATH
    )
    if not output_directory.is_dir():
        return None, ()

    version_pattern = re.compile(
        r"^{0}_{1}_v(?P<version>\d+)$".format(
            re.escape(shot_name),
            re.escape(element),
        ),
        re.IGNORECASE,
    )
    versions: list[tuple[int, Path, tuple[Path, ...]]] = []
    for candidate in output_directory.iterdir():
        if not candidate.is_dir():
            continue
        match = version_pattern.match(candidate.name)
        if match is None:
            continue
        source_files = _source_files_for_version(candidate)
        if source_files:
            versions.append((int(match.group("version")), candidate, source_files))

    if not versions:
        return None, ()
    _version, directory, files = max(versions, key=lambda item: item[0])
    return directory, files


def _placeholder_attributes(source_path: Path) -> int:
    return int(getattr(source_path.stat(), "st_file_attributes", 0))


def _needs_hydration(source_path: Path) -> bool:
    return bool(_placeholder_attributes(source_path) & _CLOUD_PLACEHOLDER_MASK)


def _hydrate_placeholder(source_path: Path) -> None:
    try:
        with source_path.open("rb") as source_file:
            source_file.read(1)
    except OSError as error:
        raise SourceHydrationError(source_path, str(error)) from error

    deadline = time.monotonic() + 5.0
    while _needs_hydration(source_path) and time.monotonic() < deadline:
        time.sleep(0.1)
    if _needs_hydration(source_path):
        raise SourceHydrationError(
            source_path,
            "Windows still reports the file as an online-only placeholder.",
        )


def hydrate_latest_source_sequence(
    show_root: str | Path,
    sequence_name: str,
    shot_name: str,
    element: str = DEFAULT_ELEMENT,
    progress: HydrationProgress | None = None,
) -> SourceHydrationResult:
    directory, source_files = find_latest_source_sequence(
        show_root,
        sequence_name,
        shot_name,
        element,
    )
    placeholders = tuple(path for path in source_files if _needs_hydration(path))
    if placeholders and progress is not None:
        progress(0, len(placeholders), placeholders[0])
    for completed, source_path in enumerate(placeholders, start=1):
        _hydrate_placeholder(source_path)
        if progress is not None:
            progress(completed, len(placeholders), source_path)
    return SourceHydrationResult(
        sequence_directory=directory,
        source_files=len(source_files),
        hydrated_files=len(placeholders),
    )
