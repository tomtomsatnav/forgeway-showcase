from dataclasses import dataclass

from forgeway_kit import ModelClient


@dataclass(frozen=True)
class AgenticAnswer:
    text: str
    sources: list[str]
    queries: list[str]


def agentic_answer(
    client: ModelClient, store, question: str, max_steps: int = 6, k: int = 3
) -> AgenticAnswer:
    """Let the model search `store` as often as it needs, then answer with citations.

    Offer a `search(query, k)` tool, answer each call with `[id] text` lines, remember every
    hit, and keep only cited ids that were really retrieved. Makes at most `max_steps` model
    calls, then raises RuntimeError mentioning `max_steps`.
    """
    raise NotImplementedError("a tool loop around store.search with checked citations")
