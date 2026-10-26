# Entity resolution

Text names the same thing in many ways: "Acme Corp.", "ACME Corporation" and "The Acme
Company, Ltd." are one company. If a graph stores each spelling as its own node, the facts about
Acme are scattered over three nodes and no traversal ever joins them. **Entity resolution** maps
every mention to one stable id before a fact is written.

Real systems use embeddings, blocking and model judgements. The foundation is simpler and
worth getting exactly right: a deterministic **normalisation** that makes harmless variants
identical, plus an **alias table** for the ones rules cannot guess ("IBM" is "International
Business Machines").

## `normalise(name)`

Apply these steps in this order:

1. Decompose with `unicodedata.normalize("NFKD", name)` and drop every character for which
   `unicodedata.combining(ch)` is non-zero (so `é` becomes `e`, and full-width `Ａ` becomes `A`).
2. Casefold the result (`str.casefold`).
3. Replace every character that is not alphanumeric (`str.isalnum()` is false) with a space,
   split on whitespace, and work with the list of tokens. Apostrophes, hyphens, dots, `&` and `_`
   are all separators.
4. If the first token is `the` and there is more than one token, remove it.
5. While there is more than one token and the **last** token is one of `inc`, `incorporated`,
   `ltd`, `limited`, `llc`, `plc`, `corp`, `corporation`, `co`, `company` or `gmbh`, remove it.
6. Join the tokens with single spaces.

A name with no tokens after step 3 (`""`, `"  "`, `"&&&"`) raises `ValueError`.

```python
normalise("The Acme Company, Ltd.")  # "acme"
normalise("Müller & Söhne GmbH")  # "muller sohne"
normalise("Co")  # "co"   (never remove the only token)
```

## Your task

Implement `normalise` and `EntityResolver` in `entities.py`.

`EntityResolver(aliases=None)` takes an optional dict of alias mention to target mention. Both
sides are normalised when the resolver is built.

- `resolve(mention)` returns the **entity id**: the normalised mention, after the alias table is
  applied **once**. If `"ibm"` aliases `"international business machines"`, then resolving "IBM"
  gives the target. Aliases are not followed a second time: with `A -> B` and `B -> C`, "A"
  resolves to `b`.
- It also remembers the mention. `surface_forms(entity_id)` returns the distinct mentions (exact
  strings, as passed in) that resolved to that id, in the order they were first seen. An unknown
  id gives `[]`.
