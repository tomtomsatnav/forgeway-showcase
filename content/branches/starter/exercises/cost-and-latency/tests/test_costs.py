"""Hidden checks. Learners see each check's title and, when it fails, the assertion message."""

import json
import math
import random

from costs import call_cost, effort_costs, percentile, run_report

from forgeway_kit import Completion, FakeModel, Message, ModelCard, Usage

WORDS = [
    "quill",
    "ferro",
    "nimbus",
    "aster",
    "corvid",
    "lumen",
    "sable",
    "tidal",
    "vesper",
    "oxbow",
]
MTOK = 1_000_000


def plain(value):
    """Learner results as plain built-ins, so a value cannot lie about equality."""
    return json.loads(json.dumps(value))


def number(value, what):
    value = plain(value)
    assert type(value) in (int, float), f"{what} should be a number, got {type(value).__name__}."
    return value


def close(a, b):
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-15)


def seeded_card(rng):
    """A model with an arbitrary name and prices, so no price list anywhere can know it."""
    base = round(rng.uniform(0.05, 12), 3)
    return ModelCard(
        name=f"{rng.choice(WORDS)}-{rng.randrange(16**6):06x}",
        input_usd_per_mtok=base,
        output_usd_per_mtok=round(base * rng.uniform(2, 8), 3),
        cache_read_usd_per_mtok=round(base * rng.uniform(0.05, 0.5), 4),
        base_latency_ms=round(rng.uniform(80, 900), 1),
        ms_per_output_token=round(rng.uniform(2, 40), 2),
        context_window=200_000,
    )


def priced(usage, card):
    """The price of one call; used only after learner code has returned."""
    fresh = usage.input_tokens - usage.cache_read_input_tokens
    return (
        fresh * card.input_usd_per_mtok
        + usage.cache_read_input_tokens * card.cache_read_usd_per_mtok
        + usage.output_tokens * card.output_usd_per_mtok
    ) / MTOK


def nearest_rank(values, p):
    ordered = sorted(values)
    return ordered[math.ceil(p * len(ordered) / 100) - 1]


def test_prices_one_call():
    rng = random.Random(3)  # noqa: S311 - seeded, so grading is deterministic
    for index in range(30):
        card = seeded_card(rng)
        input_tokens = rng.randint(50, 60_000)
        output_tokens = rng.randint(1, 8_000)
        usage = Usage(
            input_tokens,
            output_tokens,
            cache_read_input_tokens=0 if index % 5 == 0 else rng.randint(0, input_tokens),
            reasoning_tokens=0 if index % 4 == 0 else rng.randint(0, output_tokens),
        )
        got = number(call_cost(usage, card), "call_cost()")
        want = priced(usage, card)
        assert close(got, want), (
            f"For {usage} on {card}, call_cost() should be {want!r} USD, but was {got!r}. Prices "
            "are per million tokens. cache_read_input_tokens are part of input_tokens and billed "
            "at the cache-read price instead of the input price; reasoning_tokens are already "
            "inside output_tokens, so do not add them again. Do not round."
        )


def seeded_run(rng, cards, calls):
    """A conversation that hops between models, so some calls read the prompt cache."""
    model = FakeModel(
        responder=lambda r: " ".join(
            random.Random(len(r.messages) * 31 + len(r.model)).choices(  # noqa: S311 - seeded, so grading is deterministic
                WORDS, k=5 + len(r.messages) % 23
            )
        ),
        models=cards,
    )
    messages = [Message(role="user", content=" ".join(rng.choices(WORDS, k=rng.randint(200, 900))))]
    completions = []
    card = rng.choice(cards)
    for _ in range(calls):
        if rng.random() < 0.3:
            card = rng.choice(cards)
        effort = rng.choice([None, "low", "medium", "high"])
        completion = model.complete(messages, model=card.name, effort=effort, max_tokens=400)
        completions.append(completion)
        messages = [
            *messages,
            Message(role="assistant", content=completion.text),
            Message(role="user", content=" ".join(rng.choices(WORDS, k=rng.randint(5, 60)))),
        ]
    return completions


def test_totals_a_run_and_its_cache_savings():
    rng = random.Random(29)  # noqa: S311 - seeded, so grading is deterministic
    for _ in range(4):
        cards = [seeded_card(rng) for _ in range(3)]
        completions = seeded_run(rng, cards, rng.randint(12, 25))
        report = plain(run_report(completions, list(cards)))
        assert isinstance(report, dict), f"run_report() should return a dict, got {report!r}."
        by_name = {card.name: card for card in cards}
        want_cost = sum(priced(c.usage, by_name[c.model]) for c in completions)
        want_savings = sum(
            c.usage.cache_read_input_tokens
            * (by_name[c.model].input_usd_per_mtok - by_name[c.model].cache_read_usd_per_mtok)
            / MTOK
            for c in completions
        )
        assert want_savings > 0, "test bug: the run should read the cache"
        got = number(report.get("cost_usd"), "report['cost_usd']")
        assert close(got, want_cost), (
            f"report['cost_usd'] should be the sum of every call's price, priced from the card "
            f"named by each completion's model: {want_cost!r} USD, but was {got!r}."
        )
        got = number(report.get("cache_savings_usd"), "report['cache_savings_usd']")
        assert close(got, want_savings), (
            f"report['cache_savings_usd'] should be {want_savings!r} USD, but was {got!r}: for "
            "each call, its cache-read tokens times the difference between that model's input "
            "price and its cache-read price."
        )

    cards = [seeded_card(rng) for _ in range(2)]
    completions = seeded_run(rng, cards, 6)
    stranger = seeded_card(rng).name
    completions.insert(
        3, Completion("hi", "end_turn", Usage(10, 2), model=stranger, latency_ms=99.0)
    )
    caught = None
    try:
        run_report(completions, list(cards))
    except ValueError as error:
        caught = error
    assert caught is not None and stranger in str(caught), (
        f"A completion from {stranger!r}, which has no model card, should raise ValueError "
        f"naming the model rather than being skipped or priced at zero; got {caught!r}."
    )


