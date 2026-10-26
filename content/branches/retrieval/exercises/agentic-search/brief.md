# Agentic search

Classic RAG retrieves once, with the user's own words, and hopes. Many questions need more: the
first search finds a document that mentions the *name* of the thing you need ("the refit was
called Operation Keel") and only a second search, for that name, finds the answer. A person
would simply search again. **Agentic search** gives the model the same ability: instead of
being handed passages, it is handed a `search` tool and decides what to look for, how often, and
when it knows enough to answer.

```text
model: search("When did the Harbour Bridge reopen?")
tool:  [bridge-news] ... the project was renamed Operation Keel ...      (no date)
model: search("Operation Keel completed", k=5)
tool:  [keel-2] Operation Keel completed in March 2022 ...
model: "It reopened in March 2022 [keel-2]."
```

It is more flexible than a fixed pipeline and costs more: several model calls, and you must
bound them. It also raises the stakes for citations. A model working over many tool results can
cite a document it never saw, or one it only half remembers, so your code must check every
citation against what was really retrieved. This builds on the loop from the tool-use exercise
and the citation parsing from grounded answers.

## Your task

Implement `agentic_answer(client, store, question, max_steps=6, k=3)` in `agent.py`.
`store.search(query, n)` returns hits with `.id` and `.text`.

- Offer the model one tool named `search` with a required string `query` and an optional
  integer `k` (default to the `k` argument when the model omits it).
- Answer each `search` call with a tool message listing the hits, one per line, as
  `[id] text`. With no hits, say so. A bad call (for example, no `query`) gets an
  `error: ...` result rather than an exception.
- Loop until the model replies without asking for a tool, using at most `max_steps` model
  calls; if it is still searching after the last, raise `RuntimeError` mentioning `max_steps`.
- Return `AgenticAnswer(text, sources, queries)`: the model's final text, the ids it cited that
  were actually retrieved by any search (in order of first citation, no duplicates; markers like
  `[ghost-9]` for documents never retrieved are dropped), and the list of queries searched.
- Tell the model, in the system prompt, to search as many times as it needs, to answer only from
  what the searches returned and to cite ids like `[doc-id]`. The question is the first user message.
