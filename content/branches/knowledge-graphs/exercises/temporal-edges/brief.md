# Temporal edges

Facts stop being true. Ada works at Initech until March, then at Globex. A graph that overwrites
the old edge answers "where does Ada work?" correctly and "where did Ada work last year?"
wrongly; one that never removes anything answers "Initech and Globex" to both. The fix is to
give every edge a **validity interval** and, when something changes, to **close** the old edge
instead of deleting it.

```text
(Ada, works_at, Initech)   [2019-04-01, 2021-03-01)
(Ada, works_at, Globex)    [2021-03-01, ∞)
(Ada, knows, Bo)           [2020-06-15, ∞)         ← not replaced: you can know many people
```

Two ideas to hold on to:

- **Intervals are half-open.** `[from, to)` includes `from` and excludes `to`, so on the day a
  job changes, exactly one edge is valid.
- **Functional predicates** have one value at a time (`works_at`, `lives_in`). Asserting a new
  value ends the old one. Other predicates (`knows`) collect values.

Real documents arrive in any order, so the graph should be a function of *which facts were
asserted and when*, not of the order you heard about them.

Production temporal graphs, Graphiti for one, are **bitemporal**: each edge carries two timelines.
*Valid time* says when the fact was true in the world; *transaction time* says when the graph
learned it and when it retired it, so you can ask what the graph believed on a given day and audit
a correction. This exercise builds valid time, the half that answers questions about the world.

## Your task

Implement `TemporalGraph(functional=())` in `temporal.py`. `functional` is the set of functional
predicates.

**Dates** are strings in the form `YYYY-MM-DD`: four ASCII digits, a hyphen, two digits, a hyphen,
two digits, nothing else. They compare correctly as plain strings. Any other date raises
`ValueError`, in every method that takes a date. (The calendar is not checked.)

- `assert_fact(subject, predicate, obj, valid_from)` records that the triple became true on
  `valid_from`.
- `invalidate(subject, predicate, obj, at)` records that it stopped being true on `at`. It
  returns `True` if the fact was valid at `at` (and now ends there), and `False`, changing
  nothing, if it was not.
- `facts_at(date, subject=None, predicate=None, obj=None)` returns the `Fact`s valid on `date`
  (`valid_from <= date < valid_to`) that match every given part (`None` is a wildcard).
- `history(subject, predicate)` returns every interval of that subject and predicate, any
  object, closed or open.

A `Fact` is `(subject, predicate, object, valid_from, valid_to)`, where `valid_to` is `None` while
the fact is still valid. Both queries return facts ordered by `valid_from`, ties in the order
their starting assertions were made. An interval's starting assertion is the call that opens it
when the rules are replayed, so when a late re-assertion moves a start back, that late call is
the one that counts.

**The rules**, applied to the assertions and invalidations of one `(subject, predicate)` pair
**in date order** (on the same date, assertions come before invalidations, and calls come in the
order they were made):

1. Asserting a triple that is already open does nothing. Otherwise it opens an interval at the
   date, so asserting a triple again after it was invalidated starts a new interval.
2. If the predicate is functional, asserting an object first closes every other open object at
   that date. An interval that would start and end on the same date is dropped.
3. An invalidation closes the open interval of its triple at its date, if there is one.

Because the rules are applied in date order, asserting an older fact late gives the same result
as asserting it on time: a value from last year that arrives today still ends when the next
value began, and a re-assertion dated before the start of an open interval moves that start back.
