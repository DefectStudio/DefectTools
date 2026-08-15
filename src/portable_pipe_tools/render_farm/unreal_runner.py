from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
from threading import Thread
import time
from typing import Any

from portable_pipe_tools.render_farm.git_sync import GIT_PULL_LOG_FILENAME
from portable_pipe_tools.render_farm.local_paths import (
    prepare_worker_output_mapping,
)
from portable_pipe_tools.render_farm.queue import (
    JOB_FILENAME,
    path_exists_with_retry,
    read_json_object,
    retry_transient_windows_lock,
    write_json_atomic,
)


LOGGER = logging.getLogger("render_worker")

UNREAL_RESULT_FILENAME = "unreal_result.json"
UNREAL_LOG_FILENAME = "unreal.log"
UNREAL_STDOUT_FILENAME = "unreal_stdout.log"
RENDER_COMMAND_FILENAME = "render_command.txt"

DEFAULT_RENDER_TIMEOUT_SECONDS = 2.0 * 60.0 * 60.0
UNREAL_PROCESS_POLL_INTERVAL_SECONDS = 0.5
PYTHON_EXECUTOR_CLASS = "/Engine/PythonTypes.DefectRenderFarmExecutor"
HOST_EXECUTOR_CLASS = (
    "/Script/MovieRenderPipelineCore.MoviePipelinePythonHostExecutor"
)
COMMAND_LINE_PIPELINE_CLASS = (
    "/Script/MovieRenderPipelineCore.MoviePipeline"
)

_ENGINE_VERSION_RE = re.compile(r"(?<!\d)(\d+\.\d+)(?!\d)")
_COMMIT_RE = re.compile(r"[0-9a-fA-F]{40,64}")


@dataclass(frozen=True)
class UnrealExecutionResult:
    success: bool
    reason: str
    exit_code: int | None
    unreal_result: dict[str, Any] | None = None
    cancelled: bool = False

    def terminal_result_details(self) -> dict[str, Any]:
        unreal_result = self.unreal_result or {}
        return {
            "simulated": False,
            "exit_code": self.exit_code,
            "cancelled": self.cancelled,
            "unreal_result_file": UNREAL_RESULT_FILENAME,
            "unreal_reported_success": unreal_result.get("success"),
            "unreal_result_stage": unreal_result.get("stage"),
            "output_file_count": unreal_result.get("output_file_count", 0),
            "output_validation": unreal_result.get("output_validation"),
            "unreal_log_file": UNREAL_LOG_FILENAME,
            "unreal_stdout_file": UNREAL_STDOUT_FILENAME,
            "render_command_file": RENDER_COMMAND_FILENAME,
            "git_pull_log_file": GIT_PULL_LOG_FILENAME,
        }


def _as_path(value: str | Path) -> Path:
    return Path(os.path.abspath(Path(value).expanduser()))


