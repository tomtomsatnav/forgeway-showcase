# Assembling a prompt under a budget

A prompt is built from many parts: rules, tool notes, retrieved documents, the user's profile, the
conversation so far. They rarely all fit. Which part gets cut when they do should be a decision
you made in advance, not something that happens to whichever part came last.

The standard answer is **priorities**. Each section says how much it matters, and the builder fills
the budget from the top: the most important sections first, whole where possible, and a cut only
where you allow one. Order is a separate question. Once you know what survives, it goes into the
prompt in the order *you* designed, not in priority order.

```text
budget 12   rules (p5, 6 tokens)   history (p2, 9 tokens)   profile (p4, 4 tokens)
visit:      rules fits -> 6 left   profile fits -> 2 left   history does not fit -> skipped
prompt:     rules, profile         (original order)
```

## Your task

In `assembly.py`, implement `assemble(sections, budget)` and `ask(client, sections, question,
budget)`. A `Section` has a `name`, a `text`, an integer `priority` (bigger matters more) and a
`truncatable` flag. Tokens are counted with `forgeway_kit.count_tokens`.

`assemble` returns the kept texts joined with `"\n\n"`, in the **original list order**. Decide
what is kept like this, with `remaining` starting at `budget`:

1. Visit the sections from the highest priority to the lowest. Sections with equal priority are
   visited in list order.
2. A section with no tokens (empty text) is never included.
3. If the whole text fits in `remaining`, keep it whole and reduce `remaining`.
4. Otherwise, if the section is `truncatable` and `remaining` is more than 0, keep the first
   `remaining` tokens of the text: cut straight after the end of the `remaining`-th token, keeping
   the original spacing and adding nothing. Then `remaining` is 0.
5. Otherwise skip the section and carry on down the list: a smaller section may still fit.

The result never has more than `budget` tokens (the `"\n\n"` separators cost nothing).

`ask` sends the assembled prompt as the **system prompt** and `question` as the single user
message, and returns the model's text. The budget covers everything sent, so the sections are
assembled with `budget - count_tokens(question)`. If the question alone is over the budget, raise
`ValueError`.
