# A personal assistant that remembers

You have built the parts of a memory one at a time: a write policy, episodes and facts, a notebook
the model reaches through tools, isolation, deletion and reflection. Each worked alone. A product
needs them to work **together**, across days, over restarts, for many people at once, and that is
where it goes wrong. A policy that writes into a store the tools cannot see. A reflection step
that forgets what it already reflected on after a restart. A deletion that removes the sentence the
user complained about, and leaves behind the fact that was derived from it.

This project is a memory service for a personal assistant. Your tests run several simulated
sessions. Each session runs in a new Python interpreter: your modules are imported afresh, the
saved data goes through a round trip as JSON text, and the clock jumps forward. Only what you wrote
into the data survives, not anything kept in memory, in `os.environ` or on a module: the tests look for what you stored in that text, and may move a user's
saved text to another user id before reading it back.

```text
Assistant.chat(user, message)
  1. policy      classifier decides: fact, episode, skip or sensitive   -> MemoryStore
  2. tool loop   model may call recall(query) / forget(topic)           <- MemoryStore
  3. reflection  unreflected episodes worth enough? -> facts with evidence -> MemoryStore
MemoryStore: data[user_id] = JSON text   (a new store over a copy of data = a restarted process)
```

## Your task

Complete three files. The starter gives signatures and the data classes. The models are
`forgeway_kit` clients, one each for the assistant itself, the classifier and the reflector.

### `memstore.py`: `MemoryStore(data, clock)`

`data` maps each user id to that user's whole memory as **JSON text**, and `clock()` gives the
time in seconds. Write `data[user_id]` after every change and read it back on every call, so that
a new store over a copy of `data` sees everything. Reading never creates an entry. Beyond that the
JSON shape is yours.

- `add_episode(user_id, text, importance)` stores an `Episode` (`at` is `clock()`, `reflected`
  false) and returns its id: 1, 2, 3 for that user, never reused. `episodes(user_id)` lists them in
  id order. `mark_reflected(user_id, ids)` sets `reflected` on those episodes.
- `set_fact(user_id, subject, attribute, value, evidence=())` keeps one current value per subject
  and attribute (both stripped and lower-cased; the value stripped, case kept). The newest claim
  wins. If nothing is stored it adds the fact (`"added"`). If the value is the same after `strip()`
  and `casefold()` it keeps the stored wording and evidence and sets `at` to `clock()`
  (`"confirmed"`). Otherwise the current value, its `at` and its evidence move to the end of that
  key's history and the new value becomes current with `at = clock()` and the given evidence
  (`"updated"`). `facts(user_id)` lists current facts sorted by `(subject, attribute)`.
  `history(user_id, subject, attribute)` lists superseded facts, oldest first.
- `recall(user_id, query, k=3)` returns the text of a `recall` tool result:

  ```text
  facts:
  - <subject> <attribute>: <value>
  episodes:
  - <episode text>
  ```

  The facts are those whose `subject` and `attribute` share at least one word with the query (words
  are runs of `a-z` and `0-9` in lower-cased text), sorted by `(subject, attribute)`, at most 5.
  The episodes are the user's top `k` by **recency + importance / 10 + relevance**, best first:
  recency is `0.5 ** (age_hours / 24)` with age from `clock()` (never below zero), relevance is the
  cosine similarity of the `HashingEmbedder()` vectors of the query and the episode text, or 0 if
  it is negative, and equal scores put the higher id first. An empty section is the single line
  `- (none)`.
- `forget(user_id, topic)` ignores surrounding space in `topic`, and ignores case on both sides:
  `"MET"` matches stored text `"Met"`. An empty topic removes nothing and returns 0. It removes:
  - every episode whose text contains the topic;
  - every fact whose text `<subject> <attribute>: <value>` contains the topic, or whose evidence
    cites a removed episode, because it was derived from something the user asked to forget. A
    removed fact takes its whole history with it;
  - every history entry of the facts that remain whose text contains the topic or whose evidence
    cites a removed episode.

  It returns how many items it removed, counting one for each episode, one for each fact and
  one for each history entry, including every entry a removed fact takes with it. Removing a fact
  that has two superseded values counts 3.
- `forget_user(user_id)` deletes the user's entry from `data`; it returns `True` if there was one.

### `policy.py`

- `apply_policy(classifier, store, user_id, turn)` is the write policy exactly as in the write-policy
  exercise: one classifier call with the turn as the only user message; a JSON reply (a Markdown
  fence is allowed) that must have a boolean `remember`; `false` is `"skipped"`; a `sensitive` that
  is `true` is `"withheld"`; `kind` `"fact"` needs non-empty `subject`, `attribute` and `value` and
  calls `store.set_fact(user_id, ...)` and returns `"fact"`; `kind` `"episode"` needs a non-empty
  `summary`, takes an optional integer `importance` (default 5, clamped to 1 to 10), calls
  `store.add_episode(user_id, ...)` and returns `"episode"`. Strings are stripped. Anything unusable is `"invalid"`, writes
  nothing and does not raise.
- `reflect(reflector, store, user_id, threshold=25)` is reflection exactly as in the reflection
  exercise, over `store.episodes(user_id)`: return 0 without a call when the unreflected importance
  is below `threshold`; otherwise one call whose only message has a `[id] text` line per unreflected
  episode; keep the facts whose three strings are non-empty and whose `evidence` is a non-empty list
  of integers that all belong to that batch (de-duplicated, order kept) with
  `store.set_fact(user_id, ..., evidence)`; and, if the reply was a JSON array, call
  `store.mark_reflected` for the whole batch. An unusable reply leaves the batch unreflected and
  returns 0. Return the number of facts written.

### `assistant.py`: `Assistant.chat(user_id, message)`

1. Run `apply_policy` on the message first.
2. Run a tool loop with `self.model`, the starter's `SYSTEM` and `TOOLS`. The only message of the
   first request is the user's message: on every request, nothing from the store may be in the
   system prompt or any message except as a tool result. Answer every call with a `tool` message in call order, for the **current user** only:
   - `recall(query)`: `store.recall(user_id, query)`; a non-string query is `error: recall needs a string query`;
   - `forget(topic)`: `forgot <n>` with `n` from `store.forget`; a topic that is not a non-empty
     string is `error: forget needs a non-empty string topic`;
   - any other tool: exactly `error: unknown tool`.

   Make at most `max_steps` model calls, then raise `RuntimeError` mentioning `max_steps`.
3. When the model answers, run `reflect` with `reflect_threshold` and return the model's text.
   If the loop raised, do not reflect.

`delete_user(user_id)` forgets everything about a user and returns whether there was anything.
