from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RenderJob:
    """One render-farm job assembled from its queue folder and JSON payloads."""

    project: str
    submitted_project: str
    queue_name: str
    status: str
    job_folder: Path
    job_json_path: Path
    result_json_path: Path
    job_id: str
    job_name: str
    shot_name: str
    render_version: int | None
    submitted_user: str
    submitted_by: str
    submitted_utc: str
    priority: int | None
    worker: str
    frame_start: int | None
    frame_end: int | None
    frame_count: int | None
    progress: float
    error_count: int
    render_started_utc: str
    render_finished_utc: str
    output_directory: str
    render_config: str
    job_data: dict[str, Any] = field(default_factory=dict)
    result_data: dict[str, Any] = field(default_factory=dict)
    load_error: str | None = None
    control_source: str = "filesystem"
