# Remember each customer

A support copilot that forgets everything between conversations makes customers repeat
themselves: which plan they are on, that they want replies in British English, that last month's
import failure was fixed by clearing the queue. It should remember those things, and it must keep
each customer's memory to that customer, survive a restart, and forget on request. A memory that
leaks between accounts or cannot be deleted is a privacy incident, not a feature.

**So far** the codebase has `chunking.py` and `kb.py` from **Index the help centre**: structure-aware
chunks with section paths and links, and a knowledge base with hybrid search, filters and
updates. They stay in your workspace and are still checked: the copilot will read the help centre
through them. This milestone adds `memory.py`, drawing on **A write policy**, **Episodic recall**
and **Per-user isolation and deletion** (and on how **A personal assistant that remembers** kept
everything in saved JSON).

```python
memory = CustomerMemory(data, clock)
learn_preferences(extractor, memory, "cust-41", "I'm on the Team plan, and please keep it brief.")
memory.add_ticket("cust-41", "Import stuck", "Cleared the import queue")
memory.recall("cust-41", "my import will not finish")  # -> [Ticket(1, ...)]
```

## Your task

Complete `memory.py`. The starter gives `Ticket`, `EXTRACT_SYSTEM` and the signatures.

### Storage

`CustomerMemory(data, clock)`: `data` maps each user id to that customer's whole memory as **JSON
text**, and `clock()` gives the time in seconds. Write `data[user_id]` after every change and read
it back on every call, so a new `CustomerMemory` over a copy of `data` (a restarted process) sees
everything. The JSON must not depend on its key: text moved to another user id works there.
Keep the memory itself in that text, and nothing anywhere else (no module state, no files): the
checks restart in a new Python process that starts with only `data`.
Reading, including `recall` and a `forget` that finds nothing, never creates an entry.

- `set_preference(user_id, key, value)`: the key is stripped and lower-cased, the value stripped
  (raise `ValueError` if either is then empty). It returns `"added"` for a new key, `"unchanged"`
  when the stored value is the same after `strip()` and `casefold()` (the stored wording is kept),
  and `"updated"` otherwise (the new value replaces it). `preferences(user_id)` is a dict sorted by
  key.
- `add_ticket(user_id, subject, resolution)` stores a `Ticket` with both texts stripped and
  `at = clock()`, and returns its id: 1, 2, 3, ... for that customer, **never reused** while the
  customer's entry exists, even after a ticket is forgotten or the process restarts.
  `tickets(user_id)` lists them in id order.

### Recall

`recall(user_id, query, k=3)` returns that customer's best `k` tickets, best first, by
**relevance + recency**:

- relevance is the cosine similarity of the `HashingEmbedder()` vectors (the default size) of the
  query and `f"{subject} {resolution}"`;
- recency is `0.5 ** (age_days / 30)`, with the age taken from `clock()` and never below zero;
- only tickets whose relevance is **above zero** are returned, however recent;
- equal scores put the higher id first.

### Deletion and isolation

- `forget(user_id, topic)` ignores surrounding space in `topic` and ignores case on both sides. An
  empty topic removes nothing. It removes every ticket whose subject or resolution contains the
  topic and every preference whose text `f"{key}: {value}"` contains it, and returns how many it
  removed. Afterwards the topic must not appear anywhere in that customer's saved text.
- `delete_user(user_id)` removes the customer's entry from `data` and returns `True`, or `False` if
  there was none.
- Nothing you do for one customer may read or change another customer's entry.

### Learning preferences

`learn_preferences(extractor, memory, user_id, message)` makes **one** call to the `extractor`
model: the only message is the customer's message as typed, and the system prompt is
`EXTRACT_SYSTEM`. The reply should be a JSON array (a Markdown code fence around it is allowed).
Store every item that is an object with a non-empty string `key` and a non-empty string `value`
(after stripping) with `set_preference`, in order, and skip the rest. A reply that is not a JSON
array stores nothing and does not raise. Return the number of items stored. The extractor decides:
do not try to spot preferences in the message yourself.
