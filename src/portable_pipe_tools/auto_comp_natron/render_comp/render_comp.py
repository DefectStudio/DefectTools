from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import tempfile
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
    def __init__(self, comp_path: Path, error: OSError) -> None:
        self.comp_path = comp_path
        self.original_error = error
        super().__init__(f"Could not start the render for {comp_path}: {error}")


class CompRenderFailedError(RuntimeError):
    pass


@dataclass(frozen=True)
class RenderCompResult:
    comp_path: Path
    process: subprocess.Popen[bytes]
    status_path: Path
    hydrated_source_files: int = 0


@dataclass(frozen=True)
class RenderCompCompletion:
    comp_path: Path
    rendered_smart_writes: int
    hydrated_source_files: int = 0


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
    environment[RENDER_STATUS_ENV] = str(status_path)
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(
            [
                str(renderer),
                "--onload",
                str(get_smart_write_render_script_path()),
                str(comp_path),
            ],
            env=environment,
            creationflags=creation_flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as error:
        status_path.unlink(missing_ok=True)
        raise CompRenderLaunchError(comp_path, error) from error

    return RenderCompResult(
        comp_path=comp_path,
        process=process,
        status_path=status_path,
        hydrated_source_files=hydration.hydrated_files,
    )


def poll_render_comp(result: RenderCompResult) -> RenderCompCompletion | None:
    return_code = result.process.poll()
    if return_code is None:
        return None

    try:
        payload = json.loads(result.status_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CompRenderFailedError(
            f"Natron finished without a valid SmartWrite render result: {error}"
        ) from error
    finally:
        result.status_path.unlink(missing_ok=True)

    state = str(payload.get("state") or "")
    message = str(payload.get("message") or "").strip()
    if return_code != 0 or state != "complete":
        detail = message or f"Natron exited with code {return_code}."
        raise CompRenderFailedError(detail)

    return RenderCompCompletion(
        comp_path=result.comp_path,
        rendered_smart_writes=int(payload.get("rendered_smart_writes") or 0),
        hydrated_source_files=result.hydrated_source_files,
    )
