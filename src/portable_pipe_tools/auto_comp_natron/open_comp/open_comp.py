from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess

from portable_pipe_tools.auto_comp_natron.create_comp import (
    CompAlreadyExistsError,
    SmartWriteOutputOptions,
    create_comp,
    get_comp_path,
)
from portable_pipe_tools.auto_comp_natron.source_media import (
    HydrationProgress,
    hydrate_latest_source_sequence,
)


CompOpener = Callable[[Path], object]
DiagnosticLog = Callable[[str], None]
NATRON_EXECUTABLE_ENV = "PORTABLE_PIPE_NATRON_EXECUTABLE"
NATRON_PLUGIN_PATH_ENV = "NATRON_PLUGIN_PATH"
DEFAULT_NATRON_EXECUTABLE = Path("F:/Natron/bin/Natron.exe")


def _log_step(diagnostic_log: DiagnosticLog | None, message: str) -> None:
    if diagnostic_log is not None:
        diagnostic_log(message)


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
    process: object | None = None
    output_log_path: Path | None = None


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
    diagnostic_log: DiagnosticLog | None = None,
    output_log_path: str | Path | None = None,
) -> object:
    environment = build_natron_environment()
    executable = (
        Path(natron_executable)
        if natron_executable is not None
        else get_natron_executable(environment)
    )
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    command = [
        str(executable),
        "--onload",
        str(get_smart_read_onload_script_path()),
        str(comp_path),
    ]
    _log_step(diagnostic_log, f"Open comp: Natron command {command!r}")
    selected_output_log_path = (
        Path(output_log_path) if output_log_path is not None else None
    )
    if selected_output_log_path is None:
        process = subprocess.Popen(
            command,
            env=environment,
            creationflags=creation_flags,
        )
    else:
        try:
            selected_output_log_path.parent.mkdir(parents=True, exist_ok=True)
            output_log = selected_output_log_path.open("a", encoding="utf-8")
        except OSError as capture_error:
            _log_step(
                diagnostic_log,
                "Open comp: could not configure Natron stdout/stderr capture; "
                f"launching without it ({capture_error!r})",
            )
            selected_output_log_path = None
            process = subprocess.Popen(
                command,
                env=environment,
                creationflags=creation_flags,
            )
        else:
            with output_log:
                output_log.write(f"Starting Natron for {comp_path}\n")
                output_log.write(
                    f"Command: {subprocess.list2cmdline(command)}\n"
                )
                output_log.flush()
                process = subprocess.Popen(
                    command,
                    env=environment,
                    creationflags=creation_flags,
                    stdout=output_log,
                    stderr=subprocess.STDOUT,
                )
            _log_step(
                diagnostic_log,
                "Open comp: Natron stdout/stderr log is "
                f"{selected_output_log_path}",
            )
    _log_step(
        diagnostic_log,
        f"Open comp: Natron process started with PID {process.pid}",
    )
    return process


def _open_comp_path(
    comp_path: Path,
    opener: CompOpener | None = None,
    natron_executable: str | Path | None = None,
    diagnostic_log: DiagnosticLog | None = None,
    output_log_path: str | Path | None = None,
) -> object | None:
    _log_step(diagnostic_log, f"Open comp: verifying project {comp_path}")
    if not comp_path.is_file():
        _log_step(diagnostic_log, "Open comp: project file does not exist")
        raise CompNotFoundError(comp_path)
    try:
        if opener is not None:
            _log_step(diagnostic_log, "Open comp: launching through custom opener")
            process = opener(comp_path)
        else:
            process = open_comp_in_natron(
                comp_path,
                natron_executable,
                diagnostic_log,
                output_log_path,
            )
    except OSError as error:
        _log_step(diagnostic_log, f"Open comp: launch failed with {error!r}")
        raise CompOpenError(comp_path, error) from error
    _log_step(diagnostic_log, "Open comp: launch request completed")
    return process


def open_comp(
    show_root: str | Path,
    sequence_name: str,
    shot_name: str,
    *,
    opener: CompOpener | None = None,
    natron_executable: str | Path | None = None,
    hydration_progress: HydrationProgress | None = None,
    diagnostic_log: DiagnosticLog | None = None,
    output_log_path: str | Path | None = None,
) -> OpenCompResult:
    comp_path = get_comp_path(show_root, sequence_name, shot_name)
    _log_step(diagnostic_log, f"Open comp: resolved project {comp_path}")
    if not comp_path.is_file():
        _log_step(diagnostic_log, "Open comp: resolved project is missing")
        raise CompNotFoundError(comp_path)
    _log_step(diagnostic_log, "Open comp: hydrating latest source sequence")
    hydration = hydrate_latest_source_sequence(
        show_root,
        sequence_name,
        shot_name,
        progress=hydration_progress,
    )
    _log_step(
        diagnostic_log,
        f"Open comp: hydration completed with {hydration.hydrated_files} files",
    )
    process = _open_comp_path(
        comp_path,
        opener,
        natron_executable,
        diagnostic_log,
        output_log_path,
    )
    return OpenCompResult(
        comp_path=comp_path,
        created=False,
        hydrated_source_files=hydration.hydrated_files,
        process=process,
        output_log_path=(
            Path(output_log_path)
            if output_log_path and Path(output_log_path).is_file()
            else None
        ),
    )


def create_and_open_comp(
    show_root: str | Path,
    sequence_name: str,
    shot_name: str,
    *,
    smart_write_outputs: SmartWriteOutputOptions | None = None,
    opener: CompOpener | None = None,
    natron_executable: str | Path | None = None,
    hydration_progress: HydrationProgress | None = None,
    diagnostic_log: DiagnosticLog | None = None,
    output_log_path: str | Path | None = None,
) -> OpenCompResult:
    _log_step(diagnostic_log, "Create and open comp: hydrating latest source sequence")
    hydration = hydrate_latest_source_sequence(
        show_root,
        sequence_name,
        shot_name,
        progress=hydration_progress,
    )
    _log_step(
        diagnostic_log,
        f"Create and open comp: hydration completed with {hydration.hydrated_files} files",
    )
    try:
        create_options: dict[str, object] = {
            "smart_write_outputs": smart_write_outputs,
        }
        if diagnostic_log is not None:
            create_options["diagnostic_log"] = diagnostic_log
        create_result = create_comp(
            show_root,
            sequence_name,
            shot_name,
            **create_options,
        )
    except CompAlreadyExistsError as error:
        comp_path = error.comp_path
        created = False
        _log_step(diagnostic_log, f"Create and open comp: using existing {comp_path}")
    else:
        comp_path = create_result.target_path
        created = True
        _log_step(diagnostic_log, f"Create and open comp: created {comp_path}")

    process = _open_comp_path(
        comp_path,
        opener,
        natron_executable,
        diagnostic_log,
        output_log_path,
    )
    return OpenCompResult(
        comp_path=comp_path,
        created=created,
        hydrated_source_files=hydration.hydrated_files,
        process=process,
        output_log_path=(
            Path(output_log_path)
            if output_log_path and Path(output_log_path).is_file()
            else None
        ),
    )
