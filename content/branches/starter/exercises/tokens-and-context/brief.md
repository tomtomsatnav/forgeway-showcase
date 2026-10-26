# Tokens and the context window

Models read and write **tokens**, not characters or words, and every model has a **context
window**: the most tokens it can take in one request. A long chat history eventually exceeds
it, and the API rejects the call. Production chat code therefore trims history to fit a
budget before sending.

The system prompt and every message all count towards the budget. Two rules keep a trimmed
conversation sensible: drop the *oldest* turns first, and never drop the system prompt or the
user's latest message. Most APIs also want the history to start with a user message, so an
assistant reply whose question was dropped must go too.

`forgeway_kit.count_tokens` gives a deterministic count (words and punctuation marks each count
as one token), the same one the fake model uses:

```python
count_tokens("Hello, world!")  # 4: Hello , world !
```

## Your task

Implement `fit_to_budget(system, messages, budget)` in `budget.py`. It returns the messages to
send: the longest suffix of `messages` that, together with `system`, is at most `budget`
tokens, and that starts with a user message. The latest message is always kept. If the system
prompt plus the latest message alone exceed the budget, raise `ValueError`.
