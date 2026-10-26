# Checkpoint and resume

Agents run for minutes, and processes die: a deploy restarts the server, a rate limit throws an
error, a laptop lid closes. If the agent has to start again from the beginning, that is a
waste at best. At worst it is a disaster, because some tools have effects in the world. Running
`send_email` twice sends two emails, and `charge_card` twice charges the customer twice.

The fix is a **checkpoint**: after every step that matters, save the conversation to a durable
store. On the next run with the same id, load it and carry on from where the agent was. The
detail that makes this safe is *granularity*. If you save only at the end of a round of tool
calls, a crash after the first of three calls loses its record, and the resumed agent runs
that call again. So save after every individual result, and never repeat a call whose result
you already hold.

```text
model reply (3 calls) ──► save ──► call 1 ──► save ──► call 2 ✗ crash
                                                   resume: load, call 1 is already answered,
                                                   run calls 2 and 3, only then ask the model
```

Your tests simulate crashes and count how many times each tool really ran.

## Your task

Implement `run_durable(client, run_id, task, tools, registry, store)` in `durable.py`. It is
the tool-calling loop you already know: one `client.complete(messages, tools=tools)` per step,
tool results sent back as `tool` messages in call order (errors become `error: <message>`),
returning the model's final text.

- `store` is a dict of strings. Keep the whole state of the run in `store[run_id]` as JSON text,
  and keep it up to date: after the task is recorded, after each model reply is added (before
  its tools run), after each individual tool result, and when the run finishes.
- If `store` already holds `run_id`, resume it. The saved conversation wins over `task`. Run
  only the tool calls of the last request that have no result yet, then carry on. Never run a
  call that already has a result.
- If the saved run had finished, return its answer immediately: no model call, no tool call.
- Exceptions raised by the model client propagate to the caller, and so does anything that
  kills the process outright (a `BaseException` such as `KeyboardInterrupt`) raised inside a
  tool; the checkpoint already written stays valid.
- An ordinary exception from a tool, or a call to an unknown tool, is not a crash: it becomes
  the result `error: <message>`, which is saved like any other result and never re-run.
