from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum


DEFAULT_POLL_INTERVAL_SECONDS = 15
DEFAULT_MAXIMUM_IDLE_POLL_INTERVAL_SECONDS = 120
POLL_INTERVAL_JITTER_FRACTION = 0.10
MINIMUM_POLL_INTERVAL_SECONDS = 1
MAXIMUM_POLL_INTERVAL_SECONDS = 3_600


class ListenerAction(str, Enum):
    CHECK_NOW = "check_now"
    WAIT = "wait"
    FINISH_CURRENT = "finish_current"
    STOPPED = "stopped"


def parse_poll_interval_seconds(value: str | int) -> int:
    raw_value = str(value).strip()
    try:
        seconds = int(raw_value)
    except ValueError as error:
        raise ValueError("Polling interval must be a whole number of seconds.") from error

    if not MINIMUM_POLL_INTERVAL_SECONDS <= seconds <= MAXIMUM_POLL_INTERVAL_SECONDS:
        raise ValueError(
            "Polling interval must be between "
            f"{MINIMUM_POLL_INTERVAL_SECONDS} and "
            f"{MAXIMUM_POLL_INTERVAL_SECONDS} seconds."
        )
    return seconds


def adaptive_poll_interval_seconds(
    initial_interval_seconds: int,
    consecutive_empty_checks: int,
    *,
    maximum_interval_seconds: int = DEFAULT_MAXIMUM_IDLE_POLL_INTERVAL_SECONDS,
    jitter_fraction: float = POLL_INTERVAL_JITTER_FRACTION,
    random_value: float | None = None,
) -> int:
    """Return an exponentially backed-off, slightly jittered idle poll delay."""
    initial_interval_seconds = parse_poll_interval_seconds(
        initial_interval_seconds
    )
    maximum_interval_seconds = parse_poll_interval_seconds(
        maximum_interval_seconds
    )
    if consecutive_empty_checks < 0:
        raise ValueError("Consecutive empty checks cannot be negative.")
    if not 0 <= jitter_fraction <= 1:
        raise ValueError("Polling jitter fraction must be between 0 and 1.")

    random_sample = random.random() if random_value is None else random_value
    if not 0 <= random_sample <= 1:
        raise ValueError("Polling jitter random value must be between 0 and 1.")

    target_maximum = max(initial_interval_seconds, maximum_interval_seconds)
    target_interval = initial_interval_seconds
    for _empty_check in range(consecutive_empty_checks):
        if target_interval >= target_maximum:
            break
        target_interval = min(target_maximum, target_interval * 2)
    jitter_multiplier = 1 + ((random_sample * 2 - 1) * jitter_fraction)
    return max(
        MINIMUM_POLL_INTERVAL_SECONDS,
        int(round(target_interval * jitter_multiplier)),
    )


def waiting_status(seconds_remaining: int) -> str:
    unit = "second" if seconds_remaining == 1 else "seconds"
    return f"Waiting for jobs — next check in {seconds_remaining} {unit}"


@dataclass
class ContinuousWorkerState:
    active: bool = False
    stop_requested: bool = False
    job_running: bool = False

    def start(self) -> bool:
        if self.active:
            return False
        self.active = True
        self.stop_requested = False
        self.job_running = False
        return True

    def begin_job_check(self) -> bool:
        if not self.active or self.stop_requested or self.job_running:
            return False
        self.job_running = True
        return True

    def request_stop(self) -> ListenerAction:
        if not self.active:
            return ListenerAction.STOPPED
        self.stop_requested = True
        if self.job_running:
            return ListenerAction.FINISH_CURRENT
        self.active = False
        return ListenerAction.STOPPED

    def finish_job_check(self, job_was_available: bool) -> ListenerAction:
        if not self.job_running:
            raise RuntimeError("No automatic worker job check is running.")
        self.job_running = False
        if self.stop_requested:
            self.active = False
            return ListenerAction.STOPPED
        return (
            ListenerAction.CHECK_NOW
            if job_was_available
            else ListenerAction.WAIT
        )

    def finish_job_check_with_error(self) -> ListenerAction:
        if not self.job_running:
            raise RuntimeError("No automatic worker job check is running.")
        self.job_running = False
        if self.stop_requested:
            self.active = False
            return ListenerAction.STOPPED
        return ListenerAction.WAIT
