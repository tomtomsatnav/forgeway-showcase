# Hybrid search with reciprocal rank fusion

Vector search and keyword search fail in opposite ways. Vector search is forgiving about
wording but can bury an exact identifier ("ERR-4021") under vaguely related text. Keyword search
nails the exact string but misses "refunded" when the document says "refund". Running both and
merging the results is **hybrid search**, and it is the default for serious retrieval systems.

The merging problem: a cosine score of 0.31 and a BM25 score of 14.2 mean different things. Don't
try to add them. **Reciprocal rank fusion (RRF)** ignores scores and uses only positions: each ranking
gives an item `1 / (k + rank)` points (rank counts from 1, and `k` is conventionally 60), and
the points are summed.

```python
reciprocal_rank_fusion([["a", "b", "c"], ["b", "d"]])
# b: 1/62 + 1/61 ≈ 0.0325,  a: 1/61 ≈ 0.0164,  d: 1/62,  c: 1/63  ->  b, a, d, c
```

An item both rankings like beats an item only one of them puts first. The large `k` keeps any one
list from dominating.

## Your task

In `hybrid.py` implement:

- `reciprocal_rank_fusion(rankings, k=60)`: `rankings` is a list of ranked id lists; return a
  list of `(id, score)` sorted best first. Ties are broken by first appearance (earlier ranking,
  then earlier position).
- `hybrid_search(query, retrievers, k=3, rrf_k=60, depth=20)`: each retriever is a function
  `retriever(query, n) -> list[id]`. Ask each for `depth` results, fuse them, and return the ids of
  the top `k`.
