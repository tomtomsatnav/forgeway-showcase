from dataclasses import dataclass

SOURCE_RANK = {"user": 3, "document": 2, "inferred": 1}


@dataclass(frozen=True)
class Fact:
    subject: str  # normalised: stripped and lower-cased
    attribute: str  # normalised the same way
    value: str  # stripped, case kept
    at: float  # when it was stated
    source: str  # "user", "document" or "inferred"


class FactStore:
    """One current value per (subject, attribute), with a history of superseded values."""

    def __init__(self) -> None:
        self._current: dict[tuple[str, str], Fact] = {}
        self._history: dict[tuple[str, str], list[Fact]] = {}

    def assert_fact(
        self, subject: str, attribute: str, value: str, at: float, source: str = "user"
    ) -> str:
        """Apply the resolution rules and return "added", "confirmed", "stale", "disputed"
        or "updated"."""
        raise NotImplementedError("work through the rules in order")

    def get(self, subject: str, attribute: str) -> Fact | None:
        raise NotImplementedError

    def history(self, subject: str, attribute: str) -> list[Fact]:
        """Superseded facts for the key, oldest first."""
        raise NotImplementedError

    def facts(self) -> list[Fact]:
        """Every current fact, sorted by (subject, attribute)."""
        raise NotImplementedError

    def retract(self, subject: str, attribute: str) -> bool:
        """Remove the current fact and its history. True if there was one."""
        raise NotImplementedError
