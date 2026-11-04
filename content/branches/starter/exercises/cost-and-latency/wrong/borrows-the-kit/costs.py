import io
import math
import re
from collections.abc import Sequence

from forgeway_kit import Completion, Message, ModelCard, StreamingModelClient, Usage
from forgeway_kit.live import Metered

EFFORTS = ("low", "medium", "high")
MTOK = 1_000_000


class _Replay:
    """A client that answers with a fixed usage, so Metered prices it."""

    def __init__(self, usage: Usage, model: str) -> None:
        self.usage, self.model = usage, model

    def complete(self, messages, **options):
        return Completion("", "end_turn", self.usage, model=self.model, latency_ms=1.0)


def call_cost(usage: Usage, card: ModelCard) -> float:
    """Let the toolkit's meter price the call from the card's rates."""
    out = io.StringIO()
    rates = {
        card.name: (card.input_usd_per_mtok, card.output_usd_per_mtok, card.cache_read_usd_per_mtok)
    }
    Metered(_Replay(usage, card.name), rates=rates, out=out).complete(
        [Message(role="user", content="x")]
    )
    return float(re.search(r"~\$([0-9.]+)", out.getvalue()).group(1))


def percentile(values: Sequence[float], p: float) -> float:
    if not values:
        raise ValueError("percentile of no values")
    if not 0 < p <= 100:
        raise ValueError(f"p must be in (0, 100], not {p}")
    ordered = sorted(values)
    return ordered[math.ceil(p * len(ordered) / 100) - 1]


def run_report(completions: Sequence[Completion], cards: Sequence[ModelCard]) -> dict:
    by_name = {card.name: card for card in cards}
    cost = savings = 0.0
    for completion in completions:
        card = by_name.get(completion.model)
        if card is None:
            raise ValueError(f"no model card for {completion.model!r}")
        cost += call_cost(completion.usage, card)
        discount = card.input_usd_per_mtok - card.cache_read_usd_per_mtok
        savings += completion.usage.cache_read_input_tokens * discount / MTOK
    latencies = [completion.latency_ms for completion in completions]
    return {
        "cost_usd": cost,
        "cache_savings_usd": savings,
        "p50_latency_ms": percentile(latencies, 50),
        "p95_latency_ms": percentile(latencies, 95),
    }


def effort_costs(
    client: StreamingModelClient, messages: Sequence[Message], card: ModelCard
) -> dict[str, float]:
    costs = {}
    for effort in EFFORTS:
        completion = client.complete(messages, model=card.name, effort=effort)
        costs[effort] = call_cost(completion.usage, card)
    return costs
