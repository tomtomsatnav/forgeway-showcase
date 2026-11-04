# An in-memory triple store

A knowledge graph stores facts as **triples**: `(subject, predicate, object)`. "Ada works at
Initech" is `("Ada", "works_at", "Initech")`. Because every fact has the same shape, one small
store can answer a whole family of questions by **pattern**: leave some parts as wildcards and
ask for everything that fits.

```python
store = TripleStore()
store.add("Ada", "works_at", "Initech")
store.add("Bo", "works_at", "Initech")
store.add("Ada", "lives_in", "Leeds")
store.match(predicate="works_at", obj="Initech")  # Ada's and Bo's triples
store.match(subject="Ada")  # Ada's two triples
store.match()  # everything
```

Graph databases add indexes, transactions and query languages, but this is the core contract.
The rest of the branch builds on it.

## Your task

Implement `TripleStore` in `triples.py`.

- `add(subject, predicate, obj)` stores a triple and returns `True`, or returns `False` if the
  identical triple is already stored. A store is a set: it never holds duplicates.
- `remove(subject, predicate, obj)` deletes a triple and returns `True`, or `False` if it was
  not there.
- `match(subject=None, predicate=None, obj=None)` returns a **new list** of `Triple`s whose parts
  equal every argument that is not `None`, in the order they were first added. Only `None` is
  a wildcard: an empty string `""` is a value like any other and matches only itself. Case matters:
  `"ada"` and `"Ada"` are different values.
- `len(store)` is the number of triples.

A triple that was removed and added again counts as newly added: it goes to the end.
