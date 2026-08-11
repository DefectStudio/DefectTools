from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def render_duration_seconds(
    render_started_utc: Any,
    render_finished_utc: Any = None,
    *,
    running: bool = False,
    now_utc: datetime | None = None,
) -> int | None:
    """Return elapsed render seconds, using the current time for active jobs."""
    started = _parse_timestamp_utc(render_started_utc)
    if started is None:
        return None

    finished = _parse_timestamp_utc(render_finished_utc)
    if finished is None:
        if not running:
            return None
        finished = _as_utc(now_utc or datetime.now(timezone.utc))

    if finished < started:
        return None
    return int((finished - started).total_seconds())


def format_render_time(
    render_started_utc: Any,
    render_finished_utc: Any = None,
    *,
    running: bool = False,
    now_utc: datetime | None = None,
) -> str:
    """Format a job's live or final render duration as HH:MM:SS."""
    total_seconds = render_duration_seconds(
        render_started_utc,
        render_finished_utc,
        running=running,
        now_utc=now_utc,
    )
    if total_seconds is None:
        return ""

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _parse_timestamp_utc(value: Any) -> datetime | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
