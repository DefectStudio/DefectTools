from __future__ import annotations


AUTO_REFRESH_INTERVAL_MINUTES = (1, 2, 5, 10)
DEFAULT_AUTO_REFRESH_INTERVAL_MINUTES = 1
AUTO_REFRESH_INTERVAL_LABELS = tuple(
    f"{minutes} {'minute' if minutes == 1 else 'minutes'}"
    for minutes in AUTO_REFRESH_INTERVAL_MINUTES
)


def format_auto_refresh_interval(minutes: int) -> str:
    if minutes not in AUTO_REFRESH_INTERVAL_MINUTES:
        raise ValueError(f"Unsupported auto-refresh interval: {minutes}")
    return f"{minutes} {'minute' if minutes == 1 else 'minutes'}"


def parse_auto_refresh_interval(label: str) -> int:
    normalized = label.strip().casefold()
    for minutes in AUTO_REFRESH_INTERVAL_MINUTES:
        if normalized == format_auto_refresh_interval(minutes).casefold():
            return minutes
    raise ValueError(f"Unsupported auto-refresh interval: {label}")
