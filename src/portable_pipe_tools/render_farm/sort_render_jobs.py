from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from portable_pipe_tools.render_farm.render_job import RenderJob
from portable_pipe_tools.render_farm.render_time import render_duration_seconds


SORTABLE_JOB_COLUMNS = frozenset(
    {
        "job_name",
        "worker",
        "user",
        "status",
        "render_time",
        "errors",
        "progress",
        "submitted",
    }
)
DEFAULT_DESCENDING_COLUMNS = frozenset(
    {"render_time", "errors", "progress", "submitted"}
)


def default_sort_descending(column: str) -> bool:
    """Return the most useful initial direction for a Jobs column."""
    _validate_column(column)
    return column in DEFAULT_DESCENDING_COLUMNS


def sort_render_jobs(
    jobs: Iterable[RenderJob],
    column: str,
    descending: bool = False,
) -> list[RenderJob]:
    """Return jobs sorted for a Jobs-panel column, with blanks at the end."""
    _validate_column(column)
    populated: list[tuple[Any, RenderJob]] = []
    missing: list[RenderJob] = []

    for job in jobs:
        value = _sort_value(job, column)
        if value is None or value == "":
            missing.append(job)
        else:
            populated.append((value, job))

    populated.sort(key=lambda item: item[0], reverse=descending)
    return [job for _value, job in populated] + missing


def _sort_value(job: RenderJob, column: str) -> Any:
    if column == "job_name":
        return job.job_name.casefold()
    if column == "worker":
        if job.status.casefold() != "rendering":
            return ""
        return job.worker.casefold()
    if column == "user":
        return (job.submitted_user or job.submitted_by).casefold()
    if column == "status":
        return job.status.casefold()
    if column == "render_time":
        return render_duration_seconds(
            job.render_started_utc,
            job.render_finished_utc,
            running=job.status.casefold() == "rendering",
        )
    if column == "errors":
        return job.error_count
    if column == "progress":
        return job.progress
    if column == "submitted":
        return _timestamp_value(job.submitted_utc)
    raise AssertionError(f"Unhandled render-job sort column: {column}")


def _timestamp_value(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _validate_column(column: str) -> None:
    if column not in SORTABLE_JOB_COLUMNS:
        raise ValueError(f"Unsupported render-job sort column: {column}")