def _load_uproject(uproject: Path) -> dict[str, Any]:
    try:
        data = json.loads(uproject.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise ValueError(f"Could not read Unreal project file {uproject}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in Unreal project file {uproject}")
    return data


def _engine_version_candidates(job: dict[str, Any], uproject_data: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    association = str(uproject_data.get("EngineAssociation") or "").strip()
    if association:
        match = _ENGINE_VERSION_RE.search(association)
        if match:
            candidates.append(match.group(1))

    engine_version = str(job.get("engine_version") or "").strip()
    match = _ENGINE_VERSION_RE.search(engine_version)
    if match and match.group(1) not in candidates:
        candidates.append(match.group(1))
    return candidates


def resolve_unreal_editor_cmd(
    job: dict[str, Any],
    configured_path: str | Path | None = None,
    local_uproject: str | Path | None = None,
) -> Path:
    if configured_path:
        configured = _as_path(configured_path)
        if not configured.is_file():
            raise FileNotFoundError(
                f"Configured UnrealEditor-Cmd.exe does not exist: {configured}"
            )
        return configured

    uproject = _as_path(local_uproject or str(job.get("uproject") or ""))
    uproject_data = _load_uproject(uproject)
    program_files = Path(os.environ.get("ProgramFiles") or r"C:\Program Files")
    for version in _engine_version_candidates(job, uproject_data):
        candidate = (
            program_files
            / "Epic Games"
            / f"UE_{version}"
            / "Engine"
            / "Binaries"
            / "Win64"
            / "UnrealEditor-Cmd.exe"
        )
        if candidate.is_file():
            return candidate

    path_match = shutil.which("UnrealEditor-Cmd.exe")
    if path_match:
        return _as_path(path_match)

    versions = ", ".join(_engine_version_candidates(job, uproject_data)) or "unknown"
    raise FileNotFoundError(
        "Could not locate UnrealEditor-Cmd.exe automatically for engine version(s) "
        f"{versions}. Configure it explicitly in the Render Worker."
    )


def resolve_unreal_project(
    job: dict[str, Any],
    local_uproject: str | Path | None = None,
) -> Path:
    selected_value = local_uproject or str(job.get("uproject") or "")
    uproject = _as_path(selected_value)
    if uproject.suffix.casefold() != ".uproject":
        raise ValueError(f"Local Unreal project must be a .uproject file: {uproject}")
    if not uproject.is_file():
        source = "configured local" if local_uproject else "submitted"
        raise FileNotFoundError(
            f"The {source} Unreal project does not exist on this worker: {uproject}"
        )

    submitted_project = str(job.get("project") or "").strip()
    if submitted_project and uproject.stem.casefold() != submitted_project.casefold():
        raise ValueError(
            "The configured local Unreal project does not match the farm job: "
            f"job project is '{submitted_project}', selected file is "
            f"'{uproject.name}'."
        )
    return uproject


def validate_real_render_job(
    job: dict[str, Any],
    local_uproject: str | Path | None = None,
) -> Path:
    if job.get("job_type") != "unreal_movie_render_graph":
        raise ValueError(
            "Real rendering requires a published Unreal Movie Render Graph job; "
            f"got job_type={job.get('job_type')!r}."
        )
    if job.get("test_job") is True:
        raise ValueError("A fake test job cannot be rendered with Unreal.")
    if job.get("status") != "rendering":
        raise ValueError(
            f"Expected claimed job status 'rendering', got {job.get('status')!r}."
        )
    for field_name in (
        "job_id",
        "uproject",
        "level",
        "sequence",
        "render_config",
        "output_directory",
    ):
        value = job.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Real render job is missing '{field_name}'.")

    uproject = resolve_unreal_project(job, local_uproject)

    overrides = job.get("graph_variable_overrides")
    if not isinstance(overrides, dict) or not overrides:
        raise ValueError("Real render job has no Movie Render Graph variable overrides.")
    return uproject


def _map_package_path(level_object_path: str) -> str:
    return level_object_path.split(".", 1)[0]


def build_unreal_command(
    claimed_folder: str | Path,
    job: dict[str, Any],
    unreal_editor_cmd: str | Path | None = None,
    validate_only: bool = False,
    local_uproject: str | Path | None = None,
) -> list[str]:
    uproject = validate_real_render_job(job, local_uproject)
    folder = _as_path(claimed_folder)
    executable = resolve_unreal_editor_cmd(job, unreal_editor_cmd, uproject)
    job_path = folder / JOB_FILENAME
    unreal_log_path = folder / UNREAL_LOG_FILENAME

    command = [
        str(executable),
        str(uproject),
        _map_package_path(job["level"]),
        "-game",
        f"-MoviePipelineLocalExecutorClass={HOST_EXECUTOR_CLASS}",
        f"-ExecutorPythonClass={PYTHON_EXECUTOR_CLASS}",
        # UE 5.8's command-line parser only accepts a legacy MoviePipeline
        # subclass here. The Python executor explicitly creates MovieGraphPipeline.
        f"-MoviePipelineClass={COMMAND_LINE_PIPELINE_CLASS}",
        f"-RenderFarmJob={job_path}",
        "-unattended",
        "-RenderOffscreen",
        "-NoSplash",
        "-NoLoadingScreen",
        "-NoScreenMessages",
        "-NoSound",
        "-NoP4",
        "-stdout",
        "-FullStdOutLogOutput",
        "-UTF8Output",
        f"-abslog={unreal_log_path}",
    ]
    if validate_only:
        command.append("-RenderFarmValidateOnly=true")
    return command


def _write_text_with_retry(path: Path, text: str) -> None:
    retry_transient_windows_lock(
        lambda: path.write_text(text, encoding="utf-8", newline="\n"),
        description=f"Write text file {path}",
    )


def _query_git_commit(project_directory: Path) -> str | None:
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            ["git", "-C", str(project_directory), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=creation_flags,
        )
    except (OSError, subprocess.SubprocessError) as error:
        LOGGER.warning("Could not record rendered Git commit: %s", error)
        return None

    commit = completed.stdout.strip()
    if completed.returncode != 0 or not _COMMIT_RE.fullmatch(commit):
        detail = completed.stderr.strip() or "Git did not return a commit hash"
        LOGGER.warning("Could not record rendered Git commit: %s", detail)
        return None
    return commit.lower()


def _should_forward_unreal_line(line: str) -> bool:
    lowered = line.casefold()
    return any(
        marker in lowered
        for marker in (
            "defectrenderfarmexecutor",
            "logmovierenderpipeline",
            "error:",
            "warning:",
            "fatal error",
        )
    )


def _pump_unreal_stdout(process: subprocess.Popen[str], log_path: Path) -> None:
    def pump() -> None:
        assert process.stdout is not None
        with log_path.open("w", encoding="utf-8", newline="\n") as handle:
            for line in process.stdout:
                handle.write(line)
                handle.flush()
                clean_line = line.rstrip("\r\n")
                if clean_line and _should_forward_unreal_line(clean_line):
                    LOGGER.info("Unreal: %s", clean_line)

    retry_transient_windows_lock(
        pump,
        description=f"Capture Unreal stdout in {log_path}",
    )


def _stop_unreal_process(process: subprocess.Popen[str]) -> None:
    try:
        process.terminate()
        process.wait(timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        process.kill()
        process.wait(timeout=30)


def _wait_for_unreal_process(
    process: subprocess.Popen[str],
    timeout_seconds: float,
    should_cancel: Callable[[], bool] | None = None,
) -> tuple[int | None, str | None]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        cancel_requested = False
        if should_cancel is not None:
            try:
                cancel_requested = should_cancel()
            except Exception as error:
                LOGGER.warning(
                    "Could not check for a worker STOP request; Unreal will "
                    "continue running: %s",
                    error,
                )
        if cancel_requested:
            _stop_unreal_process(process)
            return process.returncode, "cancelled"

        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            _stop_unreal_process(process)
            return process.returncode, "timed_out"

        try:
            exit_code = process.wait(
                timeout=min(
                    UNREAL_PROCESS_POLL_INTERVAL_SECONDS,
                    remaining_seconds,
                )
            )
            return exit_code, None
        except subprocess.TimeoutExpired:
            continue


def _read_unreal_result(path: Path) -> dict[str, Any] | None:
    if not path_exists_with_retry(path):
        return None
    return read_json_object(path)


def _format_timeout_duration(timeout_seconds: float) -> str:
    if timeout_seconds >= 3_600:
        hours = timeout_seconds / 3_600
        unit = "hour" if hours == 1 else "hours"
        return f"{hours:g} {unit}"
    if timeout_seconds >= 60:
        minutes = timeout_seconds / 60
        unit = "minute" if minutes == 1 else "minutes"
        return f"{minutes:g} {unit}"
    unit = "second" if timeout_seconds == 1 else "seconds"
    return f"{timeout_seconds:g} {unit}"


def _interpret_unreal_result(
    job: dict[str, Any],
    exit_code: int,
    unreal_result: dict[str, Any] | None,
) -> UnrealExecutionResult:
    if unreal_result is None:
        if exit_code != 0:
            return UnrealExecutionResult(
                False,
                f"UnrealEditor-Cmd exited with code {exit_code}.",
                exit_code,
                None,
            )
        return UnrealExecutionResult(
            False,
            "Unreal exited with code 0 but did not write unreal_result.json.",
            exit_code,
            None,
        )
    if unreal_result.get("job_id") != job.get("job_id"):
        return UnrealExecutionResult(
            False,
            "unreal_result.json job_id does not match the claimed farm job.",
            exit_code,
            unreal_result,
        )

    output_validation = unreal_result.get("output_validation")
    output_validation_succeeded = (
        isinstance(output_validation, dict)
        and output_validation.get("success") is True
    )
    if unreal_result.get("success") is True:
        output_file_count = unreal_result.get("output_file_count", 0)
        if exit_code == 0:
            return UnrealExecutionResult(
                True,
                (
                    "Unreal render completed successfully; "
                    f"{output_file_count} output file(s) reported."
                ),
                exit_code,
                unreal_result,
            )
        if output_validation_succeeded:
            return UnrealExecutionResult(
                True,
                (
                    "Unreal render completed successfully; "
                    f"{output_file_count} output file(s) were validated. "
                    f"UnrealEditor-Cmd then exited with code {exit_code} during "
                    "shutdown."
                ),
                exit_code,
                unreal_result,
            )

    if exit_code != 0:
        reason = f"UnrealEditor-Cmd exited with code {exit_code}."
        if unreal_result.get("reason"):
            reason += f" Unreal reported: {unreal_result['reason']}"
        return UnrealExecutionResult(False, reason, exit_code, unreal_result)

    if unreal_result.get("success") is not True:
        return UnrealExecutionResult(
            False,
            str(unreal_result.get("reason") or "Unreal reported render failure."),
            exit_code,
            unreal_result,
        )
    return UnrealExecutionResult(
        False,
        "Unreal reported success but output validation did not pass.",
        exit_code,
        unreal_result,
    )


def execute_unreal_job(
    claimed_folder: str | Path,
    job: dict[str, Any],
    unreal_editor_cmd: str | Path | None = None,
    timeout_seconds: float = DEFAULT_RENDER_TIMEOUT_SECONDS,
    local_uproject: str | Path | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> UnrealExecutionResult:
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    folder = _as_path(claimed_folder)
    uproject = validate_real_render_job(job, local_uproject)
    render_farm_root = folder.parent.parent
    output_mapping = prepare_worker_output_mapping(job, render_farm_root)
    LOGGER.info(
        "Derived worker-local show root from Render Farm folder: %s",
        output_mapping.local_show_file_server_path,
    )
    LOGGER.info(
        "Remapped render output: %s -> %s",
        output_mapping.submitted_output_directory,
        output_mapping.worker_output_directory,
    )
    LOGGER.info(
        "Portable output path: %s",
        output_mapping.output_relative_directory,
    )

    command = build_unreal_command(
        folder,
        job,
        unreal_editor_cmd,
        local_uproject=local_uproject,
    )
    uproject = _as_path(command[1])
    job_path = folder / JOB_FILENAME
    command_path = folder / RENDER_COMMAND_FILENAME
    stdout_path = folder / UNREAL_STDOUT_FILENAME
    unreal_result_path = folder / UNREAL_RESULT_FILENAME

    if path_exists_with_retry(unreal_result_path):
        stale_result_path = folder / (
            f"unreal_result.before_attempt_{job.get('attempt', 0)}.json"
        )
        if path_exists_with_retry(stale_result_path):
            raise FileExistsError(
                f"Cannot preserve stale Unreal result because destination exists: "
                f"{stale_result_path}"
            )
        retry_transient_windows_lock(
            lambda: unreal_result_path.rename(stale_result_path),
            description=(
                f"Archive stale Unreal result {unreal_result_path} -> {stale_result_path}"
            ),
        )

    rendered_commit = _query_git_commit(uproject.parent)
    worker_sync_policy = str(
        job.get("worker_sync_policy") or "current_checkout"
    ).strip()
    if worker_sync_policy == "latest_branch_git_pull_ff_only":
        pulled_commit = str(job.get("git_commit_after_pull") or "").strip()
        if not rendered_commit or rendered_commit.casefold() != pulled_commit.casefold():
            raise RuntimeError(
                "The worker Git checkout changed after the pre-job pull: "
                f"pulled commit={pulled_commit or 'unknown'}, "
                f"current commit={rendered_commit or 'unknown'}."
            )

    job["worker_uproject"] = str(uproject)
    job["rendered_git_commit"] = rendered_commit
    job["worker_sync_policy"] = worker_sync_policy
    write_json_atomic(job_path, job)
    if rendered_commit:
        LOGGER.info("Render checkout Git commit: %s", rendered_commit)
    LOGGER.info("Worker-local Unreal project: %s", uproject)
    if worker_sync_policy == "latest_branch_git_pull_ff_only":
        LOGGER.info(
            "Git sync verified: rendering the latest pulled '%s' branch at %s.",
            job.get("git_branch") or "current",
            rendered_commit,
        )
    else:
        LOGGER.warning(
            "No pre-job Git pull was recorded; rendering the worker's current checkout."
        )

    command_text = subprocess.list2cmdline(command)
    _write_text_with_retry(command_path, command_text + "\n")
    LOGGER.info("Render command: %s", command_text)

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        command,
        cwd=uproject.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=creation_flags,
    )
    LOGGER.info("Started UnrealEditor-Cmd process %s", process.pid)

    output_thread = Thread(
        target=_pump_unreal_stdout,
        args=(process, stdout_path),
        name="UnrealStdoutCapture",
        daemon=True,
    )
    output_thread.start()

    exit_code, stop_reason = _wait_for_unreal_process(
        process,
        timeout_seconds,
        should_cancel,
    )
    if stop_reason == "cancelled":
        LOGGER.warning("Worker STOP requested; Unreal render process interrupted.")
        output_thread.join(timeout=30)
        return UnrealExecutionResult(
            False,
            "Unreal render interrupted by worker STOP request.",
            exit_code,
            _read_unreal_result(unreal_result_path),
            cancelled=True,
        )

    if stop_reason == "timed_out":
        timeout_label = _format_timeout_duration(timeout_seconds)
        LOGGER.error(
            "Unreal render exceeded its %s timeout; stopping process.",
            timeout_label,
        )
        output_thread.join(timeout=30)
        return UnrealExecutionResult(
            False,
            f"Unreal render exceeded its {timeout_label} timeout.",
            exit_code,
            _read_unreal_result(unreal_result_path),
        )

    assert exit_code is not None
    output_thread.join(timeout=30)
    if output_thread.is_alive():
        LOGGER.warning("Unreal stdout capture thread did not finish promptly.")

    unreal_result = _read_unreal_result(unreal_result_path)
    result = _interpret_unreal_result(job, exit_code, unreal_result)
    LOGGER.info("Unreal execution result: %s", result.reason)
    return result