def test_percentiles_by_nearest_rank():
    rng = random.Random(31)  # noqa: S311 - seeded, so grading is deterministic
    for n in [1, 2, 5, 19, 20, 21, 37, 40, 100, 101]:
        values = [round(rng.uniform(5, 3000), 1) for _ in range(n)]
        if n > 4:
            values[1] = values[3]  # a tie
        for p in [1, 25, 50, 90, 95, 99, 100]:
            got = number(percentile(list(values), p), "percentile()")
            want = nearest_rank(values, p)
            assert got == want, (
                f"percentile(values, {p}) over these {n} values should be {want} by the "
                f"nearest-rank method (the value at rank ceil(p * n / 100) in sorted order, "
                f"counting from 1), but was {got}. It is always one of the values; do not "
                f"interpolate. Values: {sorted(values)}"
            )
    for values, p in [([], 50), ([3.0, 1.0], 0), ([3.0, 1.0], 100.5), ([2.0], -5)]:
        outcome = "returned"
        try:
            percentile(values, p)
        except ValueError:
            outcome = "raised"
        assert outcome == "raised", (
            f"percentile({values}, {p}) should raise ValueError: values must not be empty and "
            "p must satisfy 0 < p <= 100."
        )


def test_reports_p50_and_p95_latency():
    rng = random.Random(37)  # noqa: S311 - seeded, so grading is deterministic
    for n in [20, 23, 40, 57]:
        card = seeded_card(rng)
        latencies = [round(rng.lognormvariate(6, 0.6), 2) for _ in range(n)]
        completions = [
            Completion("ok", "end_turn", Usage(100, 10), model=card.name, latency_ms=ms)
            for ms in latencies
        ]
        report = plain(run_report(completions, [card]))
        for key, p in [("p50_latency_ms", 50), ("p95_latency_ms", 95)]:
            got = number(report.get(key) if isinstance(report, dict) else None, f"report[{key!r}]")
            want = nearest_rank(latencies, p)
            assert got == want, (
                f"Over {n} calls, report[{key!r}] should be {want} ms, the nearest-rank "
                f"{p}th percentile of the completions' latency_ms, but was {got}."
            )
    cards = [seeded_card(rng) for _ in range(3)]
    completions = seeded_run(rng, cards, 21)
    report = plain(run_report(completions, list(cards)))
    for key, p in [("p50_latency_ms", 50), ("p95_latency_ms", 95)]:
        want = nearest_rank([c.latency_ms for c in completions], p)
        got = number(report.get(key), f"report[{key!r}]")
        assert got == want, f"report[{key!r}] should be {want} ms over a real run, but was {got}."


def test_compares_effort_levels():
    rng = random.Random(41)  # noqa: S311 - seeded, so grading is deterministic
    for _ in range(4):
        cards = [seeded_card(rng) for _ in range(3)]
        card = cards[rng.randrange(1, 3)]  # never the default model

        def responder(request):
            return " ".join(random.Random(request.sample).choices(WORDS, k=12))  # noqa: S311

        model = FakeModel(responder=responder, models=cards, default_model=cards[0].name)
        question = f"Plan a {rng.choice(WORDS)} migration in {rng.randint(2, 9)} steps."
        messages = [Message(role="user", content=question)]
        got = plain(effort_costs(model, list(messages), card))
        sent = [(r.model, r.effort) for r in model.requests]
        want_sent = [(card.name, "low"), (card.name, "medium"), (card.name, "high")]
        assert sent == want_sent, (
            f"effort_costs() should make three calls to {card.name!r}, at effort low, medium "
            f"and high in that order; it made {sent}. Pass model=card.name and effort= to "
            "complete()."
        )
        assert all([m.content for m in r.messages] == [question] for r in model.requests), (
            "Send the same messages at every effort level."
        )
        replay = FakeModel(responder=responder, models=cards, default_model=cards[0].name)
        want = {
            effort: priced(replay.complete(messages, model=card.name, effort=effort).usage, card)
            for effort in ("low", "medium", "high")
        }
        assert isinstance(got, dict) and sorted(got) == ["high", "low", "medium"], (
            f"effort_costs() should return a dict keyed 'low', 'medium' and 'high'; got {got!r}."
        )
        for effort, cost in want.items():
            assert close(number(got[effort], f"the {effort} cost"), cost), (
                f"The {effort}-effort call cost {cost!r} USD (from that call's own usage, with "
                f"its reasoning tokens and cache reads), but effort_costs() said {got[effort]!r}."
            )
