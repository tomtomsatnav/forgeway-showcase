# Schema-constrained output

In "Structured output" you asked for JSON in the prompt, then parsed, validated and repaired what
came back. That works anywhere, but it is the weakest option. Most current providers can
**constrain** the reply instead: you send a JSON Schema and the model's decoding is restricted so
that the reply fits it. There are two common forms:

- **Native structured output**: the schema goes in a `response_format` argument and the reply's
  text is JSON that fits it.
- **A forced tool call**: you offer one tool whose `input_schema` is your schema and force the
  model to call it with `tool_choice={"name": ...}`. The tool call's arguments are your object.
  This predates native support and works on more providers.

Constrained does not mean trusted. A provider may not support every schema keyword, a model
version may behave differently, and a proxy in between may drop the setting. Validate the
result anyway; it costs microseconds. And a constrained model can still **refuse**: then the
reply has `stop_reason == "refusal"` and some prose explaining why, which is a decision to
report, not malformed JSON to repair.

Some current models reject a forced `tool_choice` (often while extended thinking is on). With
those, offer the tool under `tool_choice="auto"` with a strict input schema and tell the model to
call it; that route is not part of this exercise.

```python
completion = client.complete(messages, response_format=schema)
if completion.stop_reason == "refusal":
    ...
data = json.loads(completion.text)
check(data, schema)  # the starter's validator: raises ValueError naming the first problem
```

## Your task

Implement `extract(client, text, schema, name, *, supports)` in `schema_output.py`. It returns a
dict that fits `schema`, extracted from `text`. `supports` is a set naming what this provider can
do: it may contain `"response_format"` and `"tool_choice"`. The starter gives you `check(value,
schema)`, a small JSON Schema validator, and the `Refused` exception.

Use the strongest route available, and make one `client.complete` call on it:

1. If `"response_format"` is in `supports`: send `response_format=schema` (the schema itself),
   with no tools. Parse the reply's text as JSON.
2. Otherwise, if `"tool_choice"` is in `supports`: offer exactly one `Tool` named `name` whose
   `input_schema` is `schema`, with `tool_choice={"name": name}`, and no `response_format`. The
   first tool call's arguments are the object.
3. Otherwise, send neither `response_format` nor tools. Put the schema in the prompt (every field
   name must appear in it, for example with `json.dumps(schema)`) and use the parse-and-repair
   loop from "Structured output": if the reply is not valid JSON or fails `check`, re-ask once
   with the original request, the bad reply as an assistant message and a user message that
   includes the error. If the second reply is also invalid, raise `ValueError`.

On every route:

- The text to extract from must be in the prompt.
- If a reply's `stop_reason` is `"refusal"`, raise `Refused(completion.text)` at once, without
  parsing it or asking again.
- Validate the object with `check`. On routes 1 and 2, a reply that is not valid JSON or does not
  fit the schema raises `ValueError` without asking again: the provider promised the schema, so
  a reply that breaks it is a bug to surface, not a slip to correct.
