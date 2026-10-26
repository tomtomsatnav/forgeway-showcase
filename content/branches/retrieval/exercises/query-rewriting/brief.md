# Query rewriting for follow-up questions

Users talk to chat interfaces the way they talk to people: "What does the Zephyr X2 cost?" then
"What about its battery?" Embedding the second message verbatim searches for "what about its
battery", which matches nothing useful, because the thing it refers to lives in the previous turn.

The fix is a cheap model call before retrieval: given the conversation so far and the new message,
**rewrite it into a standalone search query** ("Zephyr X2 battery life"). It costs one extra
call and often decides whether the right documents are found at all.

```text
history:  user: What does the Zephyr X2 cost?   assistant: It costs 499 pounds.
follow-up: What about its battery?
rewrite:  Zephyr X2 battery life
```

Models add quotes, labels and chatter, so clean the reply before you use it. And when there is
no history the question is already standalone, so do not pay for a call.

## Your task

In `rewrite.py` implement:

- `rewrite_query(client, history, question)`: `history` is a list of `Message`s. Ask the model for a
  standalone query, with the history in the prompt, and return the first line of its reply, stripped of whitespace
  and surrounding quotes. With empty history return `question` and do not call the model.
- `search_conversation(client, store, history, question, k=3)`: rewrite, then return
  `store.search(rewritten, k)`.

The grader's fake model only produces a useful rewrite when the history is actually in the prompt.
