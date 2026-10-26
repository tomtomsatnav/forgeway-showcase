# Multi-hop questions with provenance

"Which city is the company that employs Ada's manager based in?" has no single document that
contains the answer. It takes three facts: Ada reports to Bo, Bo works at Initech, Initech is
based in Leeds. A vector search finds passages that *look like* the question; a graph can follow
the links. Starting from the entity in the question, you walk outwards one **hop** at a time,
collect the edges you pass, and hand them to the model as evidence.

Every edge also remembers where it came from: the `source` document that asserted it. When the
model cites an edge, you can cite the document, and a reader can check the claim.

```text
Ada ──reports_to──► Bo ──works_at──► Initech ──based_in──► Leeds
 1 hop: Ada's edges   2 hops: + Bo's   3 hops: + Initech's
```

Edges point one way, but a question can need either way: "Who works at Initech?" follows
`works_at` backwards. So a hop follows edges **in both directions**.

## Your task

Implement `answer_question(client, store, question, start, max_hops=2)` in `hops.py`.

`store.match(subject=None, predicate=None, obj=None)` returns edges, each with `.subject`,
`.predicate`, `.object` and `.source`. Several edges can have the same triple and different
sources.

**Traversal.** Starting at the node `start`, repeat `max_hops` times: for every node reached in
the previous step (the start node in the first), collect all its edges, as subject and as object.
Each edge is recorded once, at the hop that first reached it (identical triples from different
sources are different edges). Nodes you have already expanded are not expanded again, so cycles
end. The nodes at the far ends of the new edges are what the next hop expands.

**Evidence.** Sort the edges by `(hop, subject, predicate, object, source)`, number them from 1,
and put them in the one user message as lines of the form `[1] subject | predicate | object`
(the source is not shown to the model), followed by the question. Call the model once, with a
system prompt that contains these three sentences word for word (add others if you like):

```text
Answer the question using only the numbered facts.
Cite each fact you rely on like [2].
If the facts do not contain the answer, say you do not know.
```

**Citations.** Return `Answer(text, edges, sources)`:

- `text` is the model's reply;
- `edges` are the edges it cited, in order of first citation, each once;
- `sources` are the distinct `source` values of those edges, in the same order.

A marker is `[` followed by a whole number written without leading zeros, and `]`. `[0]`, `[01]`,
`[x]` and numbers beyond the last fact are not markers: ignore them.

If there are no edges within reach, do not call the model. Return
`Answer("I don't know.", [], [])`.
