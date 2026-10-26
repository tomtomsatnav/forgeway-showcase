# Import what you need from `notes` (fit_notes), `pruning` (prune_stale) and `fewshot`
# (choose_examples), and `Message` from forgeway_kit.
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from fewshot import Example
from notes import Note

from forgeway_kit import ModelClient, Tool


@dataclass(frozen=True)
class Entry:
    id: str
    title: str
    tokens: int  # the size of the full document, known without reading it


@dataclass(frozen=True)
class Reply:
    text: str
    sources: list[str]


LOAD = Tool(
    name="load_document",
    description="Load the full text of one document from the catalogue by its id.",
    input_schema={
        "type": "object",
        "properties": {"doc_id": {"type": "string", "description": "A catalogue id."}},
        "required": ["doc_id"],
    },
)


class SupportSession:
    """A multi-turn support agent whose every request is built deliberately."""

    def __init__(
        self,
        client: ModelClient,
        policy: str,
        catalogue: list[Entry],
        read: Callable[[str], str],
        *,
        examples: Sequence[Example] = (),
        examples_k: int = 3,
        examples_budget: int = 120,
        notes_budget: int = 60,
        load_budget: int = 400,
        keep_rounds: int = 1,
        max_steps: int = 8,
    ) -> None:
        raise NotImplementedError("build everything that never changes once, here")

    def send(self, text: str, *, now: str, notes: Sequence[Note] = ()) -> Reply:
        """One turn of the conversation. See the brief for the exact request layout."""
        raise NotImplementedError("prune, add the turn's message, loop, cite")
