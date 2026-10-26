# System prompts and few-shot examples

A system prompt sets the standing rules for a conversation: the role, the tone, the output
format. It is sent separately from the messages, so it keeps its authority however long the
conversation grows. Putting rules in a user message instead makes them easy to dilute or
override.

**Few-shot prompting** shows the model what you want rather than describing it. You include
a few example exchanges before the real question, as alternating user and assistant messages:

```python
client.complete(
    [
        Message(role="user", content="great film!"),
        Message(role="assistant", content="positive"),
        Message(role="user", content="a dull, slow mess"),
        Message(role="assistant", content="negative"),
        Message(role="user", content="loved the soundtrack"),  # the real input
    ],
    system="Classify the sentiment of the text as positive or negative.",
)
```

## Your task

Implement `answer(client, system_prompt, question, examples=())` in `prompts.py`.

- `examples` is a sequence of `(input, output)` pairs.
- Send `system_prompt` as the system prompt, not as a message.
- Send each example as a user message followed by an assistant message, in the order given.
- Finish with `question` as the last user message, then return the reply text.
