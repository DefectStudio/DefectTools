"""The Hermes integration boundary; this build deliberately has no remote endpoint.

An adapter supplies text deltas from reply(). The GUI runs that iterator on a
worker thread and owns persistence. Computer-control requests need a separate,
explicitly wired bridge; merely connecting a chat adapter never grants access.
"""

from __future__ import annotations

from threading import Event
from typing import Iterable, Protocol, Sequence

from .storage import Message


class AgentClient(Protocol):
    name: str
    connected: bool

    def reply(self, messages: Sequence[Message], cancel: Event) -> Iterable[str]: ...


class DisconnectedAgent:
    name = "Hermes"
    connected = False

    def reply(self, messages: Sequence[Message], cancel: Event) -> Iterable[str]:
        raise ConnectionError("Hermes is not connected yet. Your message is saved locally.")
