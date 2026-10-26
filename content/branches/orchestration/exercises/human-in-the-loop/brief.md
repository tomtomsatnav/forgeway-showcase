# Human-in-the-loop interrupts

Some actions should not happen on the model's say-so alone: deleting a file, sending an email,
spending money. A **human-in-the-loop** agent pauses at those points, shows a person exactly what
it is about to do, and carries on only with their answer. Reading a file needs no such ceremony,
so the pause applies to the risky tools and nothing else.

```text
start("tidy up notes.txt")
   model asks: read_file, delete_file          delete_file needs approval
   ──► Outcome("waiting", pending=[delete_file])     nothing has run yet
                         ... a person decides ...
resume({"d1": "use archive_file instead"})
   delete_file is rejected, the model is told why, and tries archive_file
   ──► Outcome("done", "Archived notes.txt")
```

The pause is an ordinary return value, because the person may answer in a minute or in a
week: the agent keeps its conversation, hands back what is waiting, and `resume` picks up
from there. A rejection is not a failure either. It is information, and the model is often able
to find another way once it knows what you objected to.

## Your task

In `approval.py`, implement `ApprovalAgent(client, tools, registry, needs_approval)`.
`needs_approval` is the set of tool names that require a decision.

- `start(task)` begins a fresh conversation and loops: one `client.complete(messages,
  tools=tools)` per step. A reply with no tool request is `Outcome("done", text)`.
- If a tool request contains any call whose tool needs approval, **run nothing from it**. Keep
  the conversation, remember the request, and return `Outcome("waiting", pending=...)`, with
  the calls needing a decision in the model's order. A request that needs no approval just runs.
- `resume(decisions)` maps each pending call id to `True` (approve), `False` (reject) or a
  string (reject, with a reason). It runs the remembered request in the model's order: approved
  and unrestricted calls run, rejected ones get the result `rejected by user` (with `: <reason>`
  when a reason was given). Send one `tool` message per call, then continue the loop, which may
  finish or pause again.
- A raised exception, or an unknown tool, becomes the result `error: <message>`.
- `resume` raises `RuntimeError` when nothing is waiting, and `ValueError` when a pending call
  has no decision or a decision names a call that is not pending. In both cases nothing runs and
  the agent stays waiting.
