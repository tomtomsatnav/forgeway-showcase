from dataclasses import dataclass, field

from kb import KnowledgeBase
from memory import CustomerMemory

from forgeway_kit import ModelClient, Tool

INSTRUCTIONS = (
    "Answer the customer from the numbered sources only, and cite each one you use by its "
    "number, like [1]. If a source is cut short, call open_article to read the whole article."
)
OPEN_ARTICLE = Tool(
    "open_article",
    "Open a help-centre article in full, by the article id shown after a source's title.",
    {
        "type": "object",
        "properties": {"article_id": {"type": "string"}},
        "required": ["article_id"],
    },
)


@dataclass(frozen=True)
class Citation:
    chunk_id: str
    title: str
    url: str


@dataclass(frozen=True)
class Reply:
    text: str
    citations: list[Citation] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)


class Copilot:
    """One support turn: memory and sources in a budgeted prompt, articles loaded on demand."""

    def __init__(
        self,
        client: ModelClient,
        kb: KnowledgeBase,
        memory: CustomerMemory,
        *,
        policy: str,
        k: int = 5,
        source_budget: int = 400,
        memory_budget: int = 120,
        load_budget: int = 800,
        max_steps: int = 6,
    ) -> None:
        raise NotImplementedError

    def answer(self, user_id: str, question: str, *, now: str) -> Reply:
        """Answer one question for one customer. See the brief for the exact layout."""
        raise NotImplementedError
