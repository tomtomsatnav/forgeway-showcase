# JSON-RPC dispatch

The **Model Context Protocol** (MCP) is how an application plugs tools, documents and prompts into
a model without custom glue for each one. It is not exotic underneath: MCP is a set of JSON-RPC 2.0
messages. In this branch you build it by hand, at the wire level, against protocol revision
**2025-11-25** (the newest revision that opens with the `initialize` handshake). No SDK; the point
is to see what SDKs hide.

Everything starts with three message shapes:

```text
request       {"jsonrpc": "2.0", "id": 7, "method": "ping", "params": {}}
notification  {"jsonrpc": "2.0", "method": "notifications/initialized"}
response      {"jsonrpc": "2.0", "id": 7, "result": {}}
              {"jsonrpc": "2.0", "id": 7, "error": {"code": -32601, "message": "..."}}
```

A request carries an `id` and must be answered with a response bearing the same id. A
**notification** has no `id` and must *never* be answered, not even with an error, because there
is nobody waiting. MCP narrows JSON-RPC a little: an id is a string or an integer, never null, and
there are no batches.

The standard error codes you will use throughout the branch:

| Code | Meaning |
| --- | --- |
| -32700 | Parse error: the text was not JSON |
| -32600 | Invalid request: JSON, but not a valid message |
| -32601 | Method not found |
| -32602 | Invalid params |
| -32603 | Internal error |

## Your task

Implement `dispatch(message, methods)` in `rpc.py`. `message` is a decoded JSON value and
`methods` maps method names to functions that take the `params` dict (an empty dict when absent)
and return a result dict. Return the response dict, or `None` when no response is due.

- A request gets `{"jsonrpc": "2.0", "id": <same id, same type>, "result": <handler result>}`.
- A notification runs its handler if there is one and returns `None`, even if the method is
  unknown or the handler raises.
- An unknown method is error -32601, and its message names the method (`method not found: foo`;
  the wording and capitalisation are yours). A handler raising `InvalidParams` is -32602, using
  the exception's message. Any other exception is -32603 with a fixed message that does not
  reveal the exception's text.
- Anything that is not a valid message (not an object, `jsonrpc` not `"2.0"`, `method` not a
  string, an id that is not a string or integer, `params` that is not an object) is error -32600
  and never reaches a handler. Echo the message's `id` in that error if it had a valid one;
  otherwise use `null`.
