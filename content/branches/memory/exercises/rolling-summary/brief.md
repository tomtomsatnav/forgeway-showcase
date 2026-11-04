# A rolling summary

A chat that runs for hours cannot keep every message in the prompt. The cheapest kind of memory is
a **rolling summary**: keep the last few messages word for word, and squeeze everything older into
a short summary that is rewritten as the chat grows. Each time you fold, the summariser sees the
*previous summary* plus the newly old messages, so facts survive from fold to fold without the
prompt ever growing.

```text
keep_recent = 2
add 1, 2         recent: [1, 2]                      summary: ""
add 3            fold [1] into ""                    recent: [2, 3]   summary: S1
add 4            fold [2] into S1                    recent: [3, 4]   summary: S2
prompt:  user "Summary of the conversation so far:\nS2", then 3, 4
```

You will not be told what the summary says, only that it is whatever the summariser replied. Your
tests give the summariser a fresh, unguessable reply every time, so the only way to pass is to
carry that exact reply forward. Summarising for a long task inside a tool loop is a different
problem, covered by the compaction exercise; this one is the plain chat version.

## Your task

Implement `RollingMemory(summariser, keep_recent=4)` in `rolling.py`. `summariser` is a model
client used only to summarise.

- `add(role, content)` appends a `Message` to `recent`. If `recent` now holds more than
  `keep_recent` messages, fold every message except the last `keep_recent` into the summary with
  **one** `summariser.complete` call, then drop them from `recent`.
- The call has no tools and one `user` message: the previous summary (the text `(none)` when there
  is none), then the folded messages, oldest first, one `role: content` line each. Nothing else
  from the conversation: messages an earlier fold already summarised, and older summaries, are
  never sent again. Tell the
  summariser what to do in the system prompt. The new `summary` is the reply with surrounding
  whitespace stripped.
- `messages()` returns what belongs in the next prompt: when there is a summary, first a `user`
  message `Summary of the conversation so far:` + a newline + the summary, then the `recent`
  messages. With no summary yet, just the `recent` messages.
- If the summariser raises, `add` lets the error propagate. The new message is kept and nothing is
  lost; the next `add` folds everything that is pending, in one call.
