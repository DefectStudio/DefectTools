from __future__ import annotations

from datetime import datetime
import getpass
import json
import os
from pathlib import Path
import platform
import re
import sys
import threading
import traceback
from typing import Callable, Iterable


DIAGNOSTIC_LOG_FILENAME = "auto_comp_natron_verbose.log"
MAX_DIAGNOSTIC_LOG_BYTES = 5 * 1024 * 1024
DIAGNOSTIC_LOG_BACKUP_COUNT = 3
AUTO_COMP_LOG_FOLDER_NAME = "AutoComp Natron"


def _safe_user_folder_name(username: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", username).strip(" .")
    return cleaned or "Unknown User"


def get_dropbox_info_paths() -> tuple[Path, ...]:
    paths: list[Path] = []
    for environment_name in ("APPDATA", "LOCALAPPDATA"):
        environment_path = os.environ.get(environment_name)
        if not environment_path:
            continue
        candidate = Path(environment_path) / "Dropbox" / "info.json"
        if candidate not in paths:
            paths.append(candidate)
    return tuple(paths)


def _path_is_within(candidate: Path, parent: Path) -> bool:
    candidate_text = os.path.normcase(os.path.abspath(candidate))
    parent_text = os.path.normcase(os.path.abspath(parent))
    try:
        return os.path.commonpath((candidate_text, parent_text)) == parent_text
    except ValueError:
        return False


def get_dropbox_host_id(
    repository_root: str | Path,
    *,
    info_paths: Iterable[Path] | None = None,
) -> str | None:
    """Find the Dropbox account/computer identity containing the repository."""

    repository = Path(repository_root).expanduser()
    matches: list[tuple[int, str]] = []
    selected_info_paths = (
        get_dropbox_info_paths() if info_paths is None else tuple(info_paths)
    )
    for info_path in selected_info_paths:
        try:
            account_data = json.loads(info_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(account_data, dict):
            continue
        for account in account_data.values():
            if not isinstance(account, dict):
                continue
            host_id = account.get("host")
            if host_id is None or isinstance(host_id, bool):
                continue
            for dropbox_path in (account.get("path"), account.get("root_path")):
                if not dropbox_path:
                    continue
                if not _path_is_within(repository, Path(str(dropbox_path))):
                    continue
                safe_host_id = re.sub(
                    r"[^A-Za-z0-9._-]",
                    "_",
                    str(host_id).strip(),
                )
                if safe_host_id:
                    matches.append((len(str(dropbox_path)), safe_host_id))
    if not matches:
        return None
    return max(matches, key=lambda match: match[0])[1]


def get_shared_diagnostic_log_directory(
    repository_root: str | Path,
    *,
    log_username: str | None = None,
    windows_username: str | None = None,
    computer_name: str | None = None,
    dropbox_info_paths: Iterable[Path] | None = None,
) -> Path:
    """Return the Dropbox-backed per-user directory for AutoComp logs."""

    selected_log_username = str(log_username or "").strip()
    if selected_log_username:
        identity_folder = _safe_user_folder_name(selected_log_username)
    else:
        dropbox_host_id = get_dropbox_host_id(
            repository_root,
            info_paths=dropbox_info_paths,
        )
        if dropbox_host_id:
            identity_folder = f"Dropbox-{dropbox_host_id}"
        else:
            safe_username = _safe_user_folder_name(
                windows_username or getpass.getuser()
            )
            safe_computer_name = _safe_user_folder_name(
                computer_name or platform.node() or "Unknown Computer"
            )
            identity_folder = f"Windows-{safe_username}@{safe_computer_name}"
    return (
        Path(repository_root).expanduser()
        / "Development"
        / "Logs"
        / AUTO_COMP_LOG_FOLDER_NAME
        / identity_folder
    )


def get_default_diagnostic_log_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    log_root = Path(local_app_data) if local_app_data else Path.home()
    return (
        log_root
        / "PortablePipeTools"
        / "AutoCompNatron"
        / DIAGNOSTIC_LOG_FILENAME
    )


class VerboseDiagnosticLog:
    """Small, crash-safe diagnostic log that can be toggled at runtime."""

    def __init__(
        self,
        path: Path,
        *,
        enabled: bool = False,
        daily_directory: Path | None = None,
        now: Callable[[], datetime] | None = None,
        log_username: str | None = None,
    ) -> None:
        self._fallback_path = path
        self._daily_directory = daily_directory
        self._now = now or (lambda: datetime.now().astimezone())
        self._identity_details = {
            "windows_username": getpass.getuser(),
            "computer_name": platform.node() or "Unknown Computer",
        }
        if log_username:
            self._identity_details["log_username"] = log_username
        self.enabled = False
        self._lock = threading.Lock()
        if enabled:
            self.set_enabled(True)

    @property
    def path(self) -> Path:
        if self._daily_directory is not None:
            return self._daily_directory / f"{self._now().date().isoformat()}.log"
        return self._fallback_path

    def set_daily_directory(self, directory: Path) -> None:
        selected_directory = Path(directory)
        if selected_directory == self._daily_directory:
            return
        previous_path = self.path
        self._daily_directory = selected_directory
        if self.enabled:
            self.write(
                "Verbose log destination configured",
                previous_log_path=previous_path,
                log_path=self.path,
            )

    def set_log_username(self, username: str) -> None:
        selected_username = str(username).strip()
        if selected_username:
            self._identity_details["log_username"] = selected_username
        else:
            self._identity_details.pop("log_username", None)

    def natron_output_log_path(
        self,
        process_kind: str,
        item_name: str,
    ) -> Path:
        """Return the shared daily log used by AutoComp and all Natron processes."""

        del process_kind, item_name
        return self.path

    def set_enabled(self, enabled: bool) -> None:
        if enabled == self.enabled:
            return
        if enabled:
            self.enabled = True
            self.write(
                "Verbose logging enabled",
                python=sys.version.replace("\n", " "),
                platform=platform.platform(),
                process_id=os.getpid(),
                working_directory=Path.cwd(),
            )
            return
        self.write("Verbose logging disabled")
        self.enabled = False

    def write(self, event: str, **details: object) -> None:
        if not self.enabled:
            return
        timestamp = self._now().isoformat(timespec="milliseconds")
        event_details = dict(self._identity_details)
        if self._daily_directory is not None:
            event_details["log_identity"] = self._daily_directory.name
        event_details.update(details)
        detail_text = "".join(
            f" | {key}={value!r}" for key, value in event_details.items()
        )
        self._append(f"[{timestamp}] {event}{detail_text}\n")

    def exception(
        self,
        event: str,
        error: BaseException,
        **details: object,
    ) -> None:
        if not self.enabled:
            return
        self.write(event, error=repr(error), **details)
        formatted = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        for line in formatted.rstrip().splitlines():
            self._append(f"    {line}\n")

    def _append(self, text: str) -> None:
        try:
            with self._lock:
                log_path = self.path
                log_path.parent.mkdir(parents=True, exist_ok=True)
                if self._daily_directory is None:
                    self._rotate_if_needed(log_path, len(text.encode("utf-8")))
                with log_path.open("a", encoding="utf-8") as log_file:
                    log_file.write(text)
        except OSError:
            # Diagnostic logging must never interrupt an artist's operation.
            return

    def _rotate_if_needed(self, log_path: Path, incoming_bytes: int) -> None:
        try:
            current_size = log_path.stat().st_size
        except OSError:
            return
        if current_size + incoming_bytes <= MAX_DIAGNOSTIC_LOG_BYTES:
            return

        oldest_backup = log_path.with_suffix(
            log_path.suffix + f".{DIAGNOSTIC_LOG_BACKUP_COUNT}"
        )
        oldest_backup.unlink(missing_ok=True)
        for index in range(DIAGNOSTIC_LOG_BACKUP_COUNT - 1, 0, -1):
            source = log_path.with_suffix(log_path.suffix + f".{index}")
            destination = log_path.with_suffix(
                log_path.suffix + f".{index + 1}"
            )
            if source.exists():
                source.replace(destination)
        log_path.replace(log_path.with_suffix(log_path.suffix + ".1"))
