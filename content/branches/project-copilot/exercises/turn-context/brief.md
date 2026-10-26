# Assemble each turn's context

You now have a help centre the copilot can search and a memory of every customer. What reaches the
model is still up to you, and it decides almost everything: whether the answer is about the right
plan, whether last month's ticket is in view, whether the provider can reuse its cache, and
whether a citation points at a page the customer can open. This milestone builds the turn.

**So far** the codebase has `chunking.py` and `kb.py` from **Index the help centre** and `memory.py`
from **Remember each customer**. They are still checked, and the copilot now calls them on every
turn. This milestone adds `copilot.py`, drawing on **Assembling a prompt under a budget**, **A
stable prefix for prompt caching**, **Loading context just in time** and **Context provenance and
citation** (and on how **A context builder for a support agent** made them agree).

```text
tools     [OPEN_ARTICLE]                                   ┐ built once, never change
system    policy, a blank line, INSTRUCTIONS               ┘
messages  user: [now: ...] / Customer: ... / Sources: ... / question
          assistant: open_article(...)   tool: article body or error   ...   assistant: answer
```

```python
copilot = Copilot(client, kb, memory, policy="You are Tallybook's support copilot.")
reply = copilot.answer("cust-41", "How many payslips can I run each month?", now="2026-10-25 09:30")
reply.text, reply.citations, reply.calls
```

## Your task

Complete `copilot.py`. The starter gives `INSTRUCTIONS`, `OPEN_ARTICLE`, `Citation`, `Reply` and the
signatures: `Copilot(client, kb, memory, *, policy, k=5, source_budget=400, memory_budget=120,
load_budget=800, max_steps=6)` and `answer(user_id, question, *, now)`.

### The prefix

Every request offers exactly `[OPEN_ARTICLE]`, and its system prompt is `policy`, a blank line and
`INSTRUCTIONS` (`f"{policy}\n\n{INSTRUCTIONS}"`). Build both once. They must be byte-identical on
every request, in every turn, for every customer. Each `answer` is a fresh conversation whose
first message is the turn message, and within a turn each request repeats the previous one's
messages unchanged and adds to the end.

### The turn's filter

Search and open articles with `where = {"audience": "public"}`, plus `"plans"` set to the
customer's `plan` preference **lower-cased** if they have one (`"Team"` becomes `"team"`). A
customer with no `plan` preference may see any plan's articles. Internal articles never reach the
model.

### The turn message

One `user` message: these lines joined with `"\n"`.

```text
[now: <now>]
Customer:
<memory lines>
Sources:
<source lines>

<question>
```

- **Memory lines**: the customer's preferences as `- <key>: <value>` in key order, then the tickets
  from `memory.recall(user_id, question)` as `- ticket <id>: <subject> -> <resolution>`.
- **Source lines**: the chunks from `kb.search(question, k, where)`, in order, one line each:
  `[n] <title> > <section> (<article id>): <text>`, or `[n] <title> (<article id>): <text>` when
  the section is empty, with the text's whitespace collapsed to single spaces and `n` counting the
  kept sources from 1.
- **Budgets.** Memory lines are kept in order while the sum of `count_tokens(line)` stays within
  `memory_budget`, stopping at the first line that would go over (a later, shorter line is not
  used). Source lines work the same way with `source_budget`. A section with no lines is the
  single line `- (none)`.

### The loop

Make one model call per step, with the whole conversation, at most `max_steps` calls (then raise
`RuntimeError` mentioning `max_steps`). A reply with no tool calls ends the turn. Otherwise add
the assistant message with its tool calls and answer every call in order with a `tool` message:

- a tool other than `open_article`: `error: unknown tool`;
- `article_id` missing or not a non-empty string: `error: article_id is required`;
- not stored (`kb.article` gives `None`), or its `meta` fails the turn's filter (the same rule as
  search, including list fields): `error: unknown article <id>`;
- already opened this turn: `already open: <id>`;
- `count_tokens(body)` more than what is left of `load_budget` **this turn**:
  `error: over budget: <tokens> tokens needed, <left> left`;
- otherwise the article's `body`, which uses up its tokens for the rest of the turn.

Each turn starts with the whole `load_budget` and nothing opened.

### The reply

`Reply(text, citations, calls)`:

- `text` is the model's final reply, unchanged;
- `citations` has one `Citation(chunk_id, title, url)` per distinct `[n]` marker in the text that
  names a source shown this turn, in order of first citation, with the title and url from that
  chunk's metadata; other markers are ignored;
- `calls` lists every tool call of the turn in order as `{"tool": name, "arguments": dict(...)}`.
