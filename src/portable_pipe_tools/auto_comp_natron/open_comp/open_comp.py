from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess

from portable_pipe_tools.auto_comp_natron.create_comp import (
    CompAlreadyExistsError,
    create_comp,
    get_comp_path,
)
from portable_pipe_tools.auto_comp_natron.source_media import (
    HydrationProgress,
    hydrate_latest_source_sequence,
)


CompOpener = Callable[[Path], object]
NATRON_EXECUTABLE_ENV = "PORTABLE_PIPE_NATRON_EXECUTABLE"
NATRON_PLUGIN_PATH_ENV = "NATRON_PLUGIN_PATH"
DEFAULT_NATRON_EXECUTABLE = Path("F:/Natron/bin/Natron.exe")


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
    hydrated_source_files: int = 0


def get_portable_natron_plugins_path() -> Path:
    return Path(__file__).resolve().parents[4] / "natron_plugins"


def get_smart_read_onload_script_path() -> Path:
    return get_portable_natron_plugins_path() / "SmartReadOnLoad.py"


def get_natron_executable(environment: dict[str, str] | None = None) -> Path:
    values = environment if environment is not None else os.environ
    configured_path = str(values.get(NATRON_EXECUTABLE_ENV) or "").strip()
    return Path(configured_path) if configured_path else DEFAULT_NATRON_EXECUTABLE


def build_natron_environment(
    environment: dict[str, str] | None = None,
    plugin_path: str | Path | None = None,
) -> dict[str, str]:
    values = dict(environment if environment is not None else os.environ)
    portable_plugins = str(plugin_path or get_portable_natron_plugins_path())
    existing_paths = [
        value
        for value in str(values.get(NATRON_PLUGIN_PATH_ENV) or "").split(os.pathsep)
        if value
    ]
    normalized_portable = os.path.normcase(os.path.normpath(portable_plugins))
    if all(
        os.path.normcase(os.path.normpath(value)) != normalized_portable
        for value in existing_paths
    ):
        existing_paths.insert(0, portable_plugins)
    values[NATRON_PLUGIN_PATH_ENV] = os.pathsep.join(existing_paths)
    return values


def _default_opener(comp_path: Path) -> object:
    return open_comp_in_natron(comp_path)


def open_comp_in_natron(
    comp_path: Path,
    natron_executable: str | Path | None = None,
) -> object:
    environment = build_natron_environment()
    executable = (
        Path(natron_executable)
        if natron_executable is not None
        else get_natron_executable(environment)
    )
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        [
            str(executable),
            "--onload",
            str(get_smart_read_onload_script_path()),
            str(comp_path),
        ],
        env=environment,
        creationflags=creation_flags,
    )


def _open_comp_path(
    comp_path: Path,
    opener: CompOpener | None = None,
    natron_executable: str | Path | None = None,
) -> None:
    if not comp_path.is_file():
        raise CompNotFoundError(comp_path)
    try:
        if opener is not None:
            opener(comp_path)
        else:
            open_comp_in_natron(comp_path, natron_executable)
    except OSError as error:
        raise CompOpenError(comp_path, error) from error


def open_comp(
    show_root: str | Path,
    sequence_name: str,
    shot_name: str,
    *,
    opener: CompOpener | None = None,
    natron_executable: str | Path | None = None,
    hydration_progress: HydrationProgress | None = None,
) -> OpenCompResult:
    comp_path = get_comp_path(show_root, sequence_name, shot_name)
    if not comp_path.is_file():
        raise CompNotFoundError(comp_path)
    hydration = hydrate_latest_source_sequence(
        show_root,
        sequence_name,
        shot_name,
        progress=hydration_progress,
    )
    _open_comp_path(comp_path, opener, natron_executable)
    return OpenCompResult(
        comp_path=comp_path,
        created=False,
        hydrated_source_files=hydration.hydrated_files,
    )


def create_and_open_comp(
    show_root: str | Path,
    sequence_name: str,
    shot_name: str,
    *,
    opener: CompOpener | None = None,
    natron_executable: str | Path | None = None,
    hydration_progress: HydrationProgress | None = None,
) -> OpenCompResult:
    hydration = hydrate_latest_source_sequence(
        show_root,
        sequence_name,
        shot_name,
        progress=hydration_progress,
    )
    try:
        create_result = create_comp(show_root, sequence_name, shot_name)
    except CompAlreadyExistsError as error:
        comp_path = error.comp_path
        created = False
    else:
        comp_path = create_result.target_path
        created = True

    _open_comp_path(comp_path, opener, natron_executable)
    return OpenCompResult(
        comp_path=comp_path,
        created=created,
        hydrated_source_files=hydration.hydrated_files,
    )
