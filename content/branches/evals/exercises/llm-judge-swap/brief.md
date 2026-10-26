# A judge that cannot be fooled by order

To compare two answers, you can ask a model: "which is better under this rubric?" That is
**LLM-as-judge**, and it has a well-known flaw. Judges are **position-biased**: when two answers
are close in quality, many prefer whichever came first (some prefer the last). If you ask once,
your verdict depends on the order you happened to list them in, not on quality.

The fix is mechanical. Ask twice with the order **swapped**, translate both replies back to the
answers they refer to, and **aggregate**. A real preference survives the swap. A positional one
does not, and it becomes a tie.

```text
ordering 1:  Response 1 = A, Response 2 = B   reply "1"  ──► A won
ordering 2:  Response 1 = B, Response 2 = A   reply "1"  ──► B won     inconsistent ──► tie
```

Your tests use a judge whose preferences are seeded and whose position bias is real. Like a real
judge it is also sometimes inconsistent, so a single-order implementation gets some pairs wrong
in a way you cannot predict from the text.

## Your task

Implement `judge_pair` and `compare_systems` in `judge.py`.

`judge_pair(client, question, answer_a, answer_b, rubric)` makes **exactly two** requests. Each is
a fresh conversation with one `user` message that contains the rubric, the question and both
answers, with the responses labelled `Response 1` and `Response 2` and a final instruction to reply
with `1` or `2`. In the first request `answer_a` comes first; in the second `answer_b` does.
Lay each request out in this order: the label `Response 1`, the first answer, the label
`Response 2`, the second answer, then the instruction. You may mention the labels earlier too
(in an introduction, say); the label that counts is the last one before each answer.

A reply is read as follows: take its first whitespace-separated word, remove any trailing `.`, `,`,
`:`, `;` or `)`, and it must be exactly `1` or `2`; anything else raises `ValueError`. Map the
first reply `1` to A and `2` to B. Map the second reply `1` to B and `2` to A. The result is:

- `"A"` if A won both orderings;
- `"B"` if B won both orderings;
- `"tie"` in every other case.

`compare_systems(client, items, rubric)` takes `items`, a list of `(question, answer_a, answer_b)`
tuples, and judges each with `judge_pair`. It returns
`{"a_wins": ..., "b_wins": ..., "ties": ..., "a_score": ...}`, where `a_score` is
`(a_wins + 0.5 * ties) / len(items)`. Raise `ValueError` for an empty list.
