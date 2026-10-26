# Calling tools

When the model decides to use a tool, the client sends a `tools/call` request naming the tool and
its `arguments`. The server runs it and answers. MCP separates two kinds of failure, and getting
the split right is what makes a server pleasant for a model to use.

```text
client -> server  {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                   "params": {"name": "repeat", "arguments": {"text": "ho", "times": 3}}}

server -> client  {"jsonrpc": "2.0", "id": 3, "result": {
                    "content": [{"type": "text", "text": "hohoho"}], "isError": false}}
```

- A **protocol error** is a JSON-RPC `error` response. It means the request itself was wrong: an
  unknown tool name, or `params` that are not a tool call. The model usually never sees these.
- A **tool execution error** is a normal `result` with `"isError": true` and the explanation in
  `content`. It means the call was understood but did not work: the arguments failed validation,
  or the tool raised. The model *does* see these, which is the point: "`times` must be an
  integer" lets it fix the call and try again.

Validate arguments against the tool's `inputSchema` before running the tool, and never run the
tool on invalid input. Python has a trap here: `True` is an `int`, so a naive type check accepts
`true` for an integer argument.

## Your task

Implement `handle_call(request, tools)` in `calls.py`. `request` is a decoded `tools/call`
request. `tools` maps a tool name to a dict with an `"inputSchema"` and a `"handler"`. A handler
takes the arguments dict and returns a string, and may raise `ToolError` (provided) with a message
for the model. Return the complete JSON-RPC response.

- Reply with error -32602 when `params` is missing or not an object, `name` is not a string,
  `arguments` is present but not an object, or the tool does not exist.
- Check the arguments against the schema: `required` properties, each property's `type` (`string`,
  `integer`, `number`, `boolean`, `array`, `object`; booleans are neither integers nor numbers),
  `enum`, and for arrays the `type` of `items`. Properties the schema does not mention are allowed.
  A failure is a result with `isError: true` whose text names the offending argument, and only
  that one: do not list every property of the schema. The handler does not run.
- On success the result is `{"content": [{"type": "text", "text": <handler's string>}],
  "isError": false}`. A missing `arguments` means `{}`.
- If the handler raises, return an `isError` result carrying the `ToolError`'s message, or for any
  other exception its type and message. Never let an exception escape.
