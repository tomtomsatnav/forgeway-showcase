from dataclasses import dataclass

from forgeway_kit import ModelClient


@dataclass(frozen=True)
class Round:
    draft: str
    feedback: str  # the evaluator's feedback; empty for a draft that passed


@dataclass(frozen=True)
class Refined:
    text: str
    accepted: bool
    rounds: int
    history: list[Round]


def refine(client: ModelClient, task: str, max_rounds: int = 3) -> Refined:
    """Generate a draft, have it evaluated, and regenerate with the feedback until it passes.

    Each round is one generator call and one evaluator call. The evaluator replies `PASS` or
    `FAIL: <feedback>`. Stop at the first pass, or after `max_rounds` drafts.
    """
    raise NotImplementedError("generate, evaluate, then retry with the draft and the feedback")
