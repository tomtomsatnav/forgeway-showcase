# Context provenance and citation

A prompt assembled from many sources is a blender. A paragraph from a policy page, a row from a
tool, a note from a previous conversation: once they are text in one prompt, nothing says where
each came from. Then an answer cannot be checked, a wrong fact cannot be traced to the source
that planted it, and a user cannot be shown "this came from page 4 of the handbook".

**Provenance** is the habit of keeping that link. Every piece of context carries its origin and
a reference, and the prompt gives each piece a short label the model can cite. When the answer
comes back, your code, not the model, turns the labels back into sources:

```text
prompt:  [P1] Refunds are accepted within 45 days.        ← handbook.md
         [P2] Gift cards cannot be refunded.              ← tool: policy_lookup
model:   "You have 45 days [P1]."
result:  text + citations = [handbook.md]
```

A model can cite a label that does not exist, or write one in a slightly different shape, so
resolving citations is a validation step, as it was for retrieved documents.

## Your task

In `provenance.py`, implement `answer_with_sources(client, question, pieces)`. A `Piece` has
`text` (one line), `origin` (for example `"retrieval"` or `"tool"`) and `ref` (a URL, file or
call id). The starter gives you `Piece` and `Reply`.

- **Merge duplicates.** Pieces that are equal in all three fields count once, at the position of
  their first occurrence. Pieces with the same text but a different `origin` or `ref` stay
  separate: they are two sources.
- **Label** the remaining pieces `P1`, `P2`, ... in order.
- Send one **user** message: a line `[P1] text` for each piece, then a blank line, then
  `Question: ` followed by the question. With no pieces the message is only the `Question:` line.
  Any system prompt will do.
- **Resolve citations** in the reply text. A citation is a label in square brackets, `[P2]`, or
  several separated by commas, `[P1, P3]` (spaces around the commas are allowed, as in `[P1 , P3]`; a space just
  inside a bracket, as in `[ P1 ]`, or inside a label, as in `P 1`, makes it not a citation). Labels
  are case-sensitive and must be exactly `P` and a number with no leading
  zeros. Collect the pieces cited, in the order they are first cited, with no repeats, and ignore
  any label that is not one you gave out.
- Return `Reply(text, citations, grounded)`: the model's text unchanged, the cited `Piece`s, and
  `grounded`, true when at least one valid citation was found.
