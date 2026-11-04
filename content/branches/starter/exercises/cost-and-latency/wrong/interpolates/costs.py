from collections.abc import Sequence

from forgeway_kit import Completion, Message, ModelCard, StreamingModelClient, Usage

EFFORTS = ("low", "medium", "high")
MTOK = 1_000_000


def call_cost(usage: Usage, card: ModelCard) -> float:
    """The price in USD of one call that used `usage` on the model `card` describes."""
    fresh = usage.input_tokens - usage.cache_read_input_tokens  # cache reads are part of input
    return (
        fresh * card.input_usd_per_mtok
        + usage.cache_read_input_tokens * card.cache_read_usd_per_mtok
        + usage.output_tokens * card.output_usd_per_mtok  # reasoning is already in output_tokens
    ) / MTOK


def percentile(values: Sequence[float], p: float) -> float:
    """The nearest-rank `p`th percentile of `values`, for 0 < p <= 100."""
    if not values:
        raise ValueError("percentile of no values")
    if not 0 < p <= 100:
        raise ValueError(f"p must be in (0, 100], not {p}")
    import statistics

    if len(values) == 1:
        return values[0]
    return (
        statistics.quantiles(values, n=100, method="inclusive")[round(p) - 1]
        if p < 100
        else max(values)
    )


def run_report(completions: Sequence[Completion], cards: Sequence[ModelCard]) -> dict:
    """Cost, cache savings and p50/p95 latency of a run of calls, priced from `cards`."""
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
    """Ask the same question at each effort level and return what each call cost."""
    costs = {}
    for effort in EFFORTS:
        completion = client.complete(messages, model=card.name, effort=effort)
        costs[effort] = call_cost(completion.usage, card)
    return costs
