from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    text: str
    heading: str


def chunk_markdown(text: str, max_chars: int = 300) -> list[Chunk]:
    """Split markdown `text` into chunks that follow its structure.

    See the brief for the rules: split at headings, pack paragraphs up to `max_chars`,
    split oversized paragraphs by words, and record the heading on each chunk.
    """
    raise NotImplementedError("split into sections, then pack paragraphs")
