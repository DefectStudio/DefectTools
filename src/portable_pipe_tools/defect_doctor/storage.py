"""Human-readable, atomic conversation storage. No third-party dependencies."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def default_data_dir() -> Path:
    override = os.environ.get("DEFECT_DOCTOR_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    return base / "Defect" / "DefectDoctor"


@dataclass
class Message:
    role: str
    content: str
    created_at: str = field(default_factory=timestamp)
    id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class Session:
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = "New session"
    created_at: str = field(default_factory=timestamp)
    updated_at: str = field(default_factory=timestamp)
    messages: list[Message] = field(default_factory=list)
    draft: str = ""

    def add(self, role: str, content: str) -> Message:
        message = Message(role, content)
        self.messages.append(message)
        if role == "user" and self.title == "New session":
            title = " ".join(content.split())
            self.title = title[:53].rstrip() + ("…" if len(title) > 53 else "")
        self.updated_at = timestamp()
        return message


class Store:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.sessions_dir = self.directory / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.warnings: list[str] = []

    def _session_path(self, session_id: str) -> Path:
        if str(UUID(session_id)) != session_id:
            raise ValueError("Invalid session ID")
        return self.sessions_dir / f"{session_id}.json"

    @staticmethod
    def _write(path: Path, value: dict) -> None:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent,
                prefix=f".{path.stem}-", suffix=".tmp", delete=False,
            ) as handle:
                temporary = Path(handle.name)
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def save(self, session: Session) -> None:
        self._write(self._session_path(session.id), {"version": 1, **asdict(session)})

    def load(self, session_id: str) -> Session:
        value = json.loads(self._session_path(session_id).read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("version") != 1:
            raise ValueError("Unsupported conversation format")
        if value.get("id") != session_id:
            raise ValueError("Conversation ID does not match its filename")
        for name in ("title", "created_at", "updated_at", "draft"):
            if not isinstance(value.get(name), str):
                raise ValueError(f"Invalid {name}")
        for name in ("created_at", "updated_at"):
            datetime.fromisoformat(value[name])
        raw_messages = value.get("messages")
        if not isinstance(raw_messages, list):
            raise ValueError("Invalid messages")
        messages = []
        for raw in raw_messages:
            if not isinstance(raw, dict) or raw.get("role") not in ("user", "assistant"):
                raise ValueError("Invalid message role")
            for name in ("content", "id", "created_at"):
                if not isinstance(raw.get(name), str):
                    raise ValueError(f"Invalid message {name}")
            datetime.fromisoformat(raw["created_at"])
            messages.append(Message(**{key: raw[key] for key in ("role", "content", "created_at", "id")}))
        return Session(**{key: value[key] for key in ("id", "title", "created_at", "updated_at", "draft")}, messages=messages)

    def list_sessions(self) -> list[Session]:
        sessions = []
        self.warnings.clear()
        for path in self.sessions_dir.glob("*.json"):
            try:
                sessions.append(self.load(path.stem))
            except (OSError, ValueError, TypeError, KeyError) as exc:
                self.warnings.append(f"Could not read {path.name}: {exc}")
        return sorted(sessions, key=lambda session: session.updated_at, reverse=True)

    def preferences(self) -> dict:
        try:
            value = json.loads((self.directory / "preferences.json").read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_preferences(self, value: dict) -> None:
        self._write(self.directory / "preferences.json", value)


class InstanceLock:
    """Prevent two windows from overwriting the same local conversations."""

    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.handle = (directory / ".instance.lock").open("a+b")
        try:
            self.handle.seek(0, os.SEEK_END)
            if self.handle.tell() == 0:
                self.handle.write(b"0")
                self.handle.flush()
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.handle.close()
            raise RuntimeError("Defect Doctor is already using this history folder.") from exc

    def close(self) -> None:
        if not self.handle.closed:
            self.handle.close()
