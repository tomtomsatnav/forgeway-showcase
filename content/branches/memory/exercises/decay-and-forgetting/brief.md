# Decay and forgetting

A memory that only ever grows gets slower, noisier and more expensive, and it keeps things that
stopped being true long ago. People forget for good reasons: unused facts fade, while things we
keep coming back to get stronger. The classic model is the forgetting curve (Ebbinghaus, 1885):
retention falls off exponentially with the time since you last used something, and every
successful recall makes the next fade slower, which is the idea behind spaced repetition.

Forgetting is a policy, so it must be stated exactly. And it depends on time, which an agent
must never read from the wall clock: the store takes a `clock` function so that a test (or a
replay of last month's traffic) controls it.

```text
half_life = 100 s, importance 5
t=0    stored                              retention 1.0
t=100  idle 100 -> 0.5 ** 1 = 0.5
t=100  recalled: accesses 1, timer reset   retention 1.0
t=300  idle 200, stability 200 -> 0.5      (without the recall it would be 0.125)
```

## Your task

Implement `DecayingMemory(clock, half_life_s=86400.0, threshold=0.1)` in `decay.py`. `clock()`
returns the time in seconds.

- `add(text, importance=5, pinned=False)` stores a `Memory` and returns its id. Ids count up from 1
  and are never reused. `importance` is an integer from 1 to 10; anything else raises
  `ValueError`. A new memory's `last_touch` is `clock()` and its `accesses` is 0.
- `retention(memory_id)` is `1.0` for a pinned memory. Otherwise
  `0.5 ** (idle / (half_life_s * importance / 5 * (1 + accesses)))`, where `idle` is
  `clock() - last_touch` (zero if negative). An unknown id raises `KeyError`.
- A memory is **live** when its retention is greater than or equal to `threshold`. Dead memories
  stay in the store until `sweep()` but are invisible to `recall`.
- `recall(query, k=3)` considers the live memories that share at least one word with the query.
  Words are the runs of ASCII letters and digits (`a-z`, `0-9`) in the lower-cased text, so
  `"Harbour, at dawn!"` has the words `harbour`, `at` and `dawn`, and `café` has `caf`. Rank
  them by retention, highest first, equal retention newest (highest id) first, and return up to `k`
  of them (`k` of 0 or less returns `[]`). Every retention is computed before any is changed. Then
  each returned memory is **reinforced**: its `accesses` goes up by one and its `last_touch` becomes
  `clock()`. Memories that were not returned are untouched.
- `sweep()` deletes every dead memory and returns their ids, smallest first. `ids()` lists the ids
  still stored, smallest first.
