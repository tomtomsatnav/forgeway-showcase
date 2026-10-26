# You will need `Message` from forgeway_kit.
from dataclasses import dataclass

from forgeway_kit import ModelClient


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    text: str


def render_context(instructions: str, documents: list[Document]) -> str:
    """The instructions block, then one `<document>` block per document, joined by newlines.

    Document text, ids and titles are untrusted: escape them so they cannot close or open a
    section. The instructions are written exactly as given.
    """
    raise NotImplementedError("escape what you do not control, then wrap it")


def ask(client: ModelClient, instructions: str, documents: list[Document], question: str) -> str:
    """Send the rendered context as the system prompt and `question` as the user message."""
    raise NotImplementedError("one call: the structure goes in the system prompt")
