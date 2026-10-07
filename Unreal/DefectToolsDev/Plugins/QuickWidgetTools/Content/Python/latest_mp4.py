"""Copy a rendered MP4 to a stable, shot-only latest filename."""

import os
import re
import shutil
import time
import uuid


SHOT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9]+_\d{3}_\d{4,}$")
MP4_SHOT_PREFIX_PATTERN = re.compile(r"^([A-Za-z0-9]+_\d{3}_\d{4,})(?=_|$)")
LATEST_FOLDER_NAME = "_latestmp4"
LOCK_RETRY_TIMEOUT_SECONDS = 15.0
LOCK_RETRY_INTERVAL_SECONDS = 0.25
TRANSIENT_WINDOWS_LOCK_ERRORS = {5, 32, 33}


def destination_from_mp4(source_mp4, job_name=""):
    """Return the latest subfolder inside the source output folder and shot-only MP4 path."""
    source_path = os.path.abspath(os.path.normpath(os.fspath(source_mp4)))
    file_stem, extension = os.path.splitext(os.path.basename(source_path))
    if extension.casefold() != ".mp4":
        raise ValueError(f"Expected an MP4 source: {source_path}")

    match = MP4_SHOT_PREFIX_PATTERN.match(file_stem)
    if match:
        shot_name = match.group(1)
    else:
        shot_name = str(job_name or "").strip()
        if not SHOT_NAME_PATTERN.fullmatch(shot_name):
            raise ValueError(f"Could not derive a valid shot name from MP4: {source_path}")

    latest_folder = os.path.join(os.path.dirname(source_path), LATEST_FOLDER_NAME)
    return os.path.join(latest_folder, f"{shot_name}.mp4")


def _retry_windows_lock(operation):
    """Retry temporary Windows sharing/access errors for a bounded period."""
    deadline = time.monotonic() + LOCK_RETRY_TIMEOUT_SECONDS
    while True:
        try:
            return operation()
        except OSError as exc:
            remaining = deadline - time.monotonic()
            if getattr(exc, "winerror", None) not in TRANSIENT_WINDOWS_LOCK_ERRORS or remaining <= 0:
                raise
            time.sleep(min(LOCK_RETRY_INTERVAL_SECONDS, remaining))


def copy_latest_mp4(source_mp4, job_name=""):
    """Atomically replace the latest MP4; retain the previous copy on failure."""
    source_path = os.path.abspath(os.path.normpath(os.fspath(source_mp4)))
    destination_path = destination_from_mp4(source_path, job_name)
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"Rendered MP4 does not exist: {source_path}")
    if os.path.getsize(source_path) <= 0:
        raise ValueError(f"Rendered MP4 is empty: {source_path}")

    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
    temporary_path = os.path.join(
        os.path.dirname(destination_path),
        f".{os.path.basename(destination_path)}.{uuid.uuid4().hex}.partial",
    )
    try:
        _retry_windows_lock(lambda: shutil.copy2(source_path, temporary_path))
        if os.path.getsize(temporary_path) <= 0:
            raise ValueError(f"Copied MP4 is empty: {source_path}")
        _retry_windows_lock(lambda: os.replace(temporary_path, destination_path))
    finally:
        if os.path.exists(temporary_path):
            try:
                os.remove(temporary_path)
            except OSError:
                pass
    return destination_path
