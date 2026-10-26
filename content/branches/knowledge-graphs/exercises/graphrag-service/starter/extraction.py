from dataclasses import dataclass
from typing import Any, NamedTuple

from forgeway_kit import ModelClient


class Triple(NamedTuple):
    subject: str
    predicate: str
    object: str


@dataclass(frozen=True)
class Extraction:
    triples: list[Triple]
    rejected: list[Any]


def extract(client: ModelClient, ontology: dict, text: str) -> Extraction:
    """Ontology-guided extraction, exactly as in the extraction exercise."""
    raise NotImplementedError
