from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from portable_pipe_tools.render_farm.render_job import RenderJob


MISSING_VALUE = "--"


@dataclass(frozen=True)
class JobDetail:
    property_name: str
    value: str


@dataclass(frozen=True)
class JobDetailSection:
    name: str
    details: tuple[JobDetail, ...]


def get_render_job_details(job: RenderJob) -> tuple[JobDetailSection, ...]:
    """Build Deadline-style grouped property rows for one RenderJob."""
    data = job.job_data
    result_value = job.result_data or data.get("result", {})
    result = result_value if isinstance(result_value, dict) else {}
    outputs_value = data.get("outputs", {})
    outputs = outputs_value if isinstance(outputs_value, dict) else {}

    frame_end = job.frame_end
    if (
        frame_end is not None
        and str(data.get("frame_end_semantics", "")).lower() == "exclusive"
    ):
        frame_end -= 1
    frame_range = _format_frame_range(job.frame_start, frame_end)

    general = JobDetailSection(
        "General",
        (
            JobDetail("Job Name", _display(job.job_name)),
            JobDetail("Job ID", _display(job.job_id)),
            JobDetail("Project", _display(job.project)),
            JobDetail("Submitted Project", _display(job.submitted_project)),
            JobDetail("Job Type", _display(data.get("job_type"))),
            JobDetail("Status", _display(job.status.title())),
            JobDetail("Queue", _display(job.queue_name)),
            JobDetail("Priority", _display(job.priority)),
            JobDetail("Attempt", _display(data.get("attempt"))),
            JobDetail(
                "Black List",
                _format_worker_list(data.get("blacklisted_workers")),
            ),
        ),
    )
    submission = JobDetailSection(
        "Submission",
        (
            JobDetail("Submitted User", _display(job.submitted_user)),
            JobDetail("Submitted Computer", _display(job.submitted_by)),
            JobDetail("Submitted", _format_timestamp(job.submitted_utc)),
            JobDetail("Batch ID", _display(data.get("batch_id"))),
        ),
    )
    render = JobDetailSection(
        "Render",
        (
            JobDetail("Shot", _display(job.shot_name)),
            JobDetail("Render Version", _format_version(job.render_version)),
            JobDetail("Frame Range", frame_range),
            JobDetail("Frame Count", _display(job.frame_count)),
            JobDetail("Render Configuration", _display(job.render_config)),
            JobDetail("Configuration Mode", _display(data.get("config_mode"))),
            JobDetail("Level", _display(data.get("level"))),
            JobDetail("Sequence", _display(data.get("sequence"))),
            JobDetail("Unreal Engine", _display(data.get("engine_version"))),
        ),
    )
    worker_and_timing = JobDetailSection(
        "Worker & Timing",
        (
            JobDetail("Worker", _display(job.worker)),
            JobDetail("Claimed", _format_timestamp(data.get("claimed_utc"))),
            JobDetail("Render Started", _format_timestamp(job.render_started_utc)),
            JobDetail("Render Finished", _format_timestamp(job.render_finished_utc)),
            JobDetail(
                "Render Duration",
                _format_duration(job.render_started_utc, job.render_finished_utc),
            ),
            JobDetail("Progress", f"{job.progress:g}%"),
        ),
    )
    output = JobDetailSection(
        "Output",
        (
            JobDetail("Output Directory", _display(job.output_directory)),
            JobDetail(
                "Output Filename Format",
                _display(data.get("output_file_name_format")),
            ),
            JobDetail(
                "MP4 Filename Format",
                _display(data.get("mp4_file_name_format")),
            ),
            JobDetail("MP4 Enabled", _format_bool(outputs.get("mp4"))),
            JobDetail("EXR Enabled", _format_bool(outputs.get("exr"))),
            JobDetail("Hero Enabled", _format_bool(outputs.get("hero"))),
            JobDetail(
                "Reported Output Files",
                _display(result.get("output_file_count")),
            ),
        ),
    )
    result_section = JobDetailSection(
        "Result",
        (
            JobDetail("Result Status", _display(result.get("status") or job.status)),
            JobDetail("Exit Code", _display(result.get("exit_code"))),
            JobDetail("Reason", _display(result.get("reason"))),
            JobDetail("Simulated", _format_bool(result.get("simulated"))),
            JobDetail("Error Count", _display(job.error_count)),
            JobDetail("Metadata Warning", _display(job.load_error)),
        ),
    )
    advanced = JobDetailSection(
        "Advanced",
        (
            JobDetail("Unreal Project", _display(data.get("uproject"))),
            JobDetail(
                "Submitted Git Commit",
                _display(data.get("submitted_git_commit")),
            ),
            JobDetail(
                "Rendered Git Commit",
                _display(data.get("rendered_git_commit")),
            ),
            JobDetail(
                "Submission Sync Policy",
                _display(data.get("sync_policy")),
            ),
            JobDetail(
                "Worker Sync Policy",
                _display(data.get("worker_sync_policy")),
            ),
            JobDetail("Git Branch", _display(data.get("git_branch"))),
            JobDetail("Git Upstream", _display(data.get("git_upstream"))),
            JobDetail(
                "Git Commit Before Pull",
                _display(data.get("git_commit_before_pull")),
            ),
            JobDetail(
                "Git Commit After Pull",
                _display(data.get("git_commit_after_pull")),
            ),
            JobDetail(
                "Git Pull Summary",
                _display(data.get("git_pull_summary")),
            ),
            JobDetail("Job Folder", str(job.job_folder)),
            JobDetail("Job JSON", str(job.job_json_path)),
            JobDetail("Result JSON", _existing_path_or_missing(job.result_json_path)),
        ),
    )
    return (
        general,
        submission,
        render,
        worker_and_timing,
        output,
        result_section,
        advanced,
    )


def _display(value: Any) -> str:
    if value is None or value == "":
        return MISSING_VALUE
    return str(value)


def _format_worker_list(value: Any) -> str:
    if not isinstance(value, (list, tuple)):
        return _display(value)
    workers = [str(worker).strip() for worker in value if str(worker).strip()]
    return ", ".join(workers) if workers else MISSING_VALUE


def _format_bool(value: Any) -> str:
    if value is None:
        return MISSING_VALUE
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "on"}:
            return "Yes"
        if normalized in {"false", "no", "0", "off"}:
            return "No"
    return "Yes" if bool(value) else "No"


def _format_version(version: int | None) -> str:
    return f"v{version:03d}" if version is not None else MISSING_VALUE


def _format_frame_range(start: int | None, end: int | None) -> str:
    if start is None and end is None:
        return MISSING_VALUE
    if start is None:
        return str(end)
    if end is None:
        return str(start)
    return f"{start}-{end}"


def _parse_timestamp(value: Any) -> datetime | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_timestamp(value: Any) -> str:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return _display(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.strftime("%Y-%m-%d %H:%M:%S %Z").rstrip()


def _format_duration(start_value: Any, finish_value: Any) -> str:
    started = _parse_timestamp(start_value)
    finished = _parse_timestamp(finish_value)
    if started is None or finished is None or finished < started:
        return MISSING_VALUE
    total_seconds = int((finished - started).total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _existing_path_or_missing(path: Path) -> str:
    return str(path) if path.is_file() else MISSING_VALUE
