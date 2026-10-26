# Index the help centre

This guided project builds one codebase over five milestones: a support copilot for Tallybook, a
small accounting product. By the end it answers customers from the help centre, remembers each
customer, assembles a careful prompt for every turn, guards what goes in and out, and ships only
when an eval suite says it may. Each milestone opens with your own code from the one before.

Everything starts with the help centre. Its articles are not tidy documents: a setup guide has
nested headings, numbered steps and shell snippets whose comment lines start with `#`, and some
articles apply to one pricing plan while others apply to all three. If the chunker cuts a shell
snippet in half, or mistakes `# export from the old system` for a heading, the copilot will quote
half a command. If the filter cannot read a list of plans, a Starter customer gets the Enterprise
limits.

You have done most of this before, in **Structure-aware chunking**, **Keyword search with BM25**,
**Hybrid search with reciprocal rank fusion** and **Metadata filtering**, and you put it together in
**A production RAG service**. This knowledge base asks for more in three places: fenced blocks,
list-valued metadata, and articles that change.

```python
kb = KnowledgeBase(HashingEmbedder(128))
for article in articles:
    kb.upsert(article)
kb.search("error A957 on import", k=5, where={"audience": "public", "plans": "team"})
```

## Your task

### `chunking.py`: `chunk_article(article, max_chars=300) -> list[Chunk]`

An article is a dict with `id`, `title`, `url`, `meta` (a dict) and `body` (markdown).

- A **fenced block** starts at a line that begins with three backticks (```` ``` ````, a language
  name may follow) and ends at the next line that begins with three backticks, or at the end of
  the article if none does. Its lines, fence lines included, are kept exactly as written and
  joined with `"\n"`. Inside a fenced block nothing is a heading and a blank line does not end it.
- Outside fenced blocks, a **heading** is a line of 1 to 6 `#` characters followed by whitespace
  and its text (trimmed). Heading lines are not part of any chunk, and they split the body into
  sections.
- Outside fenced blocks, **paragraphs** are separated by blank lines (empty or only whitespace).
  A paragraph's lines are joined with `"\n"` and trimmed.
- Within a section, consecutive paragraphs and fenced blocks pack into one chunk, joined by
  `"\n\n"`, while the chunk stays at most `max_chars` characters. A paragraph longer than
  `max_chars` splits into runs of whole words joined by single spaces, each at most `max_chars`,
  which then pack as normal. A fenced block is never split: one longer than `max_chars` is a chunk
  on its own.
- Chunks never span two sections, and a section with no body gives no chunk.

Each `Chunk(id, text, metadata)` has:

- `id`: `"<article id>#<n>"`, counting the article's chunks from 1 in order;
- `text`: the chunk body, without its heading line;
- `metadata`: the article's `meta`, plus `article` (the article id), `title`, `section` and `url`.

`section` is the **heading path**: every open heading, outermost first, joined with `" > "`, such as
`"Troubleshooting > Error A957"`. A heading closes the open headings at its own level and deeper.
`section` is `""` before the first heading.

`url` links to the chunk's place in the article: the article's `url`, then `#` and the anchor of
the innermost open heading. An anchor is the heading in lower case with every run of characters
other than `a`-`z` and `0`-`9` replaced by one `-`, and no `-` at either end, so `"Real one!"`
becomes `real-one`. With no heading (or an empty anchor) the `url` is the article's own.

### `kb.py`: `KnowledgeBase(embedder, *, depth=10, rrf_k=60, max_chars=300)`

- `upsert(article)` chunks the article with `max_chars` and stores it, replacing every chunk of any
  earlier version with the same id. The new chunks go at the **end** of the knowledge base's
  order. It returns the number of chunks stored.
- `remove(article_id)` drops the article and its chunks and returns `True`, or `False` if it was
  not stored. `article(article_id)` returns the article dict as last upserted, or `None`.
- `search(query, k=5, where=None)` returns the best `k` chunks, as in the RAG service:
  1. Both rankings index `f"{title} {section} {text}"`.
  2. `where` maps a metadata field to a value, or to `{"in": [values]}`. Every condition must hold,
     and a missing field never matches. When the stored value is a **list**, such as `plans`, the
     condition holds if any item of the list matches. Apply `where` inside each ranking, before
     that ranking is cut to `depth`.
  3. The vector ranking is the cosine similarity of `embedder` vectors, with every chunk that
     passes the filter ranked. The keyword ranking is BM25 over lower-cased runs of letters and
     digits, each distinct query term counted once:
     `sum of idf * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / avgdl))`, with `k1=1.5`, `b=0.75`
     and `idf = ln(1 + (N - df + 0.5) / (df + 0.5))`. `N`, `df` and `avgdl` describe the whole
     knowledge base as it is now, not the chunks the filter keeps. Only scores above zero are
     ranked. In both rankings, ties keep the knowledge base's order.
  4. Fuse the vector ranking, then the keyword ranking, by reciprocal rank,
     `1 / (rrf_k + rank)` summed, ties going to whichever appeared first, and return the top `k`.
     An empty knowledge base returns `[]`.
