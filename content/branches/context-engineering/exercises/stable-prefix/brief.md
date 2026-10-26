# A stable prefix for prompt caching

Every request to a model resends the whole prompt, and most of it is the same as last time:
the rules, the tool definitions, the reference material, the conversation so far. Providers
exploit this with **prompt caching**. If the start of a new request is *byte-for-byte identical*
to a recent one, the provider reuses its work for that part and charges less for it, and the
reply starts sooner. The cache works on prefixes only: change one character early and everything
after it misses. Some providers cache a long enough prompt automatically; others, Anthropic's
among them, cache only up to the breakpoints you mark (`cache_control`, a few per request) and
read the prefix in a fixed order: tools, then system, then messages. Either way, the layout below
is what makes a hit possible.

That makes the layout of a prompt a performance decision. Order it from the most stable to the
most volatile:

```text
tools          never change
system         instructions + reference docs: never change in a session
messages       turn 1, turn 2, ... append-only
newest message  [now: 10:42]  notes for this turn  the user's text      ← the only new part
```

The classic mistakes are all the same mistake: a timestamp in the system prompt, reference
documents re-sorted by relevance each turn, a note edited into an old message. Each one moves a
change to the front and throws away the cache for the rest of the request.

## Your task

In `chat.py`, implement `CachedChat(client, instructions, reference, tools=())` with a method
`send(text, *, now, notes=())` that returns the model's reply text. `reference` is a list of
strings; `tools` is a sequence of `Tool`s.

- The **system prompt** is `instructions` and then each `reference` string, in order, all joined
  with `"\n\n"`. It is built once and is the same on every request.
- The `tools` are offered on every request, in the order given.
- Each call to `send` appends one user message. It is these lines joined with `"\n"`:
  `[now: {now}]`, then `- {note}` for each note, then an empty line, then `text`.
- The conversation is **append-only**. Each request sends every message so far, exactly as
  before: all earlier user messages exactly as they were sent (volatile lines included), each
  assistant reply as a message with the text the model returned, and then the new user message.
- Make one model call per `send` and return its text.
