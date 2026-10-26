# Context compaction in a long loop

Every step of an agent loop resends the whole conversation, so a long task has a problem that a
short one does not: it grows until it no longer fits. A context window is a hard limit. When
the conversation passes it the API refuses the request, and the agent dies halfway through a
job, after hours of work.

The standard remedy is **compaction**. When the conversation gets large, ask the model to
summarise the oldest part and replace those messages with the summary. What you keep matters:

- **The task**, exactly as given. Without it the agent forgets what it is for.
- **A summary** of the older work, written to keep the facts the agent will still need.
- **The most recent messages**, untouched, so the agent continues mid-thought.

```text
before:  task │ a t a t a t a t a t a t a t │ ...   too big, 1,000 tokens
after:   task │ summary of the first ten    │ a t a t   fits, 350 tokens
```

Two details bite. A tool result must stay directly behind the assistant message that requested it,
or the API rejects the conversation, so you cannot cut between them. And compacting too eagerly
wastes a model call and throws information away, so wait until it is needed.

## Your task

Implement `run_long_task(client, task, tools, registry, *, compact_at=500, keep_recent=4,
max_steps=40)` in `compaction.py`. The starter gives you `conversation_tokens(messages)`, which
counts tokens the way the model's context window does.

- Run a tool loop: one `client.complete(messages, tools=tools)` per step, tool results sent back
  in call order (errors become `error: <message>`). Return the final text. After `max_steps` model
  calls raise `RuntimeError` mentioning `max_steps`. Summary calls are not steps: only the
  loop's own model calls count towards `max_steps`.
- Before each model call, if `conversation_tokens(messages)` is more than `compact_at`, compact:
  keep `messages[0]` and the last `keep_recent` messages, moving the start of that recent part
  back if it would begin with a `tool` message. Summarise everything between them with one call
  that offers no tools. Its user message is the older messages written out as text. Replace
  them with one user message: `Summary of earlier work:`, a newline, then the summary.
- If there is nothing between the task and the recent messages, do not compact.
