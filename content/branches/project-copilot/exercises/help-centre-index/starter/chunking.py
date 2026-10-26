from dataclasses import dataclass, field


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    metadata: dict = field(default_factory=dict)


def chunk_article(article: dict, max_chars: int = 300) -> list[Chunk]:
    """Cut one help-centre article into structure-aware chunks.

    An article is a dict with `id`, `title`, `url`, `meta` (a dict) and `body` (markdown). See
    the brief for headings, fenced blocks, packing, and the metadata every chunk carries.
    """
    raise NotImplementedError
