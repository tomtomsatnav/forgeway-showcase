# Handling truncated replies

Every request sets `max_tokens`, an upper limit on the reply length. If the model has more to
say, it is cut off mid-sentence, and the only sign is `completion.stop_reason == "max_tokens"`
instead of `"end_turn"`. Code that ignores this ships half an answer to the user, or half a
JSON document to a parser.

The usual fix is to continue: send the conversation again with the partial reply as an
assistant message, followed by a user message asking it to carry on.

```python
completion = client.complete(messages, max_tokens=50)
if completion.stop_reason == "max_tokens":
    messages += [
        Message(role="assistant", content=completion.text),
        Message(role="user", content="Continue."),
    ]
```

Always cap the number of continuations. A model that never stops would otherwise loop for ever
and run up a bill.

## Your task

Implement `complete_fully(client, question, *, max_tokens=50, max_continuations=5)` in
`continuation.py`. Call the model with `max_tokens`; while the reply was cut off and you have
continued fewer than `max_continuations` times, continue it. Return all the pieces joined
together as one string. If the cap is reached, return what you have.
