# Bridging MCP tools into a model

So far you have written the server side. The other half of MCP is the **client** that sits between
a model and one or more servers. It has two jobs: speak the protocol correctly, and translate
between MCP tools and the model's own tool-calling interface.

```text
                  MCP client                         MCP server
model  <──tools──  [list_tools]  ── tools/list ──►  [tools]
model  ─tool call─► [call_tool]  ── tools/call ──►  [run it]
model  <─ result ─  (text, errors marked)  <──────  {content, isError}
```

Speaking the protocol is less simple than it looks, because the connection is full-duplex. While
you wait for your response, the server may send you notifications (such as "my tool list
changed"), responses to older requests, or **requests of its own**. A server pinging a client that
never answers will eventually drop it. A client must therefore read in a loop, match each response
to its request by `id`, and deal with everything else.

Translating is mostly about errors. MCP has two kinds, and the model needs both in a form it can
act on: a tool that ran and failed comes back as a result with `isError: true`, and a request the
server rejected comes back as a JSON-RPC error. Either way the loop should hand the model an
`error: ...` result rather than crashing.

## Your task

In `bridge.py`, implement `McpClient` and `run_agent`. A client is built with a `transport`, which
has `send(message_dict)` and `receive()` (a dict, or `None` at the end of the connection).

`McpClient`:

- `initialize()` sends `initialize` with protocol revision `2025-11-25`, empty `capabilities` and a
  `clientInfo` (name and version). If the server's reply names a different revision, raise
  `RuntimeError` mentioning the protocol version and send nothing more. Otherwise send the
  `notifications/initialized` notification and return the result.
- `request(method, params=None)` sends a request with a fresh integer id and returns the `result`
  of the response with that id. Ignore notifications and responses to other ids. Answer a `ping`
  request from the server with an empty result, and any other server request with error -32601.
  Raise `McpError` for an error response and `ConnectionError` if the connection ends first.
- `list_tools()` returns every tool, following `nextCursor` through all pages.
- `call_tool(name, arguments)` returns the `tools/call` result as received.

`run_agent(model, mcp, question, max_steps=6)` lists the server's tools and offers them to the
model as `Tool(name, description, input_schema)`, then runs the usual tool loop: each tool call
goes to `mcp.call_tool` and its result is answered as a `tool` message. Join a result's text
blocks with newlines (a non-text block becomes `[<type> content omitted]`). When the result has
`isError`, or the server answers with a protocol error, the message is `error: ` followed by the
text. Return the model's final text. Make at most `max_steps` model calls and then raise
`RuntimeError` mentioning `max_steps`.
