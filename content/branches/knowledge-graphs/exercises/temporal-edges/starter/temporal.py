from collections.abc import Iterable
from typing import NamedTuple


class Fact(NamedTuple):
    subject: str
    predicate: str
    object: str
    valid_from: str
    valid_to: str | None


class TemporalGraph:
    def __init__(self, functional: Iterable[str] = ()) -> None:
        raise NotImplementedError

    def assert_fact(self, subject: str, predicate: str, obj: str, valid_from: str) -> None:
        """Record that the triple became true on `valid_from` (YYYY-MM-DD)."""
        raise NotImplementedError

    def invalidate(self, subject: str, predicate: str, obj: str, at: str) -> bool:
        """Record that the triple stopped being true on `at`. False if it was not valid then."""
        raise NotImplementedError

    def facts_at(
        self,
        date: str,
        subject: str | None = None,
        predicate: str | None = None,
        obj: str | None = None,
    ) -> list[Fact]:
        """Facts valid on `date` that match the pattern."""
        raise NotImplementedError

    def history(self, subject: str, predicate: str) -> list[Fact]:
        """Every interval of this subject and predicate, any object."""
        raise NotImplementedError
