from dataclasses import dataclass

from forgeway_kit import ModelClient


@dataclass(frozen=True)
class CheckedAnswer:
    text: str
    sources: list[str]
    supported: bool


def answer_with_check(
    client: ModelClient, store, question: str, k: int = 3, retry_k: int = 8
) -> CheckedAnswer:
    """Answer from `store`, verify the answer against its sources, retry once with `retry_k`.

    Each attempt: search, answer with numbered sources and [n] citations, then verify in a
    separate call that replies SUPPORTED or UNSUPPORTED. See the brief for the full rules.
    """
    raise NotImplementedError
