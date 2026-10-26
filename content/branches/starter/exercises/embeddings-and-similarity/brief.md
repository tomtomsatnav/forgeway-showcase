# Embeddings and similarity search

An **embedding** turns text into a list of numbers (a vector) so that texts which are alike
land close together. That lets you search by similarity instead of exact keywords, and it is
the core of retrieval: find the documents most relevant to a question before you put them in a
prompt.

Closeness is usually measured by **cosine similarity**: 1.0 means the vectors point the same
way, around 0 means unrelated.

```python
vectors = embedder.embed(["reset my password", "refund policy"])
cosine_similarity(vectors[0], vectors[1])  # a small number: not alike
```

In these exercises you use `HashingEmbedder`, which only captures *word overlap*. It is
deterministic and needs no network, but "car" and "automobile" look unrelated to it. Real
embedding models capture meaning; the code you write here is the same.

## Your task

Implement `top_k(embedder, query, documents, k=3)` in `search.py`. Return the `k` documents
most similar to `query`, most similar first, as the original strings. If there are fewer than
`k` documents, return them all ranked.
