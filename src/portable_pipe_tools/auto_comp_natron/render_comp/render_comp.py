from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
from uuid import uuid4
import xml.etree.ElementTree as ElementTree

from portable_pipe_tools.auto_comp_natron.create_comp import get_comp_path
from portable_pipe_tools.auto_comp_natron.open_comp import (
    CompNotFoundError,
    build_natron_environment,
    get_natron_executable,
    get_portable_natron_plugins_path,
)
from portable_pipe_tools.auto_comp_natron.source_media import (
    HydrationProgress,
    hydrate_latest_source_sequence,
)


SMART_WRITE_PLUGIN_ID = "com.portablepipetools.SmartWrite"
RENDER_STATUS_ENV = "PORTABLE_PIPE_SMART_WRITE_RENDER_STATUS"
RENDER_PROJECT_ENV = "PORTABLE_PIPE_SMART_WRITE_PROJECT"
LOAD_RENDER_PROJECT_COMMAND = (
    "import os; app.loadProject(os.environ[{0!r}])".format(RENDER_PROJECT_ENV)
)
_MIN_VIDEO_BYTES = 1024
_VIDEO_EXTENSIONS = {".mp4", ".mov"}
_RENDER_EXIT_GRACE_SECONDS = 2.0


class SmartWriteNotFoundError(RuntimeError):
    def __init__(self, comp_path: Path) -> None:
        self.comp_path = comp_path
        super().__init__(f"No SmartWrite node was found in {comp_path}.")


class CompRenderInspectionError(RuntimeError):
    def __init__(self, comp_path: Path, error: Exception) -> None:
        self.comp_path = comp_path
        self.original_error = error
        super().__init__(f"Could not inspect {comp_path}: {error}")


class CompRenderLaunchError(OSError):
    def __init__(
        self,
        comp_path: Path,
        error: OSError,
        log_path: Path | None = None,
    ) -> None:
        self.comp_path = comp_path
        self.original_error = error
        self.log_path = log_path
        log_detail = f" (Render log: {log_path})" if log_path else ""
        super().__init__(
            f"Could not start the render for {comp_path}: {error}{log_detail}"
        )


class CompRenderFailedError(RuntimeError):
    pass


@dataclass
class RenderCompResult:
    comp_path: Path
    process: subprocess.Popen[bytes]
    status_path: Path
    hydrated_source_files: int = 0
    log_path: Path | None = None
    _progress_completed_frames: int = field(
        default=0,
        init=False,
        repr=False,
    )
    _progress_total_frames: int = field(default=0, init=False, repr=False)
    _progress_percent: float = field(default=0.0, init=False, repr=False)
    _progress_completed_outputs: int = field(
        default=0,
        init=False,
        repr=False,
    )
    _progress_total_outputs: int = field(default=0, init=False, repr=False)
    _progress_finalizing: bool = field(default=False, init=False, repr=False)
    _paused: bool = field(default=False, init=False, repr=False)


@dataclass(frozen=True)
class RenderCompCompletion:
    comp_path: Path
    rendered_smart_writes: int
    hydrated_source_files: int = 0


@dataclass(frozen=True)
class RenderCompProgress:
    completed_frames: int
    total_frames: int
    percent: float
    current_frame: int | float | None = None
    completed_outputs: int = 0
    total_outputs: int = 0
    finalizing: bool = False


def get_smart_write_render_script_path() -> Path:
    return get_portable_natron_plugins_path() / "SmartWriteRenderAll.py"


def get_natron_renderer_executable(
    natron_executable: str | Path | None = None,
    environment: dict[str, str] | None = None,
) -> Path:
    executable = (
        Path(natron_executable)
        if natron_executable is not None
        else get_natron_executable(environment)
    )
    if executable.stem.casefold() == "natronrenderer":
        return executable
    return executable.with_name(f"NatronRenderer{executable.suffix}")


def _require_smart_write(comp_path: Path) -> None:
    try:
        project = ElementTree.parse(comp_path)
    except (OSError, ElementTree.ParseError) as error:
        raise CompRenderInspectionError(comp_path, error) from error

    if not any(
        (plugin_id.text or "").strip() == SMART_WRITE_PLUGIN_ID
        for plugin_id in project.iter("Plugin_id")
    ):
        raise SmartWriteNotFoundError(comp_path)


def _new_status_path() -> Path:
    status_directory = Path(tempfile.gettempdir()) / "portable_pipe_tools"
    status_directory.mkdir(parents=True, exist_ok=True)
    return status_directory / f"smart_write_render_{uuid4().hex}.json"


