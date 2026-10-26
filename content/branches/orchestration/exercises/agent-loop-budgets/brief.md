# An agent loop with budgets

The tool-calling loop you wrote earlier stops after `max_steps`. That is one guard, and real
agents need three, because a stuck agent can fail in three different ways:

- **It runs too long.** A step cap bounds the number of model calls.
- **It costs too much.** Each step resends the whole conversation, so a long loop gets steadily
  more expensive. A token budget bounds the spend, whatever the step count.
- **It goes round in circles.** The model asks for the same search again and again, expecting a
  different result. A **loop detector** notices an identical call being made repeatedly and
  stops.

Stopping is a decision, so make it *before* acting on the model's latest request. If the
budget is blown, the tools in that request must not run: a refused call has no side effects.
And stopping is not an exception. The caller wants to know what happened, so return a status.

```text
model reply ──► answered?        ──► done
              ├─ tokens > budget ──► token_budget
              ├─ repeated call   ──► loop_detected
              ├─ no steps left   ──► max_steps
              └─ otherwise run the tools and go round again
```

## Your task

Implement `run_agent(client, task, tools, registry, *, max_steps=8, token_budget=2000,
max_repeats=2)` in `agent.py`. Each step is one `client.complete(messages, tools=tools)`, and
`registry` maps a tool name to a function called as `function(**arguments)`.

After every model call, add its input and output tokens to a running total. Then:

1. If the reply is not a tool request, return `AgentResult("done", text, steps, tokens_used)`.
2. If the total is more than `token_budget`, return status `token_budget`.
3. If any call in the request is one already made `max_repeats` times (same tool, same
   arguments, whatever the key order, counting earlier calls in the same request), return
   `loop_detected`.
4. If this was the `max_steps`th model call, return `max_steps`.
5. Otherwise run every call, in order, and send each result back as a `tool` message. A raised
   exception, or an unknown tool, becomes the result `error: <message>`.

In cases 2 to 4 none of the request's tools run, and `text` is empty. `steps` is the number of
model calls made.
