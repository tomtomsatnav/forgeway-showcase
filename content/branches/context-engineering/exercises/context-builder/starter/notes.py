# You will need `count_tokens` from forgeway_kit.
from dataclasses import dataclass


@dataclass(frozen=True)
class Note:
    text: str
    priority: int


def fit_notes(notes: list[Note], budget: int) -> list[Note]:
    """The notes that fit in `budget` tokens, in their original order.

    Visit the notes from the highest priority down (ties in list order). Keep a note whole if it
    fits in what is left, otherwise skip it and carry on. Notes with no tokens are dropped.
    """
    raise NotImplementedError("greedy by priority, output in list order")
