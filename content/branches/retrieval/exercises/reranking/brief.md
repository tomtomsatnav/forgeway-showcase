# Reranking

First-stage retrieval has to be fast, so it compares a query against precomputed vectors and
makes do with a rough ordering. The right answer is often in the top 20 but not the top 3. A
**reranker** fixes that: it takes those candidates and scores each one *together with the query*,
which is slower but much sharper (cross-encoders and LLM judges are common rerankers).

The pattern is "retrieve wide, rerank narrow": fetch `n` candidates cheaply, score all of them
with the expensive scorer, keep the best `k`. If you only fetch `k` candidates the reranker has
nothing to improve.

```python
rerank_search(retrieve, scorer, "refund window", n=20, k=3)
```

Real scorers are model calls, so you should call them once per candidate and no more, and
equal scores should not shuffle results unpredictably.

## Your task

In `rerank.py` implement `rerank_search(retrieve, scorer, query, n=10, k=3)`:

- `retrieve(query, n)` returns up to `n` `Candidate(id, text)` objects, best first;
- `scorer(query, text)` returns a float, higher is better;
- score each candidate exactly once and return the top `k` `Candidate`s by score;
- candidates with equal scores keep the order the retriever gave them.
