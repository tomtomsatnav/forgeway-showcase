# Reflection

Raw episodes pile up: "ordered oat milk", "asked for the oat latte again", "said no to dairy on
Tuesday". Each is true and none is the point. **Reflection** is the step where an agent looks back
over what happened and writes down what it *means*: "prefers oat milk". It turns many episodes into
a few durable facts, which are cheaper to store, easier to retrieve and more useful in a prompt.
The *Generative Agents* paper (Park et al., 2023) triggers reflection when the importance of recent
events adds up past a threshold, so an agent reflects after something significant happens, not on a
timer.

Reflection also writes to long-term memory from a model's output, so it needs the same care as any
write. A fact with no evidence cannot be audited. A fact that cites an episode the model was never
shown is a hallucination wearing a footnote. So every fact carries the ids of the episodes that
support it, and you check those ids against what you actually sent.

```text
episodes (unreflected, importance 7+8+6 = 21 >= 20)
  [4] Ordered an oat latte
  [7] Asked the barista to swap to oat again
  [9] Declined the cheesecake: no dairy
reflector -> [{"subject": "user", "attribute": "diet", "value": "avoids dairy", "evidence": [4, 7, 9]}]
```

## Your task

Implement `reflect(reflector, episodes, facts, threshold=25)` in `reflect.py`. `episodes` is a list
of `Episode` objects in chronological order with an `id`, `text`, `importance` and a `reflected`
flag. `facts.set(subject, attribute, value, evidence)` stores a fact; `evidence` is a tuple of ids.

- The **pending** episodes are those whose `reflected` is false, in list order. If their importance
  adds up to less than `threshold`, return `0`. There is no model call and nothing changes. Exactly
  `threshold` is enough.
- Otherwise make **one** `reflector.complete` call with no tools. The only message is a `user`
  message with one line per pending episode, `[<id>] <text>`, joined with newlines. Reflected
  episodes are never sent again.
- The reply, stripped of surrounding whitespace, is a JSON array, optionally inside a Markdown
  code fence (a first line of ```` ``` ```` or ```` ```json ```` and a closing ```` ``` ````). Any
  other text before or after the array or the fence (`Sure: [...]`) makes the reply invalid; do
  not search it for an array. Each item is an object with `subject`,
  `attribute` and `value` (strings that are not empty after `strip()`) and `evidence`, a non-empty
  list of JSON integers (`true`, `false` and `2.0` are not integers, though Python compares
  them equal to 1, 0 and 2) in which **every id is the id of a pending episode**. Skip any item
  that breaks a rule, and carry on with the rest. For each valid item call `facts.set` with the three stripped strings and `evidence` as a
  tuple, with repeated ids removed and the first occurrence of each kept in place.
- If the reply is a valid JSON array (of any length, even if every item was skipped), mark every
  pending episode `reflected = True` and return the number of facts written.
- If the reply is not valid JSON or not an array, return `0`, write nothing and leave every episode
  unreflected, so the next call tries again. An error from the reflector propagates, also leaving
  every episode unreflected.
