from dataclasses import dataclass

from forgeway_kit import ModelClient


@dataclass(frozen=True)
class IngestReport:
    accepted: int  # valid triples in the model's reply
    rejected: int  # items the ontology refused


@dataclass(frozen=True)
class Citation:
    subject: str
    predicate: str
    object: str
    valid_from: str
    valid_to: str | None
    sources: list[str]


@dataclass(frozen=True)
class Answer:
    text: str
    citations: list[Citation]
    sources: list[str]


@dataclass(frozen=True)
class QueryResult:
    query: str | None  # the model's query, stripped, or None if it was refused
    rows: list[tuple[str, ...]]
    error: str | None  # why it was refused


@dataclass(frozen=True)
class Report:
    id: int
    members: list[str]
    summary: str
    sources: list[str]


@dataclass(frozen=True)
class GlobalAnswer:
    text: str
    reports: list[Report]
    sources: list[str]


class GraphRAG:
    def __init__(
        self,
        extractor: ModelClient,
        answerer: ModelClient,
        ontology: dict,
        aliases: dict[str, str] | None = None,
    ) -> None:
        raise NotImplementedError

    def ingest(self, doc_id: str, date: str, text: str) -> IngestReport:
        """Extract, resolve and record a dated document's facts, with their source."""
        raise NotImplementedError

    def ask(self, question: str, start: str, as_of: str | None = None, max_hops: int = 2) -> Answer:
        """Answer from the facts within `max_hops` of `start` that were valid at `as_of`."""
        raise NotImplementedError

    def query(self, question: str, as_of: str | None = None) -> QueryResult:
        """Have the model write a query for `question`, and run it only if it is allowed."""
        raise NotImplementedError

    def ask_global(self, question: str, as_of: str | None = None) -> GlobalAnswer:
        """Answer a question about the whole graph from its communities' summaries."""
        raise NotImplementedError
