# A router

One prompt that tries to do everything gets long, brittle and expensive. A **router** splits the
work: a cheap first call decides what kind of request this is, and a specialist with a short,
focused prompt handles it. Refund questions go to a refunds specialist, bug reports to a
technical one, and anything the classifier cannot place goes to a general fallback.

```text
message ──► classify ──► "billing" ──► billing specialist ──► answer
              │
              └─ unrecognised reply ──► default specialist
```

The classifier is a model, so its output is untrusted text. It may reply `billing`, `Billing.`
or `I'd say billing, since it mentions an invoice`. Your code, not the model, must turn that
into one valid route, and decide what happens when it cannot.

## Your task

In `router.py`, implement:

- `classify(client, message, routes, default)`: one model call. The system prompt lists every
  route as `name: description` and asks for the route name only. The user message is `message`.
  Keep `max_tokens` small (at most 32) and `temperature` at 0. Return the first route name
  mentioned in the reply, matched as a whole word and ignoring case. A name is a whole word
  when no letter, digit, underscore or hyphen touches either end of it, so `order` is not in
  `reorder`, `re-order` or `order_id`, but it is in `(order)`. If no route is mentioned, return
  `default`.
- `answer(client, message, routes, default)`: classify, then make a second call using the chosen
  route's `system` prompt and only the original message. Return `Routed(route, text)`.

`routes` maps a name to a `Route(description, system)`.
