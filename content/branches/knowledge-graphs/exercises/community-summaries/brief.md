# Community summaries

Vector search answers questions about *a passage*. Some questions are about the *whole corpus*:
"What are the main themes in these documents?" No single chunk holds that. **GraphRAG** answers
it by splitting the graph into **communities** (groups of entities that are densely
connected), asking a model to write a short report on each, and later answering global questions
from the reports.

Real systems detect communities with algorithms such as Leiden. Here the algorithm is fixed so
that you can be graded exactly: **connected components**. Treat every triple as an undirected
link between its subject and its object; a community is a set of entities that can reach each
other along such links.

```text
A ─► B ◄─ C        D ─► E        F ─► F
 └─► G                           
{A, B, C, G}      {D, E}         {F}        three communities
```

Note that `C` and `A` share no edge pointing from one to the other. Direction is ignored.

What you grade here is what *reaches the summariser*. The summary text itself is whatever the
model says.

## Your task

Implement `summarise_communities(client, triples, min_size=3, cache=None)` in `communities.py`.
`triples` is a list of `(subject, predicate, object)` tuples of strings, in any order, possibly
with repeats. It returns a list of `Community(id, members, summary)`.

1. **Find communities.** Every subject and object is an entity. A community's `members` are its
   entity names, sorted.
2. **Order them.** By number of members, largest first; equal sizes by their first (smallest)
   member name.
3. **Drop small ones.** Communities with fewer than `min_size` members are left out. Numbering
   comes after this: `id` is the position (from 0) in the list you return.
4. **Prompt the model once per community**, in that order. The user message is the community's
   distinct triples (a triple belongs to the community of its subject), sorted as tuples
   `(subject, predicate, object)` in Python's usual string order, one per line as
   `subject | predicate | object`, joined with `\n` and nothing else. The system prompt contains
   this sentence word for word (add others if you like):
   `Summarise the following facts about a group of related entities in one paragraph.`
   The reply is the community's `summary`.
5. **Cache.** If `cache` is a dict, look the user message up in it first; on a hit make no model
   call. After a call, store the reply under that message.
