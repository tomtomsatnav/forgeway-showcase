# Hybrid graph and vector retrieval

Vector search finds text that *sounds like* the question. It misses text that is *connected to*
the answer but shares no words with the question. "Who audits the company that Ada founded?"
matches the passage about Ada's company, not the passage about its auditor, which never mentions
Ada. A knowledge graph knows that the two passages are linked through the company.

**Graph-augmented retrieval** combines them:

1. Use vector search to find the chunks that match the question (the **seeds**).
2. Look at the entities those chunks mention and follow one edge from each in the knowledge graph.
3. Collect the chunks that mention the entities you reached.
4. Fuse the two ranked lists into one.

```text
question ──vectors──► chunk about Ada's company  (mentions: Initech)
                              │ Initech ◄─audits─ Sable & Co
                              ▼
                      chunk about Sable & Co      (shares no words with the question)
```

## Your task

Implement `hybrid_search(query, chunks, mentions, edges, embedder, k=3, vector_k=3)` in
`hybrid.py`. It returns a list of `(chunk_id, score)` pairs, best first.

- `chunks` maps chunk id to text.
- `mentions` maps chunk id to the list of entity names it mentions (a name may appear more than
  once). A chunk missing from the dict mentions nothing.
- `edges` is a list of `(subject, predicate, object)` triples between entities.
- `embedder` has `embed(texts)`, which returns one vector per text.

The procedure is fixed:

1. **Vector list.** Rank every chunk by the cosine similarity of its embedding to the query's,
   highest first, equal scores by chunk id (ascending). Keep the first `vector_k`, whatever their
   scores. A chunk's **rank** is its 1-based position in this list.
2. **Seeds.** The entities mentioned by the chunks in the vector list.
3. **Expansion.** Every entity joined by an edge, in either direction, to a seed, except the
   seeds themselves. One edge only: do not follow edges from the expansion.
4. **Graph list.** Every chunk that mentions at least one expansion entity, ordered by how many
   distinct expansion entities it mentions (most first), equal counts by chunk id. Its rank is
   its 1-based position in this list.
5. **Fusion** (reciprocal rank fusion). A chunk's score is the sum of `1 / (60 + rank)` over the
   lists it appears in. Only chunks in at least one list can be returned. Sort by score, highest
   first, equal scores by chunk id, and return the first `k` as `(chunk_id, score)` with the
   score as an unrounded float.

`cosine_similarity` in `forgeway_kit` computes step 1's similarity.
