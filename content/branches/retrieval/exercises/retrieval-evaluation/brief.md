# Evaluating retrieval

"It feels better" is how retrieval regressions ship. Before changing a chunk size, an embedder or
a fusion constant, you need numbers from a small **labelled set**: queries paired with the ids of
the documents that should come back.

Two metrics cover most needs:

- **recall@k**: of the documents that *should* be retrieved, what fraction appear in the top `k`?
  It tells you whether the answer ever reaches the model.
- **MRR** (mean reciprocal rank): how high is the first correct result? A hit at rank 1 scores 1,
  rank 2 scores 0.5, rank 4 scores 0.25, no hit scores 0, averaged over all queries.

```python
recall_at_k(["d3", "d1", "d9"], {"d1", "d2"}, k=3)  # 0.5: found d1, missed d2
reciprocal_rank(["d3", "d1", "d9"], {"d1", "d2"})  # 0.5: first hit is at rank 2
```

A common slip is averaging MRR only over the queries that found something, which flatters a
retriever that fails often.

## Your task

In `evaluate.py` implement:

- `recall_at_k(retrieved, relevant, k)` for one query (`relevant` is a set; 0.0 if it is empty);
- `reciprocal_rank(retrieved, relevant)` for one query;
- `evaluate(retriever, labelled, k)`: `retriever(query)` returns a ranked id list, `labelled` is a list of
  `(query, relevant_set)`; return `Metrics(recall, mrr)`, each averaged over all queries;
- `best_retriever(retrievers, labelled, k)`: `retrievers` is a dict of name to retriever; return the
  name with the highest mean recall@k, then highest MRR, then earliest in the dict.
