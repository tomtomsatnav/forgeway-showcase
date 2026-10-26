# Self-checking RAG

A grounded prompt reduces hallucination but does not remove it. If retrieval missed the key
passage, the model may still produce a fluent answer from memory. A **verification step** catches
many of these: after answering, ask the model (in a separate call, with the sources and the
answer in front of it) whether every claim is supported. If not, the usual cause is that
retrieval was too narrow, so try again with a larger `k`.

```text
retrieve(k=3) -> answer -> verify -> UNSUPPORTED
retrieve(k=8) -> answer -> verify -> SUPPORTED     -> return it, supported=True
```

Two production details matter. Verdicts are model text, so parse them carefully (note that
"UNSUPPORTED" contains "SUPPORTED"). And the loop must be bounded: one retry, then return what you
have with `supported=False`, so a hard question costs at most two retrievals and four model calls.
Callers can then decide to show a caveat or escalate.

## Your task

Implement `answer_with_check(client, store, question, k=3, retry_k=8)` in `selfcheck.py`.
`store.search(question, n)` returns hits with `.id` and `.text`. Each attempt is:

1. retrieve, then answer with numbered sources `[1] ...` and a request to cite `[n]`;
2. in a **separate** model call, show the sources and the answer and ask for exactly `SUPPORTED`
   or `UNSUPPORTED`.

If the verdict is SUPPORTED, return it. Otherwise run one more attempt with `retry_k` and return
that result whatever its verdict. Return `CheckedAnswer(text, sources, supported)`; `sources`
are the ids cited (in order of first citation, no duplicates, ignoring invalid numbers). If a
retrieval returns no hits, skip the model for that attempt and treat it as unsupported with
text "I don't know".
