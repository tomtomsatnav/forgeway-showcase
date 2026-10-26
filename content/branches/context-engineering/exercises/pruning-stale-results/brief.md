# Pruning stale tool results

In a long agent run, tool results are the bulk of the conversation: a file read, a search page, a
log dump. They matter at the moment they arrive and much less ten steps later, but they are resent
on every call. Pruning them is the cheapest way to keep a long run inside its window, and unlike
summarising it costs no model call and cannot invent facts.

The rule has to respect the shape of a tool conversation. An assistant message that asks for
tools and the `tool` messages that answer it belong together (a **round**), and a provider
rejects a conversation in which a call has no result. So pruning must never remove half of a
round. The safe method is to **keep every message and replace only the content** of old results
with a short note of what was there:

```text
before:  assistant(get_page 1)  tool: <600 tokens of page one>
after:   assistant(get_page 1)  tool: [pruned: get_page, 612 tokens]      ← call and id intact
```

The model can still see that it fetched page one and, if it needs it again, fetch it again.

## Your task

In `pruning.py`, implement `prune_stale(messages, keep)` and `run_pruned(client, task, tools,
registry, keep=2, max_steps=20)`. Tokens are counted with `forgeway_kit.count_tokens`.

`prune_stale` returns a new list; the input and its messages are not changed.

1. A **round** is an assistant message with `tool_calls` and the `tool` messages directly after
   it. Other messages (user messages, plain assistant replies) are not part of a round.
2. The newest `keep` rounds are fresh and stay exactly as they are. Every older round is stale.
3. In a stale round, each `tool` message's content is replaced by `[pruned: {name}, {n} tokens]`,
   where `name` is the name of the tool call it answers (matched by `tool_call_id`) and `n` is the
   token count of the content being replaced. Keep the message's `tool_call_id`.
4. A replacement is made only if the placeholder has **fewer tokens** than the original, so
   short results stay and pruning never makes a conversation bigger.
5. Every message stays, in the same order. Only `tool` content can change.

`run_pruned` is the tool loop you know: one `client.complete(messages, tools=tools)` per step,
every call answered in order, and the model's final text returned. A tool is called as
`registry[name](**arguments)` and its result becomes the content of the `tool` message as
`str(result)`; the content is `error: <message>` if the tool raises and `error: unknown tool` if it
is not in `registry`. Before **every** model call, replace the stored history with
`prune_stale(history, keep)`, so a result that has been pruned stays pruned. After `max_steps`
model calls without a final reply, raise `RuntimeError` mentioning `max_steps`.
