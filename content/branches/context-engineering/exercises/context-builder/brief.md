# A context builder for a support agent

You have built the parts: a budget with priorities, a stable prefix, few-shot examples chosen by
similarity, loading on demand, pruning, and cited provenance. Each worked on its own. A real agent
needs them to work *together*, and they pull against each other. Pruning rewrites old messages,
which the cache wants left alone. The best examples for one question are the wrong ones for the
next, and they cost tokens every turn. Loading on demand needs to know what is still in front of
the model, which pruning changes. A citation is only honest if the model could actually see the
source. The skill here is deciding **when**, and **where**, each thing happens.

You are building the context for a support desk agent that holds a conversation over many turns.
It has a catalogue of help-centre documents and loads them as it needs them, and a bank of past
tickets with the replies that worked. Every request it sends is graded, so the layout below is
exact.

```text
tools     load_document                                       ┐ never change
system    policy, then the catalogue (id: title)              ┘
messages  turn 1: user, (assistant calls, tool results)..., assistant reply
          turn 2: ...                      older tool results pruned at the start of a turn
          turn N: user  [now: ...] notes... examples... question  ← everything about this turn
```

## Your task

Four files, which import each other.

**`notes.py`** — `fit_notes(notes, budget)` chooses which per-turn notes fit. A `Note` has a `text`
and a `priority`. Visit the notes from the highest priority down (equal priorities in list order).
Keep a note whole if its tokens (`count_tokens`) fit in what is left of `budget`; otherwise skip it
and carry on. A note with no tokens is dropped. Return the kept notes in their original order.

**`pruning.py`** — `prune_stale(messages, keep)` returns a new list. A **round** is an assistant
message with tool calls and the `tool` messages directly after it. The newest `keep` rounds are
left alone. In every older round, the content of each `tool` message becomes
`[pruned: {name}, {n} tokens]`, where `name` is the tool call it answers (matched by
`tool_call_id`) and `n` is the token count of the content replaced, but only if the placeholder has
fewer tokens than the original. Every message stays, in order.

**`fewshot.py`** — `choose_examples(pool, query, k, budget)` chooses worked examples. An `Example`
has a `question` and an `answer`, and costs the tokens of both. Rank the pool by the
`cosine_similarity` of `HashingEmbedder()` vectors (default settings) of `query` and each
`question`, highest first, equal similarities in pool order. Visit it in that order, keeping an
example if it fits in what is left of `budget` and skipping it otherwise, until `k` are kept.
Return them best match first.

**`session.py`** — `SupportSession(client, policy, catalogue, read, *, examples=(), examples_k=3,
examples_budget=120, notes_budget=60, load_budget=400, keep_rounds=1, max_steps=8)` with
`send(text, *, now, notes=())`, which returns `Reply(text, sources)`. The starter gives you
`Entry`, `Reply` and the `LOAD` tool.

- **Requests.** Offer exactly `[LOAD]`. The system prompt is `policy`, a blank line, `Documents:`,
  a newline, and one `- {id}: {title}` line per catalogue entry, joined with newlines. Both are
  built once and never change.
- **Start of a turn.** First replace the stored history with `prune_stale(history, keep_rounds)`.
  This is the only time anything is pruned, and nothing else already sent ever changes: earlier
  user messages, examples and all, stay exactly as they were. Then add one user message: the lines
  `[now: {now}]`, `- {note}` for each note kept by `fit_notes(notes, notes_budget)` and an empty
  line; then, for each example `choose_examples(examples, text, examples_k, examples_budget)`
  returns, in the reverse of the order it returns them (so the best match is last),
  `Q: {question}`, `A: {answer}` and an empty line; and last `text`, all joined with `"\n"`.
- **The loop.** One model call per step, with the whole history, at most `max_steps` in a turn
  (then `RuntimeError` mentioning `max_steps`). A reply with no tool calls ends the turn: add it to
  the history as an assistant message. Otherwise add the assistant message and answer every call,
  in order, with a `tool` message:
  - `doc_id` missing or not a non-empty string: `error: doc_id is required`
  - not in the catalogue: `error: unknown document {doc_id}`
  - its **full text is still in the history** (a delivered text no `tool` message holds any more,
    because it was pruned, does not count): `already loaded: {doc_id}`
  - more tokens (the entry's `tokens`) than are left of `load_budget` **in this turn**:
    `error: over budget: {tokens} tokens needed, {left} left`, without calling `read`
  - otherwise `read(doc_id)` (it returns the document's text as a string), which uses up the entry's `tokens` for this turn.
- **Sources.** `Reply.sources` lists the ids written in square brackets in the reply, such as
  `[kb-12ab]` (letters, digits, `_` and `-`), in order of first citation without repeats, keeping
  only ids whose full text is in the history the final request was made from.
