# A GraphRAG question-answering service

You have built the parts: ontology-guided extraction, entity resolution, temporal edges,
multi-hop questions with provenance, a guarded query language and community summaries. A real
service is those parts joined, and the joins are where the bugs live. "Acme Corp." in one
document and "The ACME Company" in another must be one node *before* a fact is written, and the
same node when a model names it in a query. A document dated last March must close the value
that a document dated this March replaced, even if it is ingested afterwards. An answer that
cites a fact must be able to say which documents support it, including the ones that merely
repeated it, and so must an answer about the whole graph.

```text
doc (id, date, text) ──extract──► triples ──resolve──► ids ──► temporal graph (with sources)
                                                                      │ facts valid at as_of
question + start ──resolve──► walk ──► model ──► cited facts + documents
question ──► model ──► query ──check──► rows
question ──► communities ──► summaries ──► model ──► cited reports + documents
```

Your tests drive `service.GraphRAG` only. The other five files are the structure the starters
suggest; keep them, change them, or fold everything into `service.py`, but submit all six.

## Your task

Implement `GraphRAG(extractor, answerer, ontology, aliases=None)`. `extractor` and `answerer` are
model clients; the extractor is only ever used to extract, and ingesting never calls the
answerer.
`ontology` is the dict from the extraction exercise (`types` and `relations`) with one extra
optional key, `functional`: the relations that have one value at a time. `aliases` is the alias
table from the entity resolution exercise. Each service has its own graph, resolver and summaries
and shares nothing with another.

### `ingest(doc_id, date, text)`

`date` is `YYYY-MM-DD`: four ASCII digits, a hyphen, two digits, a hyphen, two digits, and
nothing else. Anything else raises `ValueError` before the model is called.

1. Extract the triples from `text` exactly as in the extraction exercise: the same system prompt
   lines (`Entity types: ...` and `- relation: Domain -> Range`), `text` as the only user
   message, `max_tokens=2000`, the same validation, fenced replies accepted, and `ValueError` for
   a reply that is not a JSON array. If extraction raises, nothing is recorded.
2. Resolve each valid triple's subject and object to entity ids with the entity resolver
   (normalisation, then the alias table once). Predicates stay as they are. If either name
   normalises to nothing (`"&&&"`), that triple is refused: nothing of it is recorded, it counts
   as rejected rather than accepted, and the document's other triples are recorded as usual.
3. Record each triple as asserted on `date`, by document `doc_id`, with the temporal rules of the
   temporal edges exercise: events are applied in date order whatever order they arrived in;
   asserting a triple that is already open adds a source and nothing else; a functional
   relation's new value closes the other open values on that date, and an interval that would
   start and end on the same date is dropped. **Unlike** that exercise, documents with the same
   date are applied in `doc_id` order (string order), not call order, and the triples of one
   document in reply order. So the graph never depends on arrival order.
4. Return `IngestReport(accepted, rejected)`: the number of triples recorded (valid triples, as
   `Extraction.triples`, so repeats count once) and the number refused (the items extraction
   rejected, plus any triple refused in step 2).

A late document is applied at its own date, as if it had arrived on time. If it restates the
value that was open on that date, it joins that interval's sources and changes nothing else. If
it gives a functional relation another value, that value replaces the open one from that date,
until a later assertion of a different value.

A fact's **sources** are the `doc_id`s of the assertion that opened its interval and of those
that restated the triple while that interval was open, listed by `(date, doc_id)` and without
repeats. Each interval has its own: when a triple ends and is later asserted again, the new
interval starts with only the new document. A document whose interval was dropped (it started
and ended on the same date) supports nothing. Sources therefore do not depend on arrival order
either.

### `ask(question, start, as_of=None, max_hops=2)`

1. Resolve `start` like any other mention. `as_of` is `None` or a date (invalid dates raise
   `ValueError`).
2. The facts to search are those valid on `as_of` (`valid_from <= as_of`, and `as_of` before
   `valid_to` if there is one), or when `as_of` is `None`, those that have not ended.
3. Walk them as in the multi-hop exercise: `max_hops` hops from the start id, both directions,
   each fact recorded at the hop that first reached it, nodes expanded once. Sort by
   `(hop, subject, predicate, object)` and number from 1.
4. Call the answerer once, with a system prompt that contains these three sentences word for
   word (add others if you like): `Answer the question using only the numbered facts.`,
   `Cite each fact you rely on like [2].` and
   `If the facts do not contain the answer, say you do not know.` Send one user message: `Facts:`, then one line per fact
   `[n] subject | predicate | object | valid_from`, a blank line and `Question: ` plus the
   question.
5. Return `Answer(text, citations, sources)`, where `text` is the answerer's reply unchanged. A
   marker is `[` and a whole number without leading zeros and `]`; ones that match no fact are
   ignored. `citations` are the cited facts in order of first citation, each once, as
   `Citation(subject, predicate, object, valid_from, valid_to, sources)` with `sources` as a
   list. `sources` on the answer are the citations' sources combined, in that order, without
   repeats.

If no fact is within reach, do not call the answerer: return `Answer("I don't know.", [], [])`.

### `query(question, as_of=None)`

A question whose answer is a list of names is better answered by a query than by prose.

1. `as_of` is checked as in `ask`. Call the answerer once, with a system prompt that explains the
   query language of the guarded text-to-query exercise and contains a line `Predicates: `
   followed by the ontology's relations, sorted and joined with `, `. The only user message is
   `question`, unchanged.
2. The reply is untrusted. Check it, stripped, exactly as that exercise does, with two
   differences: the allowed predicates are the ontology's relations, and a quoted subject or
   object is a mention, which must resolve to a subject or object of a fact valid on `as_of`
   (a name that normalises to nothing is refused too).
3. If anything is wrong, return `QueryResult(None, [], "<a short reason>")`. Otherwise run it
   over the facts valid on `as_of` and return `QueryResult(query, rows, None)`, with the stripped
   reply and the rows as that exercise builds them, in entity ids. Zero rows is a valid answer.

### `ask_global(question, as_of=None)`

Some questions are about the whole graph, not one entity's neighbourhood.

1. `as_of` is checked as in `ask`. Take the communities of the facts valid on `as_of` exactly as
   the community summaries exercise does with `min_size=3`, and have the answerer summarise each
   one with that exercise's prompts. A service never asks for the same summary twice: it keeps
   each summary under its user message for as long as it lives.
2. If there is no community, do not call the answerer: return
   `GlobalAnswer("I don't know.", [], [])`.
3. Otherwise call the answerer once more, with a system prompt that contains these three
   sentences word for word: `Answer the question using only the numbered reports.`,
   `Cite each report you rely on like [2].` and
   `If the reports do not contain the answer, say you do not know.` Send one user message:
   `Reports:`, then one line per community `[n] summary` with `n` its id plus one, a blank line
   and `Question: ` plus the question.
4. Return `GlobalAnswer(text, reports, sources)`, `text` being the reply unchanged. Markers are
   read as in `ask`. `reports` are the cited communities in order of first citation, each once,
   as `Report(id, members, summary, sources)`. A report's sources are its facts' sources, the
   facts in the order of its summary prompt, without repeats; `sources` on the answer combine
   the reports' in that order.
