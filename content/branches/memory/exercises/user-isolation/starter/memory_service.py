import re
from dataclasses import dataclass

from forgeway_kit import Embedder, HashingEmbedder, ModelClient


@dataclass(frozen=True)
class Record:
    id: str  # "m1", "m2", ...
    number: int  # the counter behind the id, in order of adding
    user_id: str
    text: str


def words(text: str) -> list[str]:
    """Lower-cased runs of ASCII letters and digits."""
    return re.findall(r"[a-z0-9]+", text.lower())


class MemoryService:
    """Memories for many users, behind one keyword index and one vector index."""

    def __init__(self, embedder: Embedder | None = None) -> None:
        self.embedder = embedder or HashingEmbedder()
        self.records: dict[str, Record] = {}  # id -> record
        self.word_index: dict[str, set[str]] = {}  # word -> ids of records containing it
        self.vectors: dict[str, list[float]] = {}  # id -> embedding of the text
        self._counter = 0

    def add(self, user_id: str, text: str) -> str:
        raise NotImplementedError("one counter for everyone; fill all three indexes")

    def search(self, user_id: str, query: str, k: int = 3) -> list[Record]:
        raise NotImplementedError("this user's records only, filtered before ranking and cutting")

    def forget(self, user_id: str, memory_id: str) -> bool:
        raise NotImplementedError("only the owner can delete; remove from every index")

    def forget_user(self, user_id: str) -> int:
        raise NotImplementedError("remove every record this user owns from every index")

    def answer(self, client: ModelClient, user_id: str, question: str) -> str:
        raise NotImplementedError("build the prompt from this user's memories only")
