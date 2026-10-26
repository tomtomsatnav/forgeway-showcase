# Semantic facts and contradictions

Episodes record what *happened*. **Semantic memory** records what is *true*: the user lives in
Leeds, prefers metric units, is allergic to peanuts. Facts are stored one value per
`(subject, attribute)`, so asking "where does Priya live?" is a lookup, not a search.

The hard part is that facts change and sources disagree. Priya moves house. A document says one
thing and she says another. A model guesses something she never said. A memory that simply
overwrites on every write forgets the user's own words the moment an uncertain guess arrives, and a
memory that never overwrites is stuck on last year's address. You need a **resolution rule**, and
it must be written down exactly, because "usually the newest wins" is not something you can test.

```text
assert Priya lives_in Leeds   (t=100, user)      -> added
assert Priya lives_in Leeds   (t=120, document)  -> confirmed
assert Priya lives_in York    (t=90,  user)      -> stale      (older than what we hold)
assert Priya lives_in York    (t=130, inferred)  -> disputed   (less trusted than the user's word)
assert Priya lives_in York    (t=140, user)      -> updated    (Leeds moves to history)
```

## Your task

Implement `FactStore` in `facts.py`. A claim is `assert_fact(subject, attribute, value, at, source)`
with `at` a number (when it was stated) and `source` one of `user`, `document` or `inferred`, ranked
in that order (3, 2, 1). Any other source raises `ValueError`.

- **Keys and values.** Subject and attribute are compared after `strip()` and `lower()`, and stored
  that way. The value is stored with `strip()` applied and its case kept. Two values are the same
  if they are equal after `strip()` and `casefold()`.
- **Resolution**, in this order, returning the status as a string:
  1. Nothing is stored for the key: store the claim, `"added"`.
  2. Same value as the current fact: `"confirmed"`. Keep the stored wording, raise `at` to the larger
     of the two, and keep the more trusted source (the stored one if equal).
  3. A different value, with `at` earlier than the current fact's: `"stale"`. Ignore it.
  4. A different value from a source ranked below the current fact's: `"disputed"`. Ignore it.
  5. A different value with the same `at` and the same rank: `"disputed"`. Ignore it.
  6. Otherwise `"updated"`: the current fact goes to the end of the key's history and the claim
     becomes current.
- `get(subject, attribute)` returns the current `Fact` or `None`. `history(subject, attribute)` returns
  the superseded facts, oldest first. `facts()` returns every current fact sorted by `(subject,
  attribute)`.
- `retract(subject, attribute)` removes the current fact **and** its history and returns `True`, or
  returns `False` if nothing was stored.
