# Parallel fan-out and aggregation

Summarising twelve documents one after another takes twelve times as long as it needs to. The
requests do not depend on each other, so **fan out**: send them all at once, wait for every
reply, then **aggregate** the replies with one last call that sees them together.

```text
            ┌─► summarise doc A ─┐
documents ──┼─► summarise doc B ─┼─► collect ──► aggregate ──► overview
            └─► summarise doc C ─┘
```

Concurrency makes two things easy to get wrong. First, replies arrive in whatever order the
network delivers them, so an aggregation prompt built "as they finish" changes from run to run;
build it from the input order instead. Second, one request failing must not throw away the
work of the others: report it and carry on with what you have.

Your tests cannot rely on timing or ordering, so they check the **set** of requests, the
aggregation you built from the results, and that the calls genuinely overlapped.

## Your task

Implement `summarise_all(client, documents, max_workers=4)` in `fanout.py`. `documents` maps an
id to its text.

- Send one request per document: the document text as the single user message. Run them
  concurrently, with at most `max_workers` in flight at once.
- A request that raises a `ModelError` puts the document id and the error message in `failed`.
  The other documents are unaffected. Only a `ModelError` counts as a failed document: any other
  exception is a bug and propagates out of `summarise_all`.
- Make one aggregation call. Its user message is one line per summarised document, `[id] summary`,
  in the order of `documents` (not the order replies arrived), joined with newlines. Failed
  documents are left out.
- Return `FanOutResult(summaries, failed, overview)`: `summaries` maps id to summary in the order
  of `documents`, and `overview` is the aggregation reply. If every document failed, make no
  aggregation call and return an empty `overview`.
