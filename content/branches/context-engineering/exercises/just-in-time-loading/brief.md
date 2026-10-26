# Loading context just in time

The obvious way to give a model knowledge is to put it all in the prompt. It works until the
knowledge base is bigger than the window, and it is wasteful long before that: you pay for every
document on every call, whether or not the question needed it, and a long prompt is harder for a
model to use well.

**Just-in-time loading** turns this around. The prompt holds a cheap *map*, the catalogue of what
exists, and the model fetches what it needs with a tool call. Most documents are never read. A
person does the same: they look at the table of contents, not the whole book.

```text
system:  - kb-3f1a: Harbour tariffs
         - kb-9c20: Courier insurance      ← titles only, a few tokens each
model:   load_document("kb-3f1a")
tool:    <the full text of that one document>
```

A model can still be greedy, or be talked into loading everything, so the loading is **budgeted**:
you decide how many tokens of documents one run may pull in, and the tool refuses the rest. The
catalogue records each document's size, so a refusal costs nothing: you do not read a document
just to find out it was too big.

## Your task

In `jit.py`, implement `answer_jit(client, question, catalogue, read, budget, max_steps=8)`.
`catalogue` is a list of `Entry(id, title, tokens)`; `read(doc_id)` returns a document's text. The
starter gives you `LOAD`, the `load_document` tool (one required string argument, `doc_id`).

- Offer only `LOAD`. The **system prompt** lists every catalogue entry on its own line as
  `- {id}: {title}` (after an introduction of at most 60 tokens, if you like) and contains no document text. The question
  is the first user message.
- Loop: one model call per step, returning the model's text as soon as it makes no tool call.
  Answer every call, in order, with a `tool` message:
  - `doc_id` missing, or not a non-empty string: `error: doc_id is required`
  - an id not in the catalogue: `error: unknown document {doc_id}`
  - an id already loaded in this run: `already loaded: {doc_id}` (the text is not sent again)
  - an entry whose `tokens` is more than what is left of `budget` (`budget` minus the `tokens`
    of everything loaded so far): `error: over budget: {tokens} tokens needed, {left} left`. Do
    not call `read`.
  - otherwise the text from `read(doc_id)`, and the entry's `tokens` is used up.
- The budget is the catalogue's `tokens`, not a recount. A refused document stays refused, but a
  smaller one later in the same batch may still fit.
- After `max_steps` model calls without a final reply, raise `RuntimeError` mentioning `max_steps`.
