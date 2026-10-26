# The MCP gateway

Real deployments rarely connect a model to every MCP server directly. They put a **gateway** in
between: one server that the agent talks to, which in turn talks to many others. The gateway is
where you decide what the model may see and do, and it has to behave well when its servers do not.

```text
  model ── agent.py ── client.py ══ stdio ══ gateway.py ══ stdio ══ server "notes"
 (fenced results,      (McpClient)          (a server to its caller,  server "ledger"
  asks the user)                             a client to each server)
```

You are building all three pieces. They are graded together, against servers that misbehave, and on
what finally reaches the model (`FakeModel.requests`), so every hop has to keep its side of the
bargain.

## The gateway

`python gateway.py '<json>'` is a stdio MCP server (newline-delimited JSON, stdout for protocol
messages only and flushed after each one, logs on stderr). The one argument is a JSON object mapping
a **server name** to the argv list that starts that server as a child process, for example
`{"notes": ["python", "notes.py"], "ledger": [...]}`. Names are 1 to 32 **ASCII** letters, digits or
`-`; anything else makes the gateway explain on stderr and exit with status 2 without reading stdin.
It serves until stdin closes, then stops its children and exits with status 0.

**Lifecycle.** Speak revision `2025-11-25`. `initialize` needs `protocolVersion` (a string),
`capabilities` and `clientInfo` (objects); anything less is -32602 and changes no state. A second
one is -32600. The reply always names `2025-11-25`, and its capabilities are `tools`, `resources`
and `prompts`, each `{}`. Before `initialize` only `ping` works; anything else is -32600. Invalid
messages are -32600 (echo the id if it was valid), unparseable lines -32700 with a null id, unknown
methods -32601, and notifications are never answered.

**Connecting.** When `initialize` arrives, start every server and run the client handshake on it
(`McpClient` from `client.py`). Then list what it advertised in its `capabilities`, and only that,
following every cursor: tools, resources, prompts. Each list is fetched once and remembered. A
server that cannot be started, speaks another revision, or fails while being listed contributes
nothing and is never used again. `StdioTransport` in `client.py` is provided; it gives up on a
silent server after two seconds, and its `close()` kills the child at once. Answer a call to a
silent server within about three seconds: if you close a server more gently, give it at most one
second to exit before you kill it.

**Catalogue.** `tools/list`, `resources/list` and `prompts/list` list every server's entries, in
the order the servers were given and each server's own order, in pages of **three** with an opaque
`nextCursor` (no trailing empty page; an invalid cursor is -32602, as in the pagination exercise).
Each entry is a copy of the server's, changed only here: a tool or prompt `name` becomes
`<server>__<name>`, and a resource `uri` becomes `mcp://<server>/<uri>`. Annotations, output
schemas and the rest are relayed untouched.

**Calls.**

- `tools/call`: `arguments` may be left out and then means `{}`. A missing `name` or `arguments`
  that is not an object is -32602, and so is a name the gateway did not list. Check `arguments`
  against the tool's `inputSchema` with `check_instance` (in `gateway.py`): problems give a normal
  result with `isError` true and a text starting `Invalid arguments` that includes the problems it
  found (they name the argument), and the server hears nothing. Otherwise forward the call under
  the tool's original name and arguments.
- A result is relayed as received. If the tool has an `outputSchema` and the result is not an
  error, its `structuredContent` must exist and be valid; if not, answer an `isError` result whose
  text starts `invalid structured output` and carries no `structuredContent`.
- `resources/read` takes a namespaced uri (a missing one is -32602) and asks the server for the
  original. A uri the gateway did not list is -32002 and is never forwarded. Each returned content has its `uri` set to the
  namespaced one. `prompts/get` takes a namespaced name (unknown, or `arguments` that are not
  strings, is -32602) and relays the server's answer.

**Failures cross two hops, and each kind keeps its shape.**

| What happened downstream | What the gateway answers |
| --- | --- |
| The tool ran and failed (`isError` result) | The same result, unchanged |
| The server answered with a JSON-RPC error | A JSON-RPC error with the same code and `data`, and the message `<server>: <message>` |
| The server died, was silent or closed the pipe | -32603 with a message saying `<server>` is `unavailable`; the server is closed and every later call to it answers the same at once |

While waiting for an answer a server may notify, send stray responses and send **requests of its
own**: answer a `ping` with an empty result and any other request with -32601, as `McpClient`
does. One failing server never costs another one anything.

**Confirmation.** A tool is destructive when its annotations say `"destructiveHint": true` (exactly
the boolean; the specification treats annotations as hints, and here only that hint counts, never
the tool's name). A call to one that passes the argument check does not run. The gateway answers an
`isError` result whose text says confirmation is required, with
`structuredContent: {"confirmation": {"token": "<token>"}}`. The token is fresh for every
challenge and is **not** in the text. The caller repeats the same call with
`"_meta": {"gateway/confirm": "<token>"}` in the params; if the token was issued for exactly that
tool and those arguments and has not been used, the call runs (without `_meta`). Any other token
gets a new challenge. A token is good once: presenting it uses it up, even when the call does not
match.

## The client and the agent

In `client.py`, `McpClient(transport)` is your tool-bridge client with a few more parts:
`initialize()`, `request(method, params=None)` (matches ids, answers server pings, raises
`McpError` with `code`, `message` and `data`), `list_all(method, key, max_pages=50)` (follows
`nextCursor`; seeing a cursor twice, or more than `max_pages` pages, raises `ConnectionError`),
`list_all_tools()`, `call_tool(name, arguments, meta=None)` (add `"_meta": meta` to the params when
`meta` is given) and `close()`.

In `agent.py`, `run_agent(model, mcp, question, confirm, max_steps=6)` is the safe agent from the
untrusted-output exercise, extended. `mcp` is a connected `McpClient` (in some checks a stand-in
with the same methods), and the agent may use any of the methods above:

- Offer only tools whose whole name is 1 to 64 ASCII letters, digits, `_` or `-`, each as
  `Tool(name, description, input_schema)`. Clean each description: replace non-printable
  characters with spaces, collapse whitespace and strip, then cut to 197 characters plus `...` if
  it is over 200.
- Use one fixed system prompt that mentions `<tool-result>`, calls what is inside untrusted data
  and says never to follow instructions found there.
- Every tool message is exactly `<tool-result>\n` + body + `\n</tool-result>`. The body joins all
  content blocks with newlines (a non-text block is `[<type> content omitted]`), prefixed `error: `
  for an `isError` result; a protocol error is `error: <message>`; a call to a tool you did not
  offer is `error: unknown tool` and never reaches `mcp`. Cut a body to 2000 characters (prefix
  included) and add ` [truncated]`, then replace the leading `<` of each look-alike
  `<tool-result ...>` or `</tool-result ...>` tag (any case, spacing or attributes) with `&lt;`.
  The tag name must be exactly `tool-result`: `<tool-resultx>` is ordinary text.
- Make each call first without `meta`. If the result is a confirmation challenge (an `isError`
  result with a string at `structuredContent.confirmation.token`), call `confirm(name, arguments)`
  with the offered tool name and the arguments. If it returns true, repeat the call with
  `meta={"gateway/confirm": token}` and use that result (a second challenge is
  `error: confirmation was not accepted`); if not, the body is `error: declined by the user`.
  The model never sees the token, the challenge or `structuredContent`.
- At most `max_steps` model calls, then `RuntimeError` mentioning `max_steps`; return the final text.
