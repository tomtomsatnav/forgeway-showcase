# Guarded text-to-query

Letting a model write a database query is attractive: the user asks in English, and the answer
is exact rows instead of a paragraph. It is also dangerous. A model's output is influenced by
the user, by documents it has read and by whoever planted text in them, so a query it wrote is
**untrusted input**. If your code executes it as it stands, the user's question has become your
program.

The safe design is a **small language with an allow-list**. You define a grammar that can only
express reads, you check the model's text against it, and you run only what you understood. If it
does not fit exactly, it is refused, not repaired, and nothing touches the store.

## The language

```text
FIND ?who WHERE ("Ada", "works_at", ?org) AND (?who, "works_at", ?org) LIMIT 5
```

```text
query    = "FIND" vars "WHERE" pattern { "AND" pattern } [ "LIMIT" number ]
vars     = var { var }
pattern  = "(" term "," term "," term ")"      subject, predicate, object
term     = var | quoted
var      = "?" then 1 to 16 characters from a-z, 0-9 and _, the first a letter (a-z)
quoted   = a double quote, 1 to 64 characters that are not a double quote, a
           backslash or a newline, and a double quote
number   = 1 to 99, written without leading zeros
```

Whitespace means spaces, tabs and newlines (`\n`) only; a carriage return `\r` is not
whitespace. It separates the words and may appear (or not) around the brackets and commas; at
least one whitespace character must separate `FIND`, each variable, `WHERE`, `AND` and `LIMIT`
from their neighbours. Keywords are upper case. The whole reply, once stripped of leading and
trailing whitespace (strip only spaces, tabs and newlines, not other Unicode whitespace), must
be exactly one query: no code fences, no explanation before or after.

On top of the grammar, these rules must hold:

1. The **predicate** of every pattern is a quoted name found in `store.predicates()`. It cannot be
   a variable.
2. A quoted **subject** or **object** is found in `store.entities()`.
3. At most 3 patterns.
4. Every variable after `FIND` is distinct and appears in at least one pattern.
5. `LIMIT` is at most 50. Without it the limit is 20.

## Your task

Implement `ask(client, store, question)` in `guard.py`. It returns `Outcome(query, rows, error)`.

- Call the model once with a system prompt that explains the language and contains a line
  `Predicates: ` followed by the allowed predicates, sorted and joined with `, `. The only user
  message is `question`, unchanged.
- Check the stripped reply as described above. If anything is wrong, return
  `Outcome(None, [], "<a short reason>")` and do not call `store.match` at all.
- Otherwise run it. Patterns run left to right; each is answered with
  `store.match(subject, predicate, obj)`, where a term you already know (a quoted name, or a
  variable bound by an earlier pattern) is passed in and anything else is `None`. A variable used
  twice in one pattern must get the same value in both places. The rows are tuples of the
  `FIND` variables' values, in `FIND` order, distinct, sorted, then cut to the limit. Return
  `Outcome(reply, rows, None)`; zero rows is a valid answer.

`store.match` returns triples with `.subject`, `.predicate` and `.object`.
