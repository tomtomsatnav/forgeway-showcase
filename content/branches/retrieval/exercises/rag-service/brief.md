# A production RAG service

Every exercise so far built one part and handed it a tidy input. A real service has to make the
parts agree with each other: the chunker decides what the filters can see, the filters decide what
the reranker scores, the reranker decides what the model reads, and the model's answer has to be
traced back to a document a person can open. Your earlier solutions are the right ingredients, but
pasted side by side they will not pass: each one was written for a simpler contract, and this
service asks more of several of them (nested headings, context for the reranker, a verdict that
only the verifier gives).

You are building the service for a small company's product handbooks. Each product has a public
handbook, a partner sheet of fault codes and an internal staff note that must never reach a
customer. Users ask questions, sometimes as follow-ups ("does it cover repairs?"), and expect an
answer with sources.

```python
chunks = chunk_documents(docs)
retriever = Retriever(chunks, embedder, scorer=judge)
service = RagService(client, retriever, k=3, retry_k=6, source_budget=300)
reply = service.ask("Does it cover repairs?", history, where={"audience": "public"})
reply.text, reply.citations, reply.supported, reply.query
```

## Your task

Work in three files. Each starts with its signatures and dataclasses.

### `ingest.py`: `chunk_documents(docs, max_chars=240) -> list[Chunk]`

A document is a dict with `id`, `title`, `meta` (a dict) and `body` (markdown). Chunk it as in
structure-aware chunking:

- a heading is a line of 1 to 6 `#` characters followed by whitespace and its text; heading lines
  are not part of any chunk, and they split the body into sections;
- paragraphs are separated by blank lines (empty or only whitespace);
- within a section, consecutive paragraphs pack into one chunk, joined by `"\n\n"`, while the
  chunk stays at most `max_chars` characters;
- a paragraph longer than `max_chars` splits into runs of whole words joined by single spaces,
  each at most `max_chars`, and those runs then pack as normal;
- chunks never span two sections, and a section with no body gives no chunk.

Each `Chunk(id, text, metadata)` has:

- `id`: `"<document id>#<n>"`, counting that document's chunks from 1 in order;
- `text`: the chunk body, without its heading line;
- `metadata`: the document's `meta`, plus `doc` (the document id), `title` and `heading`.

Handbooks nest their headings, and `### Power` means little without the `## Faults` above it, so
`heading` is the **heading path**: every open heading, outermost first, joined with `" > "`, such
as `"Faults > Power"`. A heading closes the open headings at its own level and deeper, so a `##`
after `## Faults > ### Power` gives a path with just the new heading. `heading` is `""` before the
first heading.

### `retrieval.py`: `Retriever(chunks, embedder, *, scorer=None, depth=12, pool=8, rrf_k=60)`

`search(query, k=3, where=None)` returns the best `k` chunks:

1. **Index text.** Both rankings index `f"{title} {heading} {text}"`, not the bare body.
2. **Filter.** `where` maps a metadata field to a value, or to `{"in": [values]}`. Every condition
   must hold (`{"audience": "public", "product": "Orbit-3"}` means both), and a missing field never
   matches. Apply it inside **each** ranking, before that ranking is cut to `depth`.
3. **Two rankings.** Vector search (cosine similarity of `embedder` vectors) and BM25. The vector
   ranking has no minimum score: every chunk that passes the filter is ranked. BM25 tokens are
   lower-cased runs of letters and digits, each distinct query term counts once, and a chunk's
   score is

   `sum over query terms of idf * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / avgdl))`

   with `k1=1.5`, `b=0.75`, `f` the term's count in the chunk, `dl` the chunk's token count and
   `idf = ln(1 + (N - df + 0.5) / (df + 0.5))`. `N`, `df` and `avgdl` are taken over the **whole
   corpus**, not over the chunks the filter keeps: a filter decides which chunks may be returned,
   not how rare a word is. Only scores above zero are ranked. In both rankings, ties keep the
   chunks' original order.
4. **Fuse** the vector ranking, then the keyword ranking, with reciprocal rank fusion; ties go to
   whichever appeared first.
5. **Rerank.** Without a `scorer`, return the top `k` of the fused list. With one, score the top
   `max(pool, k)` fused chunks, each exactly once, and return the best `k` by score, highest
   first; equal scores keep their fused order. The reranker needs the same context as the
   rankings, so call it as `scorer(query, f"{title} {heading} {text}")`, not with the bare body.

### `service.py`: `RagService(client, retriever, *, k=3, retry_k=6, source_budget=300)`

`ask(question, history=(), where=None)` returns `Reply(text, citations, supported, query)`:

1. **Rewrite.** With a non-empty `history` (a list of `Message`s), make one model call that sees the
   whole conversation, in order, and the question (put them in whichever order you like). The
   search query is the first non-empty line of its reply, trimmed and without surrounding `"` or
   `'` quotes; if that leaves nothing, search the question. With no history the query is the
   question and there is no call. Rewrite once per `ask`.
2. **Attempt** with `k`: call `retriever.search(query, k, where)`, then keep sources in order while
   their lines fit the budget. A source is one line, `[n] title > heading: text` (just `[n] title: text`
   when the heading is empty), numbered from 1, with the text's whitespace collapsed to single spaces.
   The budget is the sum of `count_tokens(line)`; stop at the first line that would go over it.
   No sources left means no model call: the attempt is unsupported, with the text `I don't know`.
3. **Answer** with one call: the sources and the user's own question as typed, and a system prompt
   that asks for answers from the sources only, citing them by number, like `[1]` (any wording
   that asks the model to cite will do).
4. **Verify** with a second call that shows the same numbered sources and the answer, and asks for
   `SUPPORTED` or `UNSUPPORTED`. That reply is the verdict: trimmed and case-insensitive, the
   answer is supported only if the reply starts with `SUPPORTED`. Do not second-guess it by
   comparing the answer with the sources yourself; the verifier is the judge.
5. **Retry** once if unsupported: repeat the attempt with `retry_k`, the same query, the same `where`
   and the same budget. Return the second attempt whatever its verdict.
6. **Reply.** `text` is the model's answer unchanged. `citations` has one
   `Citation(chunk_id, doc, title, heading)` per distinct valid `[n]` marker, in order of first
   citation, taken from the cited chunk's metadata; markers that match no shown source are ignored.
   `query` is the query that was searched.

Internal notes must never reach the model or a citation when the caller filters them out.
