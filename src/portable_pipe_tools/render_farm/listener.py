from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


DEFAULT_POLL_INTERVAL_SECONDS = 15
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
