# Choosing few-shot examples by similarity

Showing a model a few worked examples is one of the strongest prompting tools there is. But
which examples? A fixed set of three is a compromise: right for some inputs, irrelevant for
others, and always taking up room. If you have a bank of labelled examples, you can do better
by picking, for each new input, the ones **most like it**. A support ticket about a refund is
best taught by other refund tickets.

The recipe is the retrieval you already know, pointed at examples instead of documents: embed the
pool, embed the new input, take the nearest few. The order then matters too. Models lean on what
they have just read, so the closest example goes **last**, right before the new input.

```text
pool ──embed──► nearest 3 to "where is my refund?"   (closest first: e1, e2, e3)
prompt:  user e3.input / assistant e3.label
         user e2.input / assistant e2.label
         user e1.input / assistant e1.label        ← closest, nearest the question
         user "where is my refund?"
```

Your tests use a model that copies the label of the last example it sees, which is a crude but
real tendency, so the answer shows whether the right example reached the prompt in the right
place.

## Your task

In `fewshot.py`, implement `select_examples(pool, query, k)` and `classify(client, pool, text,
k=3)`. An `Example` has an `input` and a `label`.

- `select_examples` embeds `query` and every `example.input` with `HashingEmbedder()` (its
  default settings) and ranks the pool by `cosine_similarity` to the query, highest first. Equal
  similarities keep pool order. It returns the first `k` examples, best match first. A `k` above
  the pool size returns the whole pool, ranked. `k < 1` raises `ValueError`.
- `classify` makes one model call and returns its text. The messages are, for each chosen
  example from the **least** to the **most** similar, a user message with its `input` and an
  assistant message with its `label`, followed by a user message with `text`. Any system prompt
  will do.
