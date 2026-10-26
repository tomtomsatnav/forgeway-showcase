from dataclasses import dataclass

from forgeway_kit import ModelClient


@dataclass(frozen=True)
class Answer:
    text: str
    sources: list[str]


def answer(client: ModelClient, store, question: str, k: int = 3) -> Answer:
    """Answer `question` from the top `k` hits of `store.search(question, k)`.

    Each hit has `.id` and `.text`. Put the sources in the prompt as `[1] ...`, `[2] ...`,
    ask the model to cite them as [n], and return its reply with the ids it cited.
    """
    raise NotImplementedError("retrieve, build the prompt, ask, parse the citations")
