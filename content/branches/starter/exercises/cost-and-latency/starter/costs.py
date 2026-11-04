from collections.abc import Sequence

from forgeway_kit import Completion, Message, ModelCard, StreamingModelClient, Usage

EFFORTS = ("low", "medium", "high")


def call_cost(usage: Usage, card: ModelCard) -> float:
    """The price in USD of one call that used `usage` on the model `card` describes."""
    raise NotImplementedError


def percentile(values: Sequence[float], p: float) -> float:
    """The nearest-rank `p`th percentile of `values`, for 0 < p <= 100."""
    raise NotImplementedError


def run_report(completions: Sequence[Completion], cards: Sequence[ModelCard]) -> dict:
    """Cost, cache savings and p50/p95 latency of a run of calls, priced from `cards`."""
    raise NotImplementedError


def effort_costs(
    client: StreamingModelClient, messages: Sequence[Message], card: ModelCard
) -> dict[str, float]:
    """Ask the same question at each effort level and return what each call cost."""
    raise NotImplementedError
