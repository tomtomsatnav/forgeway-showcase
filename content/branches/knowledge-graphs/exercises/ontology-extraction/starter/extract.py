import json  # noqa: F401  (you will need it)
from dataclasses import dataclass
from typing import Any, NamedTuple

from forgeway_kit import Message, ModelClient  # noqa: F401


class Triple(NamedTuple):
    subject: str
    predicate: str
    object: str


@dataclass(frozen=True)
class Extraction:
    triples: list[Triple]
    rejected: list[Any]


def extract(client: ModelClient, ontology: dict, text: str) -> Extraction:
    """Ask the model for triples from `text`, keep only those that fit `ontology`."""
    raise NotImplementedError("show the ontology, then do not trust the reply")
