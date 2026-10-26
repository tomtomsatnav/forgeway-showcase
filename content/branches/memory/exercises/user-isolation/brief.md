# Per-user isolation and deletion

The moment an assistant serves more than one person, memory becomes a privacy boundary. One bug
and Priya's allergy shows up in a prompt written for Tom. The usual cause is not an exotic attack:
it is a shared index, a search that ranks everything and filters later, or a prompt built from "the
top results" without asking whose they are. Because the model will happily repeat anything in its
prompt, a leak into a prompt is a leak to the user.

Deletion is the other half. When someone asks to be forgotten (a legal right under GDPR, and plain
good manners), "deleted" must mean gone from **every** place the memory lives. A real store keeps
the text in one table, a keyword index and a vector index. Delete from the table only, and the
keyword index still holds the words and the vector index still holds a fingerprint of the text.

```text
records     m1 -> Record(user=alice, "alice takes oat milk")      <- delete here ...
word_index  oat -> {m1, m4}    milk -> {m1, m2}                   <- ... and here (m1 out of every set)
vectors     m1 -> [0.1, -0.3, ...]                                <- ... and here
```

## Your task

Implement `MemoryService` in `memory_service.py`. The starter declares its three indexes:
`records` (id to `Record`), `word_index` (word to a set of ids) and `vectors` (id to embedding).
`words(text)` gives the lower-cased `a-z0-9` words of a text.

- `add(user_id, text)` stores the text and returns its id `m1`, `m2`, and so on. One counter is shared
  by all users, and an id is never reused, even after a deletion. Put the record in all three
  indexes (the vector is `embedder.embed([text])[0]`).
- `search(user_id, query, k=3)` considers only that user's records which share at least one word
  with the query, found through `word_index`. Rank them by cosine similarity between the query's
  embedding and the record's stored vector, highest first, equal scores in the order they were
  added. Return the first `k` (`[]` if `k` is 0 or less). Filter by user **before** cutting to `k`.
- `forget(user_id, memory_id)` deletes one record and returns `True`. If the id does not exist, or
  belongs to another user, return `False` and change nothing. Deleting means removing the id from
  `records`, from every set in `word_index` (and removing any word whose set becomes empty), and
  from `vectors`. Nothing of the text may remain anywhere in the service, and a later `search`
  never returns it, even for a query that found it before. If you cache anything, clear it.
- `forget_user(user_id)` deletes all of a user's records the same way and returns how many.
- `answer(client, user_id, question)` makes one `client.complete` call with no tools, a system
  prompt of your own, and one `user` message of this exact form, using `search(user_id, question)`:

  ```text
  Memories:
  - <first memory text>
  - <second memory text>

  Question: <question>
  ```

  With no memories the list is the single line `(none)`. It returns the reply text.
