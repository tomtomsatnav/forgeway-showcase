import re  # noqa: F401  (you will need it)
from dataclasses import dataclass
from typing import Any

from forgeway_kit import Message, ModelClient  # noqa: F401


@dataclass(frozen=True)
class Outcome:
    query: str | None  # the accepted query text, or None if it was refused
    rows: list[tuple[str, ...]]
    error: str | None  # why it was refused, or None


def ask(client: ModelClient, store: Any, question: str) -> Outcome:
    """Have the model write a query, check it against the grammar and the allow-list, run it.

    `store.predicates()` and `store.entities()` return sets of strings;
    `store.match(subject, predicate, obj)` returns triples.
    """
    raise NotImplementedError("parse first, run only what you parsed")
