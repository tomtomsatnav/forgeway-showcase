# Streaming responses

A long reply can take many seconds to generate. Waiting for all of it before showing anything
makes an application feel broken, so chat interfaces **stream**: the provider sends the reply in
small pieces as the model writes it, and you show each piece as it lands. The pieces are events,
and your code has to put the reply back together from them. Text is easy. Tool calls are not:
their arguments arrive as fragments of JSON, cut at any character, and when the model asks for
several tools at once the fragments of different calls can arrive interleaved.

Streams also break halfway. That is harder than a failed `complete()`, because the user may
already have read half an answer. Starting again from the top would show it to them twice, and
the second answer may not even match the first. If nothing has been shown yet, though, a restart
costs nothing visible.

```python
for event in client.stream(messages, tools=tools):
    if isinstance(event, TextDelta):  # event.text: the next piece of reply text
        ...
    elif isinstance(event, ToolCallStart):  # event.id, event.name
        ...
    elif isinstance(event, ToolCallDelta):  # event.id, event.partial_json: a fragment
        ...
    elif isinstance(event, ToolCallEnd):  # event.id: that call's fragments are complete
        ...
    elif isinstance(event, MessageEnd):  # event.stop_reason, event.usage: always last
        ...
```

Each call's arguments, joined in order, are one JSON object, for example the fragments
`'{"ci'`, `'ty": "Le'` and `'eds"}'`.

## Your task

Implement `stream_completion(client, messages, on_text, *, tools=())` in `streaming.py`. It
returns the reply as a `Completion`, as `client.complete` would.

- Call `client.stream(messages, tools=tools)`.
- For each `TextDelta`, call `on_text` with exactly its text, once per delta, before reading the
  next event.
- The `Completion`'s `text` is every delta's text joined exactly, with nothing added or stripped;
  its `stop_reason` and `usage` are those of the `MessageEnd` event.
- Its `tool_calls` hold one `ToolCall(id, name, arguments)` per call, in the order the calls
  started. `arguments` is the call's fragments joined and parsed as JSON; a call with no
  fragments has the arguments `{}`.
- If the stream raises a `ModelError` after any text was passed to `on_text`, do not start it
  again. Raise `StreamInterrupted(partial_text, error)` (defined in the starter), where
  `partial_text` is exactly the text shown so far and `error` is the error the stream raised.
- If it raises before any text was shown and the error is a `ServerError` or `RateLimitError`,
  call `client.stream` once more and return that attempt's reply alone: nothing from the broken
  attempt carries over. If the second attempt also breaks before any text, let its error
  propagate. Any other error before text (such as `InvalidRequestError`) propagates at once.

A production app would wait before restarting, with the backoff from "Retries and exponential
backoff", and show the user that the answer was cut off rather than hiding it.
