from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys

from portable_pipe_tools.auto_comp_natron.create_comp import (
    CompAlreadyExistsError,
    create_comp,
    get_comp_path,
)


CompOpener = Callable[[Path], object]


class CompNotFoundError(FileNotFoundError):
    def __init__(self, comp_path: Path) -> None:
        self.comp_path = comp_path
        super().__init__(f"The comp does not exist: {comp_path}")


class CompOpenError(OSError):
    def __init__(self, comp_path: Path, error: OSError) -> None:
        self.comp_path = comp_path
        self.original_error = error
        super().__init__(f"Could not open {comp_path}: {error}")


@dataclass(frozen=True)
class OpenCompResult:
    comp_path: Path
    created: bool


def _default_opener(comp_path: Path) -> object:
    if hasattr(os, "startfile"):
        return os.startfile(str(comp_path))
    if sys.platform == "darwin":
        return subprocess.Popen(["open", str(comp_path)])
    return subprocess.Popen(["xdg-open", str(comp_path)])


def _open_comp_path(
    comp_path: Path,
    opener: CompOpener | None = None,
) -> None:
    if not comp_path.is_file():
        raise CompNotFoundError(comp_path)
    try:
        (opener or _default_opener)(comp_path)
    except OSError as error:
        raise CompOpenError(comp_path, error) from error


def open_comp(
    show_root: str | Path,
    sequence_name: str,
    shot_name: str,
    *,
    opener: CompOpener | None = None,
) -> OpenCompResult:
    comp_path = get_comp_path(show_root, sequence_name, shot_name)
    _open_comp_path(comp_path, opener)
    return OpenCompResult(comp_path=comp_path, created=False)


def create_and_open_comp(
    show_root: str | Path,
    sequence_name: str,
    shot_name: str,
    *,
    opener: CompOpener | None = None,
) -> OpenCompResult:
    try:
        create_result = create_comp(show_root, sequence_name, shot_name)
    except CompAlreadyExistsError as error:
        comp_path = error.comp_path
        created = False
    else:
        comp_path = create_result.target_path
        created = True

    _open_comp_path(comp_path, opener)
    return OpenCompResult(comp_path=comp_path, created=created)
