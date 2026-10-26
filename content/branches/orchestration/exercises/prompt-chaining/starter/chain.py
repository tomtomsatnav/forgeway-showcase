from collections.abc import Callable
from dataclasses import dataclass

from forgeway_kit import ModelClient


@dataclass(frozen=True)
class Step:
    name: str
    system: str
    gate: Callable[[str], str | None]  # None if the output is fine, else what is wrong with it


@dataclass(frozen=True)
class ChainResult:
    text: str
    outputs: dict[str, str]


class GateFailed(Exception):
    def __init__(self, step: str, reason: str, output: str) -> None:
        super().__init__(f"gate failed at step {step!r}: {reason}")
        self.step = step
        self.reason = reason
        self.output = output


def run_chain(client: ModelClient, text: str, steps: list[Step]) -> ChainResult:
    """Feed `text` through `steps`, checking each output with its gate before the next step.

    A failing gate raises GateFailed(step.name, reason, output) and no later step runs.
    """
    raise NotImplementedError("one model call per step, a gate between each pair")
