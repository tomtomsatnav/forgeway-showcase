# Output guardrails with retries and refusal

You ask a model for JSON and usually get it. Sometimes you get prose, a missing field, a number
as a string, or an answer that breaks house policy ("we guarantee a refund"). Downstream code and
customers should never see those replies. An **output guardrail** checks every reply against a
**schema** (the shape) and a **policy** (what it may say), and when a reply fails it either
**retries** with the problems explained or, when attempts run out, **refuses**.

```text
reply ──► valid JSON object? right fields and types? no banned phrase?
              │ yes ──► return it
              │ no  ──► tell the model what was wrong ──► try again ... ──► refuse
```

A refusal has to be safe by construction. It is built from your own text and never includes the
rejected reply.

## Your task

Implement `guarded_json(client, prompt, schema, banned=(), max_attempts=3, system=None)` in
`guard.py`.

`schema` maps each field name to one of `"string"`, `"integer"`, `"number"` or `"boolean"`. A reply
is **acceptable** only if, after stripping surrounding whitespace, it parses with `json.loads` to
an object and:

- every schema field is present, and no other field is (extra fields are a problem);
- `string` is a JSON string; `boolean` is `true` or `false`; `integer` is a JSON integer (`3`, not
  `3.0` or `true`); `number` is any JSON number, integer or not (never `true` or `false`);
- no string value contains a phrase from `banned` (compared case-insensitively, as a substring).
  Only the object's top-level string values are checked; field names and other types are not.
  Check the policy on every JSON object, even one that also breaks the schema.

Behave like this:

1. Start with one `user` message holding `prompt`, and pass `system` through. Make at most
   `max_attempts` requests.
2. An acceptable reply is returned as `{"status": "ok", "data": <the object>, "attempts": n}`.
3. A rejected reply is retried: append the rejected reply as an `assistant` message, then a `user`
   message that names every problem: the field name for each schema problem (missing, wrong type
   or unexpected) and the banned phrase for each policy problem (in any case). Reply text that is not a JSON
   object is a problem too.
4. If the last attempt is also rejected, return
   `{"status": "refused", "reason": ..., "attempts": max_attempts}`. `reason` is `"policy"` when
   the last reply contained a banned phrase (whether or not it also broke the schema), otherwise
   `"schema"`. Nothing from any rejected reply
   may appear in the result.
