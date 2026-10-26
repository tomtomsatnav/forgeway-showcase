from dataclasses import dataclass

from forgeway_kit import ModelClient


@dataclass(frozen=True)
class Citation:
    chunk_id: str
    doc: str
    title: str
    heading: str


@dataclass(frozen=True)
class Reply:
    text: str
    citations: list[Citation]
    supported: bool
    query: str


class RagService:
    def __init__(
        self,
        client: ModelClient,
        retriever,
        *,
        k: int = 3,
        retry_k: int = 6,
        source_budget: int = 300,
    ) -> None:
        raise NotImplementedError

    def ask(self, question: str, history=(), where: dict | None = None) -> Reply:
        """Rewrite a follow-up, retrieve, answer with citations, verify, retry once.

        `history` is a list of `Message`s. See the brief for every rule.
        """
        raise NotImplementedError
