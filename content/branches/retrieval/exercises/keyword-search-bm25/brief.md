# Keyword search with BM25

Embeddings are good at "roughly about this", and poor at exact strings: error codes, product SKUs,
function names, people's surnames. Keyword search is the opposite. **BM25** is the classic scoring
function behind it (and behind Elasticsearch, Lucene and SQLite's FTS5), and it is the other half
of the hybrid search you will build next.

For each query term it rewards documents that contain the term, with three adjustments:

- **idf**: a term in few documents is worth more than one in most of them;
- **saturation**: the tenth occurrence of a word adds much less than the first;
- **length normalisation**: a long document mentions everything eventually, so it is discounted.

```text
idf   = ln(1 + (N - df + 0.5) / (df + 0.5))
score = sum over distinct query terms of
        idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avgdl))
```

`N` is the number of documents, `df` the number containing the term, `tf` its count in this
document, `dl` the document's length in tokens and `avgdl` the average length. Use `k1=1.5`, `b=0.75`.

## Your task

Implement `BM25(documents, k1=1.5, b=0.75)` in `bm25.py`, where `documents` is a dict of id to text.
`search(query, k=3)` returns up to `k` `(id, score)` pairs, highest score first (ties keep dictionary
order), including only documents whose score is above zero. Tokenise by lower-casing and taking runs
of letters and digits.