def _new_log_path(shot_name: str) -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    log_root = (
        Path(local_app_data)
        if local_app_data
        else Path(tempfile.gettempdir())
    )
    log_directory = (
        log_root
        / "PortablePipeTools"
        / "AutoCompNatron"
        / "render_logs"
    )
    log_directory.mkdir(parents=True, exist_ok=True)
    safe_shot_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", shot_name).strip("._")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return log_directory / (
        f"{timestamp}_{safe_shot_name or 'unknown_shot'}_{uuid4().hex[:8]}.log"
    )


def _append_render_log(log_path: Path | None, message: str) -> None:
    if log_path is None:
        return
    try:
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(
                f"[{datetime.now().astimezone().isoformat(timespec='milliseconds')}] "
                f"[AutoComp] {message}\n"
            )
    except OSError:
        # Diagnostics must never be allowed to interrupt a render or queue.
        return


def _failure_artifact_detail(result: RenderCompResult) -> str:
    paths = []
    if result.log_path is not None:
        paths.append(f"Render log: {result.log_path}")
    if result.status_path.exists():
        paths.append(f"Status data: {result.status_path}")
    return f" ({'; '.join(paths)})" if paths else ""


def render_comp(
    show_root: str | Path,
    sequence_name: str,
    shot_name: str,
    *,
    natron_executable: str | Path | None = None,
    hydration_progress: HydrationProgress | None = None,
) -> RenderCompResult:
    comp_path = get_comp_path(show_root, sequence_name, shot_name)
    if not comp_path.is_file():
        raise CompNotFoundError(comp_path)
    _require_smart_write(comp_path)

    hydration = hydrate_latest_source_sequence(
        show_root,
        sequence_name,
        shot_name,
        progress=hydration_progress,
    )
    environment = build_natron_environment()
    renderer = get_natron_renderer_executable(natron_executable, environment)
    status_path = _new_status_path()
    log_path = _new_log_path(shot_name)
    environment[RENDER_STATUS_ENV] = str(status_path)
    environment[RENDER_PROJECT_ENV] = str(comp_path)
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    command = [
        str(renderer),
        "--cmd",
        LOAD_RENDER_PROJECT_COMMAND,
        str(get_smart_write_render_script_path()),
    ]
    _append_render_log(log_path, f"Starting render for {comp_path}")
    _append_render_log(log_path, f"Renderer: {renderer}")
    _append_render_log(log_path, f"Command: {subprocess.list2cmdline(command)}")
    _append_render_log(log_path, f"Status file: {status_path}")
    _append_render_log(
        log_path,
        f"Hydrated source files: {hydration.hydrated_files}",
    )
    try:
        # A project passed as NatronRenderer's main argument is rendered again
        # automatically. Load it first, then run our Python script as the main
        # argument so only the script's explicitly submitted tasks are rendered.
        with log_path.open("a", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                command,
                env=environment,
                creationflags=creation_flags,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
    except OSError as error:
        _append_render_log(log_path, f"Launch failed: {error!r}")
        status_path.unlink(missing_ok=True)
        raise CompRenderLaunchError(comp_path, error, log_path) from error

    _append_render_log(log_path, f"NatronRenderer PID: {process.pid}")

    return RenderCompResult(
        comp_path=comp_path,
        process=process,
        status_path=status_path,
        hydrated_source_files=hydration.hydrated_files,
        log_path=log_path,
    )


def _set_windows_process_suspended(process_id: int, suspended: bool) -> None:
    import ctypes
    from ctypes import wintypes

    process_suspend_resume = 0x0800
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    process_handle = kernel32.OpenProcess(
        process_suspend_resume,
        False,
        process_id,
    )
    if not process_handle:
        raise ctypes.WinError(ctypes.get_last_error())

    operation_name = "NtSuspendProcess" if suspended else "NtResumeProcess"
    operation = getattr(ntdll, operation_name)
    operation.argtypes = [wintypes.HANDLE]
    operation.restype = wintypes.LONG
    try:
        status = operation(process_handle)
        if status != 0:
            raise OSError(
                f"{operation_name} failed for process {process_id} "
                f"with NTSTATUS 0x{status & 0xFFFFFFFF:08X}."
            )
    finally:
        kernel32.CloseHandle(process_handle)


def _set_process_suspended(process_id: int, suspended: bool) -> None:
    if os.name == "nt":
        _set_windows_process_suspended(process_id, suspended)
        return

    stop_signal = getattr(signal, "SIGSTOP", None)
    continue_signal = getattr(signal, "SIGCONT", None)
    selected_signal = stop_signal if suspended else continue_signal
    if selected_signal is None:
        raise OSError("Process pause and resume are not supported on this platform.")
    os.kill(process_id, selected_signal)


def pause_render_comp(result: RenderCompResult) -> bool:
    """Suspend a running NatronRenderer without discarding render state."""

    if result._paused or result.process.poll() is not None:
        return False
    _set_process_suspended(result.process.pid, True)
    result._paused = True
    _append_render_log(result.log_path, "Renderer process suspended by user.")
    return True


def resume_render_comp(result: RenderCompResult) -> bool:
    """Resume a NatronRenderer previously suspended by this application."""

    if not result._paused:
        return False
    if result.process.poll() is not None:
        result._paused = False
        return False
    _set_process_suspended(result.process.pid, False)
    result._paused = False
    _append_render_log(result.log_path, "Renderer process resumed by user.")
    return True


def terminate_render_comp(
    result: RenderCompResult,
    *,
    timeout: float = 2.0,
) -> bool:
    """Stop a running Natron renderer, escalating if it will not exit."""

    process = result.process
    if process.poll() is not None:
        result._paused = False
        return False
    if result._paused:
        try:
            _set_process_suspended(process.pid, False)
        except OSError:
            pass
        result._paused = False
    _append_render_log(result.log_path, "Termination requested for renderer.")
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _append_render_log(
            result.log_path,
            "Renderer did not terminate before timeout; killing it.",
        )
        process.kill()
        process.wait(timeout=timeout)
    _append_render_log(
        result.log_path,
        f"Renderer stopped with exit code {process.poll()}.",
    )
    return True


def _frame_path(filename: str, frame: int) -> Path | None:
    hash_match = re.search(r"#+", filename)
    if hash_match is not None:
        width = len(hash_match.group(0))
        return Path(
            filename[: hash_match.start()]
            + str(frame).zfill(width)
            + filename[hash_match.end() :]
        )

    printf_match = re.search(r"%0?(\d*)d", filename)
    if printf_match is None:
        return None
    width_text = printf_match.group(1)
    rendered_frame = (
        str(frame).zfill(int(width_text)) if width_text else str(frame)
    )
    return Path(
        filename[: printf_match.start()]
        + rendered_frame
        + filename[printf_match.end() :]
    )


def _filesystem_output_progress(output: object) -> tuple[int, int | None]:
    if not isinstance(output, dict):
        return 0, None
    try:
        first_frame = int(output["first_frame"])
        last_frame = int(output["last_frame"])
        frame_increment = max(1, int(output["frame_increment"]))
    except (KeyError, TypeError, ValueError):
        return 0, None

    frames = range(first_frame, last_frame + 1, frame_increment)
    filename = str(output.get("filename") or "")
    if not filename:
        return 0, None
    first_path = _frame_path(filename, first_frame)
    if first_path is not None:
        completed_frames = []
        for frame in frames:
            frame_path = _frame_path(filename, frame)
            try:
                if (
                    frame_path is not None
                    and frame_path.is_file()
                    and frame_path.stat().st_size > 0
                ):
                    completed_frames.append(frame)
            except OSError:
                continue
        return (
            len(completed_frames),
            max(completed_frames) if completed_frames else None,
        )

    output_path = Path(filename)
    minimum_size = (
        _MIN_VIDEO_BYTES
        if output_path.suffix.casefold() in _VIDEO_EXTENSIONS
        else 1
    )
    try:
        is_complete = (
            output_path.is_file() and output_path.stat().st_size >= minimum_size
        )
    except OSError:
        is_complete = False
    if not is_complete:
        return 0, None
    total_frames = max(0, ((last_frame - first_frame) // frame_increment) + 1)
    return total_frames, last_frame


def read_render_comp_progress(
    result: RenderCompResult,
) -> RenderCompProgress | None:
    try:
        payload = json.loads(result.status_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    if str(payload.get("state") or "") != "rendering":
        return None

    outputs = payload.get("outputs")
    filesystem_current_frames: list[int] = []
    completed_outputs = 0
    total_outputs = 0
    if isinstance(outputs, dict) and outputs:
        total_frames = 0
        completed_frames = 0
        try:
            for output in outputs.values():
                if not isinstance(output, dict):
                    continue
                output_total = max(0, int(output.get("total") or 0))
                callback_completed = min(
                    output_total,
                    max(0, int(output.get("completed") or 0)),
                )
                filesystem_completed, filesystem_current = (
                    _filesystem_output_progress(output)
                )
                filename = str(output.get("filename") or "")
                is_sequence_output = bool(
                    re.search(r"#+|%0?\d*d", filename)
                )
                observed_completed = min(
                    output_total,
                    (
                        filesystem_completed
                        if is_sequence_output
                        else max(callback_completed, filesystem_completed)
                    ),
                )
                total_frames += output_total
                completed_frames += observed_completed
                if output_total:
                    total_outputs += 1
                    if observed_completed >= output_total:
                        completed_outputs += 1
                if filesystem_current is not None:
                    filesystem_current_frames.append(filesystem_current)
        except (TypeError, ValueError):
            return None
    else:
        try:
            total_frames = max(0, int(payload.get("total_frames") or 0))
            completed_frames = max(
                0,
                int(payload.get("completed_frames") or 0),
            )
        except (TypeError, ValueError):
            return None
        completed_frames = min(completed_frames, total_frames)

    finalizing = bool(total_frames and completed_frames >= total_frames)
    percent = (
        (completed_frames / total_frames) * 100.0 if total_frames else 0.0
    )
    if finalizing:
        percent = 99.0

    # Filesystem-backed progress can briefly observe fewer files while a writer
    # replaces an output or Dropbox refreshes a placeholder. A stale status
    # snapshot must never make an active queue job move backwards.
    completed_frames = max(
        completed_frames,
        result._progress_completed_frames,
    )
    total_frames = max(total_frames, result._progress_total_frames)
    completed_frames = min(completed_frames, total_frames)
    percent = max(percent, result._progress_percent)
    completed_outputs = max(
        completed_outputs,
        result._progress_completed_outputs,
    )
    total_outputs = max(total_outputs, result._progress_total_outputs)
    finalizing = finalizing or result._progress_finalizing
    result._progress_completed_frames = completed_frames
    result._progress_total_frames = total_frames
    result._progress_percent = percent
    result._progress_completed_outputs = completed_outputs
    result._progress_total_outputs = total_outputs
    result._progress_finalizing = finalizing

    current_frame = payload.get("current_frame")
    if not isinstance(current_frame, (int, float)):
        current_frame = (
            max(filesystem_current_frames)
            if filesystem_current_frames
            else None
        )
    return RenderCompProgress(
        completed_frames=completed_frames,
        total_frames=total_frames,
        percent=percent,
        current_frame=current_frame,
        completed_outputs=completed_outputs,
        total_outputs=total_outputs,
        finalizing=finalizing,
    )


def poll_render_comp(result: RenderCompResult) -> RenderCompCompletion | None:
    return_code = result.process.poll()
    payload = None
    if return_code is None:
        try:
            payload = json.loads(result.status_path.read_text(encoding="utf-8"))
            completed_age = time.time() - result.status_path.stat().st_mtime
        except (OSError, ValueError):
            return None
        if (
            str(payload.get("state") or "") != "complete"
            or completed_age < _RENDER_EXIT_GRACE_SECONDS
        ):
            return None
        terminate_render_comp(result)
        return_code = result.process.poll()

    if payload is None:
        try:
            payload = json.loads(result.status_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            _append_render_log(
                result.log_path,
                f"Renderer exited with code {return_code}; final status "
                f"could not be read: {error!r}",
            )
            raise CompRenderFailedError(
                "Natron finished without a valid SmartWrite render result: "
                f"{error}{_failure_artifact_detail(result)}"
            ) from error

    state = str(payload.get("state") or "")
    message = str(payload.get("message") or "").strip()
    _append_render_log(
        result.log_path,
        f"Renderer exited with code {return_code}; final status payload: "
        f"{json.dumps(payload, sort_keys=True)}",
    )
    # Natron 2.5 returns 1 when closeProject() quits a background script even
    # after every output has been validated. The per-render status file is
    # unique, so a complete state is the authoritative success signal.
    if state != "complete":
        detail = message or f"Natron exited with code {return_code}."
        _append_render_log(result.log_path, f"Render classified as failed: {detail}")
        raise CompRenderFailedError(
            f"{detail}{_failure_artifact_detail(result)}"
        )

    result.status_path.unlink(missing_ok=True)
    _append_render_log(
        result.log_path,
        "Render classified as successful after SmartWrite output validation.",
    )

    return RenderCompCompletion(
        comp_path=result.comp_path,
        rendered_smart_writes=int(payload.get("rendered_smart_writes") or 0),
        hydrated_source_files=result.hydrated_source_files,
    )
