"""Price a few live calls with your own functions.

python live.py   (set FORGEWAY_LIVE first; see LIVE-MODE.md)

Set PRICES to your model's current list prices (USD per million tokens) before trusting the totals.
"""

from costs import effort_costs, run_report

from forgeway_kit import Message, ModelCard, default_client

client = default_client()
question = [Message(role="user", content="In two sentences: what is a prompt cache?")]
completions = [client.complete(question, max_tokens=200) for _ in range(3)]
model = completions[0].model
PRICES = (4.0, 20.0, 0.40)  # input, output, cache read
card = ModelCard(model, *PRICES, base_latency_ms=0, ms_per_output_token=0, context_window=200_000)

print(run_report(completions, [card]))
print(effort_costs(client, question, card))
