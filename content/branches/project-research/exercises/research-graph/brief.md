# Milestone 2: a knowledge graph of what the team finds

**So far.** In milestone 1 you built the team's two MCP servers on one core:
`search_server.py` (`search` and `fetch` over a corpus) and `notes_server.py` (`add_note`,
`list_notes` and a `delete_note` that needs confirmation), with resources, pagination and
argument checks in `mcp_server.py`. They are in your workspace, and they still have to work: one
check here builds the graph from what your search server returns.

**This milestone** adds `knowledge.py`. Workers will fetch documents, and a writer will need the
facts in them, with dates and with the sentence that says so. Raw documents are long, repetitive,
contradict each other over time and may contain text that tries to give orders. A knowledge graph
keeps only typed facts that the document actually states, joins the different spellings of one
entity, records when each fact held, and remembers which documents support it.

```text
fetch result {id, title, date, text} ──extract (one model call)──► items
     ──check ontology and evidence──► (Type:id, relation, Type:id) at date, by doc, with evidence
     ──replay in (date, doc id) order──► facts with validity intervals and sources
```

It draws on **Ontology-guided extraction**, **Entity resolution**, **Temporal edges**,
**Multi-hop questions with provenance** and **A GraphRAG question-answering service**. The graph
here differs from that service in three ways: entity ids carry their type, every triple must quote
its evidence, and the whole graph can be saved and loaded, which milestone 3 needs to survive a
crash.

## Your task

Implement `KnowledgeGraph(ontology)` in `knowledge.py`. `ontology` is
`{"types": [...], "relations": {name: [Domain, Range]}, "functional": [names]}`, where a
functional relation has one value at a time. Learner-facing results are plain dicts and lists.

### `ingest(client, doc)`

`doc` is what `fetch` returns as `structuredContent`: `{"id", "title", "date", "text"}`.

1. `date` must be `YYYY-MM-DD` (four ASCII digits, a hyphen, two digits, a hyphen, two digits,
   nothing else), or raise `ValueError` before the model is called.
2. A document whose `id` was already ingested is skipped without a model call: return
   `{"accepted": 0, "rejected": 0, "duplicate": True}`.
3. Make one call with `max_tokens=2000`. The system prompt contains the line
   `Entity types: ` plus the types joined with `, `, one line `- <relation>: <Domain> -> <Range>`
   per relation, and the sentence in `DATA_SENTENCE` (in the starter). The only message is a user
   message holding exactly `<document id="ID" date="DATE">`, a newline, the text, a newline and
   `</document>`.
4. The reply is a JSON array, perhaps inside a ```` ``` ```` or ```` ```json ```` fence. Anything
   else raises `ValueError`, and the document is not recorded, so it can be ingested later.
5. An item is valid when it is an object with `subject` and `object` (each `{"name", "type"}`
   with string values), a `predicate` that is a relation of the ontology with the subject's type
   as its domain and the object's type as its range, and an `evidence` string that is not blank
   and occurs **word for word** in the document's text. Both names must also normalise to
   something (below). Anything else is rejected.
6. An entity's id is `<type>:<normalised name>`, normalised exactly as in the entity resolution
   exercise: NFKD and drop combining marks, casefold, every non-alphanumeric character becomes a
   space, split on whitespace, drop a leading `the` when more than one token is left, drop
   trailing `SUFFIXES` while more than one token is left, join with single spaces. So
   `The ACME Company, Ltd.` of type `Organisation` is `Organisation:acme`, and a person called
   Acme is `Person:acme`, a different entity.
7. A triple (subject id, predicate, object id) repeated in one reply counts once, with its first
   evidence. Return `{"accepted": <triples recorded>, "rejected": <items refused>,
   "duplicate": False}`.

### Time and sources

Each recorded triple is asserted on the document's `date` by its `id`. Apply assertions in order
of `(date, doc id, position in the reply)`, whatever order the documents arrived in, so the graph
never depends on arrival order.

- Asserting a triple that is already open adds a source and nothing else.
- For a functional relation, asserting a new object for a subject closes that subject's other
  open objects for the relation on that date. An interval that would start and end on the same
  date is dropped, and its sources with it.
- An interval's `sources` are `{"doc", "evidence"}` for the assertions that opened it or restated
  it while it was open, in application order, one per document (its first evidence). When a
  triple ends and is asserted again later, the new interval starts with only the new document.

### `facts(as_of=None, entity=None)`

The facts valid on `as_of` (`valid_from <= as_of`, and `as_of < valid_to` when there is a
`valid_to`), or when `as_of` is `None` the ones that have not ended. An invalid `as_of` raises
`ValueError`. With `entity` (an entity id), only facts where it is the subject or the object.
Each fact is `{"subject", "predicate", "object", "valid_from", "valid_to", "sources"}`, with
`valid_to` `None` while open, sorted by `(subject, predicate, object, valid_from)`.

### `to_json()` and `KnowledgeGraph.from_json(text)`

`to_json()` returns a `str` of JSON holding everything the graph knows. `from_json` rebuilds it,
in a new process with nothing else to go on: it answers `facts` the same, still skips documents
it has ingested, and further documents change it exactly as they would have changed the original.
The tests call `from_json` in a new Python interpreter that is handed only the text, so the text
must hold the documents' ids and evidence itself: nothing kept in memory or in a file of your
own is there.
