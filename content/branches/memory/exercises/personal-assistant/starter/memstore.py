from collections.abc import Callable, MutableMapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Episode:
    id: int
    text: str
    importance: int  # 1 to 10
    at: float  # when it was stored, from the clock
    reflected: bool = False


@dataclass(frozen=True)
class Fact:
    subject: str  # stripped, lower-cased
    attribute: str  # stripped, lower-cased
    value: str  # stripped, case kept
    at: float  # when it was last stated or confirmed
    evidence: tuple[int, ...] = ()  # ids of the episodes it was derived from


class MemoryStore:
    """Every user's memory, kept as one JSON text per user in `data`.

    `data` maps a user id to that user's whole memory as JSON text. Keep it up to date after
    every change, and read from it rather than from attributes of this object, so that a new
    `MemoryStore` over a copy of `data` (a restarted process) sees everything.
    """

    def __init__(self, data: MutableMapping[str, str], clock: Callable[[], float]) -> None:
        self.data = data
        self.clock = clock

    def add_episode(self, user_id: str, text: str, importance: int) -> int:
        """Store an episode and return its id (1, 2, 3 ... per user, never reused)."""
        raise NotImplementedError

    def episodes(self, user_id: str) -> list[Episode]:
        """The user's episodes in id order."""
        raise NotImplementedError

    def mark_reflected(self, user_id: str, ids: list[int]) -> None:
        raise NotImplementedError

    def set_fact(
        self,
        user_id: str,
        subject: str,
        attribute: str,
        value: str,
        evidence: tuple[int, ...] = (),
    ) -> str:
        """Returns "added", "confirmed" or "updated"; see the brief for the rule."""
        raise NotImplementedError

    def facts(self, user_id: str) -> list[Fact]:
        """Current facts sorted by (subject, attribute)."""
        raise NotImplementedError

    def history(self, user_id: str, subject: str, attribute: str) -> list[Fact]:
        """Superseded values for the key, oldest first."""
        raise NotImplementedError

    def recall(self, user_id: str, query: str, k: int = 3) -> str:
        """The text of a `recall` tool result; see the brief for the exact format."""
        raise NotImplementedError

    def forget(self, user_id: str, topic: str) -> int:
        """Delete what mentions `topic`, and what was derived from it. Returns how many items."""
        raise NotImplementedError

    def forget_user(self, user_id: str) -> bool:
        """Delete everything about the user. True if there was anything."""
        raise NotImplementedError
