# Exact, fuzzy and set metrics

"It seems better" is not an evaluation. Before you can compare two prompts, two models or two
versions of the same system, you need a **metric**: a function that turns an answer and a
reference into a number, the same way every time. Different questions need different metrics:

- **Exact match** for answers with one right form ("Paris").
- **Token F1** for short free text, where a few extra or missing words should cost a little,
  not everything.
- **Set metrics** for answers that are a collection (the documents retrieved, the tools called),
  where order does not matter.

An **eval harness** is the loop around them: run the system on every case in a fixed set, score
each answer, and report the scores and their mean.

```text
cases ──► system ──► answers ──► metric(answer, expected) ──► scores ──► mean
```

## Your task

Implement these in `metrics.py`. Every rule below is graded exactly.

- `normalise(text)`: lower-case it (`str.lower()`), delete every character in
  `string.punctuation`, split on whitespace, drop the words `a`, `an` and `the`, and join what is
  left with single spaces.
- `exact_match(prediction, reference)`: `1.0` if the two normalised strings are equal, else `0.0`.
- `token_f1(prediction, reference)`: split both normalised strings into words. `common` is the
  size of their multiset intersection (a word that appears 2 times in one and 3 in the other
  counts 2). If both are empty the score is `1.0`. If `common` is 0 the score is `0.0`. Otherwise
  `precision = common / len(prediction words)`, `recall = common / len(reference words)` and
  `F1 = 2 * precision * recall / (precision + recall)`.
- `set_scores(predicted, expected)`: the two lists are turned into sets, so repeats are ignored.
  Return `{"precision": ..., "recall": ..., "f1": ...}` where `precision = |P ∩ E| / |P|` and
  `recall = |P ∩ E| / |E|`, and F1 is as above. If both sets are empty, all three are `1.0`.
  Otherwise an empty `P` gives precision `0.0`, an empty `E` gives recall `0.0`, and F1 is `0.0`
  whenever `precision + recall` is 0.
- `evaluate(client, cases, metric, system=None)`: `cases` is a list of
  `{"input": str, "expected": str}`. For each case, in order, make one `client.complete` call whose
  only message is the case's input as a `user` message (a fresh conversation every time), passing
  `system`. Score the reply text with `metric(prediction, expected)`. Return
  `{"scores": [...], "mean": ..., "failures": [...]}`, where `failures` holds the index of every
  case that scored below `1.0`. With no cases, make no calls and return `mean` `0.0`.
