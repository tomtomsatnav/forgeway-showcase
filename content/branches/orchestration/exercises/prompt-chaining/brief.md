# Prompt chaining with gates

Hard tasks go better as a sequence of easy ones. Instead of asking for a finished release note
in one prompt, a **chain** extracts the user-facing changes, then drafts the note, then polishes
the tone. Each step has a short prompt of its own, and each can be tested separately.

The risk is that a mistake early on is passed down the chain looking like good input. A **gate**
is ordinary code between two steps that checks the output before anyone builds on it: is it
valid JSON, is it short enough, does it still mention the order number? A failing gate stops the
chain, so you pay for no further calls and nothing downstream ever sees the bad output.

```text
text ──► step 1 ──► gate 1 ──► step 2 ──► gate 2 ──► step 3 ──► gate 3 ──► result
                      │ fails
                      └──► stop: GateFailed(step 1, "not valid JSON")
```

## Your task

Implement `run_chain(client, text, steps)` in `chain.py`. A `Step` has a `name`, a `system`
prompt and a `gate`: a function from the step's output to `None` (fine) or a string saying what
is wrong.

- Run the steps in order. Each is one call: its own `system` prompt, and as the single user
  message the previous step's output (the first step gets `text`).
- Run a step's gate on its output before starting the next step.
- If a gate returns a reason, raise `GateFailed(step_name, reason, output)` straight away. Make
  no further model calls. Only `None` means the output is fine: an empty string is still a
  reason.
- Otherwise return `ChainResult(text, outputs)`: the last step's output, and every step's
  output keyed by step name. With no steps, the result is the original `text` and no outputs.
