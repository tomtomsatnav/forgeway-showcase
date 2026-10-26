from dataclasses import dataclass
from typing import Protocol

from forgeway_kit import ModelClient


@dataclass
class Episode:
    id: int
    text: str
    importance: int  # 1 to 10
    reflected: bool = False


class FactBook(Protocol):
    def set(self, subject: str, attribute: str, value: str, evidence: tuple[int, ...]) -> None: ...


def reflect(
    reflector: ModelClient,
    episodes: list[Episode],
    facts: FactBook,
    threshold: int = 25,
) -> int:
    """Consolidate unreflected episodes into facts. Returns how many facts were written."""
    raise NotImplementedError("gate on the threshold, ask once, validate every fact, then mark")
