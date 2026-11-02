"""Attempt-scoped MRG progress and monotonic inactivity deadlines.

Engine ticks, file timestamps and lease heartbeats are deliberately not progress.
The frame counters describe work submitted by MRG, not validated output files.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
import json
import math
from pathlib import Path
import time
from typing import Any

UNREAL_PROGRESS_FILENAME = "unreal_progress.json"
DEFAULT_NO_PROGRESS_TIMEOUT_SECONDS = 600.0
DEFAULT_STARTUP_TIMEOUT_SECONDS = 1800.0
DEFAULT_FINALIZATION_TIMEOUT_SECONDS = 1800.0
_PHASES = {"startup", "warmup", "rendering", "finalizing", "complete"}
_COUNTERS = (
    "current_frame", "segment_index", "output_frame_index",
    "output_sub_sample_index", "engine_warm_up_frame_index",
)


def validate_progress(value: Any, job: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        return None
    if value.get("job_id") != job.get("job_id"):
        return None
    attempt = value.get("attempt")
    if type(attempt) is not int or attempt != job.get("attempt", 0):
        return None
    phase = value.get("phase")
    percent = value.get("progress")
    if type(phase) is not str or phase not in _PHASES or type(percent) not in (int, float):
        return None
    if not 0 <= percent <= 100 or not math.isfinite(percent):
        return None
    result = {"schema_version": 1, "phase": phase, "progress": float(percent)}
    for field in (*_COUNTERS, "total_frames"):
        count = value.get(field, 0)
        if type(count) is not int or not 0 <= count <= 2**31 - 1:
            return None
        result[field] = count
    sequence_frame = value.get("sequence_frame")
    if type(sequence_frame) is int and -(2**31) <= sequence_frame <= 2**31 - 1:
        result["sequence_frame"] = sequence_frame
    return result


class RenderProgressMonitor:
    def __init__(
        self, folder: Path, job: dict[str, Any], *,
        no_progress_timeout_seconds: float = DEFAULT_NO_PROGRESS_TIMEOUT_SECONDS,
        startup_timeout_seconds: float = DEFAULT_STARTUP_TIMEOUT_SECONDS,
        finalization_timeout_seconds: float = DEFAULT_FINALIZATION_TIMEOUT_SECONDS,
        output_paths: Iterable[Path] = (),
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        for value in (no_progress_timeout_seconds, startup_timeout_seconds,
                      finalization_timeout_seconds):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Render inactivity timeouts must be positive finite seconds")
        self.path = folder / UNREAL_PROGRESS_FILENAME
        self.job = job
        self.clock = monotonic
        self.started = self.last_advance = self.phase_started = monotonic()
        self.timeouts = {"startup": startup_timeout_seconds,
                         "warmup": no_progress_timeout_seconds,
                         "rendering": no_progress_timeout_seconds,
                         "finalizing": finalization_timeout_seconds,
                         "complete": finalization_timeout_seconds}
        self.latest: dict[str, Any] = dict(
            schema_version=1, phase="startup", progress=0.0, current_frame=0,
            total_frames=0, segment_index=0, output_frame_index=0,
            output_sub_sample_index=0, engine_warm_up_frame_index=0,
        )
        self.high_water = (0, 0, 0, 0, 0)
        self.seen_stages: set[tuple[int, str]] = {(0, "startup")}
        self.finalizing = False
        self.output_paths = tuple(output_paths)
        self.output_high_water: dict[Path, tuple[int, int]] = {}
        self.next_output_check = self.started
        self._sample_output_progress(self.started, baseline=True)

    def _sample_output_progress(self, now: float, *, baseline: bool = False) -> None:
        if not baseline and (not self.finalizing or now < self.next_output_check):
            return
        self.next_output_check = now + 10.0
        for path in self.output_paths:
            try:
                if path.is_file():
                    stat = path.stat()
                    current = (1, stat.st_size)
                elif path.is_dir():
                    # Only the current job's known output folder, never a show-wide scan.
                    count = size = 0
                    for child in path.iterdir():
                        if child.is_file() and child.suffix.casefold() in {".exr", ".png", ".jpg", ".jpeg", ".mp4", ".mov"}:
                            count += 1
                            size += child.stat().st_size
                    current = (count, size)
                else:
                    current = (0, 0)
            except OSError:
                continue
            previous = self.output_high_water.get(path, (0, 0))
            if not baseline and (current[0] > previous[0] or current[1] > previous[1]):
                self.last_advance = now
            self.output_high_water[path] = (max(current[0], previous[0]), max(current[1], previous[1]))

    def poll(self) -> dict[str, Any]:
        now = self.clock()
        try:
            # An incomplete receipt must not terminate a healthy Unreal process.
            with self.path.open("r", encoding="utf-8") as handle:
                data = handle.read(65537)
            value = validate_progress(json.loads(data), self.job) if len(data) <= 65536 else None
        except (OSError, ValueError, TypeError):
            value = None
        if value is not None:
            phase = value["phase"]
            key = tuple(value[field] for field in _COUNTERS)
            stage = (value["segment_index"], phase)
            order = {"startup": 0, "warmup": 1, "rendering": 2, "finalizing": 3, "complete": 4}
            advanced = key > self.high_water
            forward_phase = order[phase] >= order[self.latest["phase"]]
            # Once finalization starts, late/regressing receipts cannot restart rendering.
            eligible = (phase != "startup" or self.latest["phase"] == "startup") and (
                forward_phase or advanced) and (not self.finalizing or phase in {"finalizing", "complete"})
            if eligible and (advanced or stage not in self.seen_stages or key == self.high_water):
                changed_stage = stage not in self.seen_stages
                if advanced or changed_stage:
                    self.last_advance = now
                if phase != self.latest["phase"] and changed_stage:
                    self.phase_started = now
                self.seen_stages.add(stage)
                self.high_water = max(key, self.high_water)
                self.finalizing |= phase in {"finalizing", "complete"}
                self.latest = value
        self._sample_output_progress(now)
        return self.snapshot(now)

    def snapshot(self, now: float | None = None) -> dict[str, Any]:
        now = self.clock() if now is None else now
        return dict(self.latest, last_progress_age_seconds=max(0.0, now - self.last_advance),
                    elapsed_seconds=max(0.0, now - self.started))

    def stalled_reason(self) -> str | None:
        phase = self.latest["phase"]
        now = self.clock()
        # Loading has its own allowance, not a timer reset by repeated startup receipts.
        age = now - (self.started if phase == "startup" else self.last_advance)
        limit = self.timeouts[phase]
        if age < limit:
            return None
        return (f"Unreal made no render progress for {age / 60:g} minutes "
                f"during {phase} (limit {limit / 60:g} minutes; "
                f"render frame {self.latest['current_frame']}/{self.latest['total_frames']}).")
