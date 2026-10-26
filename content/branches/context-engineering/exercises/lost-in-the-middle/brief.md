# Ordering context against "lost in the middle"

Long-context models do not read every position equally. In many studies, facts at the start and
at the end of a long prompt are used reliably, while facts buried in the middle are used less
often. The effect varies by model and prompt, but the habit it teaches is sound: when
you retrieve ten passages, do not paste them in whatever order the search returned. **Put the
most relevant ones where they are least likely to be missed.**

The usual rule is to keep the best at the edges and let the weakest sit in the middle:

```text
ranked by score:  A  B  C  D  E  F        (A is the best)
placed in prompt: A  C  E  F  D  B        best first, second best last, and so on inwards
```

You will see that the placement is graded the way the model experiences it: by what order the
chunks reached the prompt, and by a model that only attends to the two ends.

## Your task

In `ordering.py`, implement `place(chunks)` and `ask(client, question, chunks)`. A `Chunk` has an
`id`, a one-line `text` and a numeric `score` (bigger is more relevant).

`place` returns a new list (the input is not changed), using this rule:

1. Rank the chunks by score, highest first. Equal scores keep their original relative order.
2. Deal the ranks out alternately: ranks 0, 2, 4... go on the **front** in rank order; ranks 1, 3,
   5... go on the **back**.
3. The result is the front list followed by the back list **reversed**. So the best chunk comes
   first, the second best comes last, the third best is second, the fourth best is second to last,
   and the weakest end up in the middle.

`ask` sends one **user** message and returns the model's text. The message is the placed chunks,
one per line as `[id] text`, then a blank line, then `Question: ` followed by the question. The
question always goes last. With no chunks, the message is only the `Question:` line.
