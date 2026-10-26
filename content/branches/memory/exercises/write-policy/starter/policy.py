from typing import Protocol

from forgeway_kit import ModelClient


class MemoryStore(Protocol):
    def add_fact(self, subject: str, attribute: str, value: str) -> None: ...

    def add_episode(self, text: str, importance: int) -> None: ...


def apply_policy(classifier: ModelClient, store: MemoryStore, turn: str) -> str:
    """Ask the classifier what to do with `turn`, enforce the reply, and write accordingly.

    Returns "fact", "episode", "skipped", "withheld" or "invalid".
    """
    raise NotImplementedError("one classifier call, then validate every field of the reply")
