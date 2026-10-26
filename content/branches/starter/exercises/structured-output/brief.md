# Structured output

Programs need data, not prose. The common pattern is to ask the model for JSON, parse it, and
hand the result to the rest of your code. Models are good at this but not perfect: they add
commentary, leave out a field, or emit a trailing comma. Code that trusts the reply will
crash downstream, far from the cause.

In production, reach for your provider's **native structured output** first: a JSON-schema
response format or a forced tool call constrains the model to your schema and removes most of
these failures. Validate-and-repair, which you write here, is the safety net behind it, and the
only option when a model or provider lacks the feature.

So treat model output as untrusted input: parse it, validate it, and when it is wrong give the
model one chance to fix it by showing it exactly what was wrong.

```python
try:
    data = json.loads(reply)
except json.JSONDecodeError as error:
    # send: original request, the bad reply (assistant), then the error (user)
    ...
```

## Your task

Implement `extract_person(client, text)` in `extract.py`. It must return a dict with a
non-empty string `name` and an integer `age` (a boolean is not an integer), extracted from `text` by the model.

- Prompt the model to reply with only a JSON object with the keys `name` and `age`.
- If the reply is not valid JSON, or the fields are missing or of the wrong type, ask again
  **once**: send the original request, the bad reply as an assistant message, and a user
  message that includes the error.
- If the second reply is also bad, raise `ValueError`.
