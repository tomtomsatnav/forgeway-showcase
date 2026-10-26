# An in-memory vector store

A vector store holds `(id, text, vector)` triples and answers one question quickly: which stored
texts are closest to this query? Production systems use approximate indexes to do it over
millions of vectors, but the contract is exactly what you will build: embed on the way in,
embed the query on the way out, rank by similarity.

Similarity is usually **cosine**: the angle between two vectors, ignoring their length. A long
document that repeats a word ten times should not beat a short one that matches the query
perfectly, and raw dot products let it. Many embedders return unit-length vectors, which hides
the difference until you swap in one that does not.

```python
store = VectorStore(HashingEmbedder())
store.add("a", "refund policy for annual plans", {"team": "billing"})
store.search("annual refund", k=1)  # [Hit(id='a', text=..., score=0.6..., metadata={...})]
```

The `HashingEmbedder` in `forgeway_kit` is deterministic and **lexical**: it scores shared words
and word fragments. It does not understand meaning, and the checks are designed around that.

## Your task

Implement `VectorStore` in `store.py`. `add(id, text, metadata=None)` stores an entry (re-adding an id replaces
it). `search(query, k=3)` returns up to `k` `Hit` objects ordered by cosine similarity, highest
first, with equal scores keeping insertion order. An empty store returns `[]`.
