# Metadata filtering

Real corpora are not one flat pool. A support bot must only see the documents the current
customer's plan allows; a legal search is limited to one jurisdiction; a "latest news" query is
restricted to this year. That is what **metadata filters** are for, and they are a correctness and
security requirement as much as a quality feature.

Where you apply the filter matters. If you retrieve the top 3 overall and *then* drop the ones
that do not match, a popular but out-of-scope document can crowd the right ones out and you are
left with nothing. Filter first, then rank within what remains.

```python
store.search("refund policy", k=2, where={"audience": "customer"})
store.search("refund policy", k=2, where={"lang": {"in": ["en", "fr"]}})
```

## Your task

The `VectorStore` in `store.py` already embeds and scores entries. Implement
`search(query, k=3, where=None)`:

- `where` maps a metadata field to either a plain value (equality) or `{"in": [values]}`;
- every condition must hold; an entry lacking the field does not match;
- the filter is applied **before** taking the top `k`;
- with `where=None` or `{}` nothing is filtered. Return `Hit`s, most similar first.
