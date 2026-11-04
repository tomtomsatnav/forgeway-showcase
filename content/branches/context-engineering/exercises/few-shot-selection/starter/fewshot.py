# You will need `HashingEmbedder`, `Message` and `cosine_similarity` from forgeway_kit.
from dataclasses import dataclass

from forgeway_kit import ModelClient


@dataclass(frozen=True)
class Example:
    input: str
    label: str


def select_examples(pool: list[Example], query: str, k: int) -> list[Example]:
    """The `k` examples whose inputs are most similar to `query`, best match first.

    Similarity is the cosine of `HashingEmbedder()` vectors; equal scores keep pool order.
    """
    raise NotImplementedError("embed, rank, take k")


def classify(client: ModelClient, pool: list[Example], text: str, k: int = 3) -> str:
    """Show the model the `k` nearest examples as user/assistant turns (closest last), then
    `text` as the final user message, and return its reply."""
    raise NotImplementedError("selected examples become the first turns of the conversation")
