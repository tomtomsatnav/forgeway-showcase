# Grounded answers with citations

Retrieval-augmented generation (RAG) means the model answers from text you hand it rather than from
memory. The retrieval half finds passages; the generation half has to be told to use them. Two
things make the result trustworthy in production: the model sees *only* the retrieved sources,
and every claim carries a citation a user (or your code) can check.

The usual trick is to number the sources in the prompt and ask for `[n]` markers:

```text
Answer using only the sources below. Cite them like [1].

[1] Refunds are issued within 30 days.
[2] Support is open 24/7.

Question: How long do refunds take?
```

The model replies "Refunds take 30 days [1]." Your code then turns `[1]` back into the real
document id so the UI can link to it. Those markers are model output: they can be repeated,
out of range or missing, and your parser has to cope.

Two cautions. Retrieved text is **untrusted input**: a document can contain instructions that try
to hijack the model, so keep your instructions separate from the sources and see
the Prompt injection basics exercise (`starter.prompt-injection-basics`) for how. And some providers offer
native citation features that return structured references for you; they are worth using when
available, but the numbered-marker pattern works with any model and teaches what they do.

## Your task

Implement `answer(client, store, question, k=3)` in `rag.py`. `store.search(question, k)` returns hits
with `.id` and `.text`. Call it, build a prompt containing the numbered sources and the question,
and ask the model with `client.complete`. Return `Answer(text, sources)` where `text` is the
model's reply and `sources` lists the ids of the sources it cited, in order of first citation,
without duplicates and ignoring markers that match no source.

If the store returns no hits, do not call the model: return an `Answer` with a short
"I don't know" style text and `sources=[]`.
