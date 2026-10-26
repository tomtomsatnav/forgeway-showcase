# Ontology-guided extraction

Asking a model to "pull out the facts" gives you whatever it feels like: `works at`,
`employed_by`, `is a worker of`, a `Person` that is really a city. A graph built from that
cannot be queried, because the same idea has five spellings and the types are wrong.

An **ontology** fixes the vocabulary. It lists the entity types that may exist and, for every
relation, which type may be its subject (the **domain**) and which its object (the **range**).
You do two things with it:

1. Show it to the model, so most replies already fit.
2. Check every triple in the reply against it anyway. The model is a guesser, and a graph is
   only as trustworthy as the filter in front of it.

```python
ontology = {
    "types": ["Person", "Organisation", "City"],
    "relations": {
        "works_at": ["Person", "Organisation"],
        "based_in": ["Organisation", "City"],
    },
}
```

`("Ada", works_at, "Leeds")` is rejected: Leeds is a `City`, and `works_at` needs an
`Organisation`.

## Your task

Implement `extract(client, ontology, text)` in `extract.py`. It returns
`Extraction(triples, rejected)`.

**The request.** Call `client.complete` once with `max_tokens=2000` and:

- a system prompt that contains, each on its own line, `Entity types: ` followed by the types
  joined with `, `, and then one line per relation, in the ontology's order, in exactly the form
  `- works_at: Person -> Organisation`. Add whatever other instructions you like around them;
- exactly one user message whose content is `text`, unchanged.

**The reply.** The model is asked for a JSON array in which every item looks like this:

```json
{"subject": {"name": "Ada", "type": "Person"}, "predicate": "works_at",
 "object": {"name": "Initech", "type": "Organisation"}}
```

If the reply, once stripped of surrounding whitespace, starts and ends with a code fence
(three backticks), remove the opening line (with any language tag) and the closing fence before
parsing. A reply that is not valid JSON, or is JSON but not an array, raises `ValueError`.

**The checks.** An item is **valid** only if all of these hold:

- it is an object with `subject`, `predicate` and `object`;
- `subject` and `object` are objects whose `name` and `type` are strings, and each name is not
  empty once stripped of whitespace;
- the predicate is one of the ontology's relations;
- the subject's type equals that relation's domain and the object's type equals its range
  (exact, case-sensitive).

`Extraction.triples` holds a `Triple(subject, predicate, object)` of the **stripped names** for
each valid item, in reply order. A triple that appears again (after stripping) is kept once.
`Extraction.rejected` holds every invalid item exactly as it arrived in the reply, in order.
