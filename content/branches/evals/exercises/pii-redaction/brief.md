# Redacting personal data before the model

Customers paste things into support chats that you never wanted: an email address, a card
number, a National Insurance number. If that text goes to a model provider it can be logged,
retained and, in the worst case, repeated back to someone else. An **input guardrail** removes
the sensitive parts *before* the request is built, so what leaves your system is already safe.

The check that matters is what reached the model, not what your code printed:

```text
"Call me on +44 7700 900123"  ──► redact ──►  "Call me on [PHONE]"  ──► model
```

Regular expressions are the right tool for data with a fixed shape, and a poor one for
anything else, so the patterns here are deliberately narrow. Redaction is not a security
boundary on its own, but it removes the easy leaks.

## Your task

Implement `redact(text)` and `ask(client, history, text, system=None)` in `redact.py`.

`redact` replaces every match of these four patterns, **in this order**, each over the text the
previous step produced. Patterns are case-sensitive and use Python's `re`:

| Order | Placeholder | Pattern |
| --- | --- | --- |
| 1 | `[EMAIL]` | `[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}` |
| 2 | `[CARD]` | `\b(?:\d{4}[ -]?){3}\d{4}\b` |
| 3 | `[NINO]` | `\b[A-Z]{2}\d{6}[A-D]\b` |
| 4 | `[PHONE]` | `(?<!\w)\+?\d(?:[ -]?\d){9,12}(?!\w)` |

So an email is `[EMAIL]` even if its local part is all digits, and a 16-digit card with hyphens
is `[CARD]` rather than part-phone. Anything else, including `ab@c`, `AB12345C` and a nine-digit
number, stays exactly as written.

`ask` sends one request and returns the reply text. `history` is a list of earlier `Message`s
(user and assistant); `text` is the new user message. Every message the model receives must have
its `content` redacted, in order: the history first, with each message's role kept, then `text`
as a `user` message. The `system` prompt is your own text and is passed through unchanged.
