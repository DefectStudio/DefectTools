from __future__ import annotations

from pathlib import Path

from portable_pipe_tools.render_farm.queue import retry_transient_windows_lock
from portable_pipe_tools.render_farm.render_job import RenderJob
from portable_pipe_tools.render_farm.unreal_runner import (
    UNREAL_LOG_FILENAME,
    UNREAL_STDOUT_FILENAME,
)


def get_render_log(job: RenderJob) -> str:
    """Load the best available render log text for one render job."""
    result = job.result_data or job.job_data.get("result", {})
    result_data = result if isinstance(result, dict) else {}

    requested_names = (
        result_data.get("unreal_log_file"),
        UNREAL_LOG_FILENAME,
        result_data.get("unreal_stdout_file"),
        UNREAL_STDOUT_FILENAME,
    )
    candidate_paths: list[Path] = []
    for requested_name in requested_names:
        if not requested_name:
            continue
        # Log references are expected to name files inside the job package.
        candidate = job.job_folder / Path(str(requested_name)).name
        if candidate not in candidate_paths:
            candidate_paths.append(candidate)

    for log_path in candidate_paths:
        if not log_path.is_file():
            continue
        log_text = retry_transient_windows_lock(
            operation=lambda path=log_path: path.read_text(
                encoding="utf-8-sig",
                errors="replace",
            ),
            description=f"Read render log {log_path}",
        )
        if log_text:
            return log_text
        return f"Render log is currently empty:\n{log_path}"

    reason = str(result_data.get("reason") or "").strip()
    lines = [
        f"No Unreal render log is available for {job.job_name}.",
        f"Status: {job.status}",
        f"Job folder: {job.job_folder}",
    ]
    if reason:
        lines.extend(("", f"Result: {reason}"))
    if job.load_error:
        lines.extend(("", f"Metadata warning: {job.load_error}"))
    return "\n".join(lines)
