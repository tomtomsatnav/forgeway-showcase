# A write policy

An agent that stores everything drowns in its own notes: "ok", "thanks", a joke, an angry
message. Worse, whatever it stores comes back in later prompts, so a careless write is a
permanent one. A memory needs a **write policy**: a decision, turn by turn, about what is worth
keeping, in what form, and what must never be kept (passwords, card numbers, anything the user
would not want repeated).

The decision is a judgement, so a model makes it, with a **classifier** call. Your code then does
what code is good at: it does not believe the reply. The classifier may wrap its JSON in a
Markdown fence, forget a field, invent a `kind`, or return prose. A write based on a malformed
reply puts garbage into long-term memory.

```text
turn:       "By the way, I moved to Leeds last month."
classifier: {"remember": true, "kind": "fact", "subject": "user", "attribute": "city", "value": "Leeds"}
you write:  store.add_fact("user", "city", "Leeds")
```

Whether a turn is worth remembering depends on the classifier, not on words in the turn: a user can
say "please remember this" about nothing, and mention something vital in passing. Your tests give
the classifier arbitrary, seeded decisions and check that you followed them exactly.

## Your task

Implement `apply_policy(classifier, store, turn)` in `policy.py`. `store` has
`add_fact(subject, attribute, value)` and `add_episode(text, importance)`.

- Make **one** `classifier.complete` call per turn, with no tools. The only message is a `user`
  message that is exactly `turn`; put the policy in the system prompt.
- The reply is a JSON object, optionally inside a Markdown code fence (a first line of ```` ``` ````
  or ```` ```json ```` and a closing ```` ``` ````). Any other text before or after the object or
  the fence (`Sure! {...}`) makes it not valid JSON: do not search the reply for braces. Decide in
  this order and return the status:
  1. Not valid JSON, not an object, or `remember` is not a JSON boolean: write nothing, `"invalid"`.
  2. `remember` is `false`: write nothing, `"skipped"`.
  3. `sensitive` is `true`: write nothing, `"withheld"`. Only the JSON `true` counts: absent or
     any other value, including `1`, `1.0` and `"true"`, means not sensitive.
  4. `kind` is `"fact"`: `subject`, `attribute` and `value` must each be a string that is not empty
     after `strip()`. Call `store.add_fact` with the three stripped strings and return `"fact"`.
     Otherwise `"invalid"`.
  5. `kind` is `"episode"`: `summary` must be a string that is not empty after `strip()`.
     `importance` is optional and defaults to 5; if present it must be a JSON integer (a bool, a
     float or a string is invalid), and is clamped to 1 to 10. Call
     `store.add_episode(summary.strip(), importance)` and return `"episode"`. Otherwise `"invalid"`.
  6. Any other `kind`: `"invalid"`.
- Bad content never raises. An error from the classifier itself (a `ModelError`) does propagate.
