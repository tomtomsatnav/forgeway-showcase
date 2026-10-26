from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class Memory:
    id: int
    text: str
    importance: int  # 1 to 10
    last_touch: float  # created, or last recalled
    accesses: int = 0
    pinned: bool = False


class DecayingMemory:
    """Memories that fade with disuse and strengthen with recall."""

    def __init__(
        self,
        clock: Callable[[], float],
        half_life_s: float = 86400.0,
        threshold: float = 0.1,
    ) -> None:
        self.clock = clock
        self.half_life_s = half_life_s
        self.threshold = threshold
        self.memories: dict[int, Memory] = {}
        self._next_id = 1

    def add(self, text: str, importance: int = 5, pinned: bool = False) -> int:
        raise NotImplementedError("validate importance, store a Memory, return its id")

    def retention(self, memory_id: int) -> float:
        raise NotImplementedError("1.0 if pinned, else the formula in the brief")

    def recall(self, query: str, k: int = 3) -> list[Memory]:
        raise NotImplementedError(
            "live memories sharing a word, best retention first, then reinforce"
        )

    def sweep(self) -> list[int]:
        raise NotImplementedError("delete the dead memories and return their ids")

    def ids(self) -> list[int]:
        return sorted(self.memories)
