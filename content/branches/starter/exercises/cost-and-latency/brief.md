# Cost and latency

Every call has a price and a wait. Neither shows up in a demo, and both decide whether a feature
survives contact with real traffic. The price comes from the usage the provider reports and the
model's price list, and three details catch people out:

- **Cached input is cheaper.** When a request starts with the same blocks as a recent one, the
  provider reads them from its prompt cache and bills them at a fraction of the input price.
  `usage.cache_read_input_tokens` is that part, and it is *included* in `usage.input_tokens`.
- **Reasoning is output.** A reasoning model's thinking is billed at the output price.
  `usage.reasoning_tokens` is *included* in `usage.output_tokens`, so adding it again double
  counts. The **effort** setting is the main knob for it.
- **Prices differ by model**, often by ten times or more, so price each call with the card of
  the model that served it.

For speed, the average hides what users feel. Report percentiles: p50 is the typical call, p95
is the slow tail one call in twenty hits. There are several ways to compute a percentile; this
exercise uses the **nearest-rank** method, which always returns one of the measured values:
sort the `n` values and take the one at rank `ceil(p * n / 100)`, counting from 1.

```python
card = ModelCard(
    "small-model",
    input_usd_per_mtok=1.0,
    output_usd_per_mtok=5.0,
    cache_read_usd_per_mtok=0.1,
    base_latency_ms=300,
    ms_per_output_token=10,
    context_window=200_000,
)
usage = Usage(
    input_tokens=10_000, output_tokens=600, cache_read_input_tokens=8_000, reasoning_tokens=400
)
# 2,000 fresh input at $1, 8,000 cached at $0.10, 600 output at $5, per million tokens:
call_cost(usage, card)  # (2_000 * 1.0 + 8_000 * 0.1 + 600 * 5.0) / 1_000_000 = 0.0058
percentile([120, 340, 95, 410], 50)  # 120: rank ceil(50 * 4 / 100) = 2 of [95, 120, 340, 410]
```

## Your task

Implement four functions in `costs.py`. Return exact floats: do not round.

- `call_cost(usage, card)`: the price in USD of one call. Prices on a `ModelCard` are USD per
  million tokens: fresh input (`input_tokens - cache_read_input_tokens`) at
  `input_usd_per_mtok`, cache reads at `cache_read_usd_per_mtok`, and `output_tokens` (which
  already include reasoning) at `output_usd_per_mtok`.
- `percentile(values, p)`: the nearest-rank `p`th percentile, as above. Raise `ValueError` if
  `values` is empty or `p` is not in `0 < p <= 100`.
- `run_report(completions, cards)`: price each completion with the card whose `name` equals
  its `model`, and return a dict with these keys:
  - `"cost_usd"`: the total price of every call;
  - `"cache_savings_usd"`: what the cache saved, the sum over calls of
    `cache_read_input_tokens * (input_usd_per_mtok - cache_read_usd_per_mtok) / 1_000_000`;
  - `"p50_latency_ms"` and `"p95_latency_ms"`: the 50th and 95th percentiles of the
    completions' `latency_ms`.

  If a completion's model has no card, raise `ValueError` naming the model.
- `effort_costs(client, messages, card)`: send `messages` three times with
  `client.complete(messages, model=card.name, effort=...)`, at effort `"low"`, `"medium"` and
  `"high"` in that order, and return `{"low": cost, "medium": cost, "high": cost}`, each priced
  from that call's own usage.

Your local live mode prints an estimated cost for each call. That is a convenience with a
built-in price list, not a substitute: the tests use models no price list knows.
