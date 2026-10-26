# Checking an agent's trajectory

An agent can reach the right answer the wrong way: it refunds before it has looked the order up,
calls the search tool nine times, or touches a tool it should never use. Checking only the final
text misses all of that. A **trajectory** is the recorded sequence of tool calls an agent made.
Evaluating it means checking the sequence against a **spec**: the right tools, in the right order,
within budget.

```text
task ──► agent ──► [lookup_order(7), refund(7, 20), send_email(...)]  ──► check against the spec
```

Trajectory checks are cheap and exact. They need no judge and no reference answer, so you can run
them on every change.

## Your task

Implement two functions and a runner in `trajectory.py`.

`record_trajectory(client, task, tools, registry, max_steps=8)` runs the usual tool loop and
returns `{"calls": [...], "answer": ...}`. The task is the first `user` message. Each time the
model replies with tool calls, append them to `calls` as
`{"tool": name, "arguments": dict(arguments)}`, in the order requested, then answer every call
with a `tool` message in the same order: the result of `registry[name](**arguments)` as text, or
`error: <message>` if the tool raises, or `error: unknown tool` if `registry` has no such tool.
A call that fails is still recorded. Stop when the model replies without tool calls and return its
text as `answer`. Make at most `max_steps` model calls; if the model is still asking for tools after
that, raise `RuntimeError` mentioning `max_steps`.

`check_trajectory(calls, spec)` returns the list of violations, as the **sorted list of unique
codes** below, and `[]` when the trajectory is acceptable. Every key of `spec` is optional:

| Key | Rule | Violation code |
| --- | --- | --- |
| `required` | each listed tool must be called at least once | `missing:<tool>` |
| `forbidden` | no listed tool may be called | `forbidden:<tool>` |
| `order` | a list of `[before, after]` pairs. If `after` is called at all, `before` must be called and its **first** call must come earlier than the first call of `after`. If `after` is never called the pair is satisfied | `order:<before>><after>` |
| `max_calls` | at most this many calls in total | `budget` |
| `max_identical` | no call (same tool and equal arguments, however the keys are ordered) may be made more than this many times | `repeat:<tool>` |
| `args` | a mapping of tool to `{key: value}`: every call to that tool must contain every key with an equal value (extra keys are fine) | `args:<tool>` |

For example, `order: [["lookup_order", "refund"]]` on the trajectory `refund, lookup_order`
gives `["order:lookup_order>refund"]`.

`evaluate_trajectories(client, cases, tools, registry)` takes `cases`, a list of
`{"task": ..., "spec": ...}`. For each, in order, record a fresh trajectory and check it. Return
`{"pass_rate": ..., "results": [{"violations": [...], "passed": ...}, ...]}`, where a case
passed when it has no violations and `pass_rate` is the fraction that passed. An empty list of
cases gives `{"pass_rate": 1.0, "results": []}`: nothing failed.
