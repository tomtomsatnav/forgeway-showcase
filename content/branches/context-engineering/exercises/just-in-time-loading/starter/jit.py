# You will need `Message` from forgeway_kit.
from collections.abc import Callable
from dataclasses import dataclass

from forgeway_kit import ModelClient, Tool


@dataclass(frozen=True)
class Entry:
    id: str
    title: str
    tokens: int  # the size of the full document, known without reading it


LOAD = Tool(
    name="load_document",
    description="Load the full text of one document from the catalogue by its id.",
    input_schema={
        "type": "object",
        "properties": {"doc_id": {"type": "string", "description": "A catalogue id."}},
        "required": ["doc_id"],
    },
)


def answer_jit(
    client: ModelClient,
    question: str,
    catalogue: list[Entry],
    read: Callable[[str], str],
    budget: int,
    max_steps: int = 8,
) -> str:
    """Answer `question`, letting the model load catalogue documents on demand.

    The system prompt lists the catalogue (`- id: title`); documents arrive only as results of
    `load_document` calls, within a total budget of `budget` tokens. Makes at most `max_steps`
    model calls, then raises RuntimeError mentioning `max_steps`.
    """
    raise NotImplementedError("a tool loop around a budgeted read")
