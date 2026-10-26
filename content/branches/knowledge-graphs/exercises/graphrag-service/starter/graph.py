from collections.abc import Iterable
from typing import NamedTuple


class Fact(NamedTuple):
    subject: str
    predicate: str
    object: str
    valid_from: str
    valid_to: str | None
    sources: tuple[str, ...]  # the documents that asserted it, see the brief


def check_date(date: str) -> str:
    """Return `date` if it is YYYY-MM-DD (ASCII digits, nothing else), else raise ValueError."""
    raise NotImplementedError


class TemporalGraph:
    """The temporal edges exercise, with provenance added. Its shape is up to you."""

    def __init__(self, functional: Iterable[str] = ()) -> None:
        raise NotImplementedError

    def assert_fact(self, subject: str, predicate: str, obj: str, date: str, source: str) -> None:
        raise NotImplementedError

    def facts(self, as_of: str | None = None) -> list[Fact]:
        """Facts still valid (`as_of` None) or valid on that date."""
        raise NotImplementedError
