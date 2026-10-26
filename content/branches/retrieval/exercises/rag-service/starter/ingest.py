from dataclasses import dataclass, field


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    metadata: dict = field(default_factory=dict)


def chunk_documents(docs: list[dict], max_chars: int = 240) -> list[Chunk]:
    """Cut documents into structure-aware chunks that carry their ids and metadata.

    Each document is a dict with `id`, `title`, `meta` (a dict) and `body` (markdown). See the
    brief for the chunk ids and the metadata every chunk must carry.
    """
    raise NotImplementedError
