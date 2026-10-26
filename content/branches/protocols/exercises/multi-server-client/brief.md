# Many servers, structured output

Real agents connect to several MCP servers at once: files, a database, a search service. That
raises two problems a single connection hides.

**Names collide.** Two servers can both offer a tool called `search`, and the model sees one flat
list. A client must **namespace** the tools, for example `weather__search` and `maps__search`, and
route each call back to the right server under its original name. The separator has to be
unambiguous: if tool names may contain `__` (`get__forecast` is a legal name), then *server* names
must not, and you split on the first separator only.

**Results need a contract.** A tool can declare an `outputSchema`, and when it does, its result
carries machine-readable `structuredContent` next to the human-readable `content`. That contract
is only worth something if the client checks it: a server that returns `{"count": "three"}` for a
schema that says integer has a bug, or is lying, and downstream code must not trust the value.

```text
tools/list     -> {"name": "stats", "outputSchema": {"type": "object",
                    "properties": {"count": {"type": "integer"}}, "required": ["count"]}, ...}
tools/call     -> {"content": [{"type": "text", "text": "{\"count\": 3}"}],
                   "structuredContent": {"count": 3}, "isError": false}
```

Finally, servers fail independently. A dead server must not take the hub down with it.

## Your task

Implement the `Hub` class in `hub.py`. `Hub(clients)` takes a dict mapping a server name to a
connected client with `list_all_tools()` and `call_tool(name, arguments)`. `McpError` comes from
`forgeway_kit.mcp`. `hub.py` already holds `check_instance(value, schema)`, which returns a list of
problems with a value (empty when it is valid); use it.

- Server names are 1 to 32 **ASCII** letters (`A-Z`, `a-z`), digits or `-`. Anything else raises
  `ValueError`: `café`, a name with a trailing newline, `a_b`.
- `tools()` returns every tool of every server, servers in order and each server's tools in its
  own order. Each is a copy of the server's tool dict with `name` changed to
  `<server>__<tool>`; nothing else changes and the server's own dicts are not modified. A server
  that raises `McpError`, `ConnectionError` or `TimeoutError` while listing is skipped, and
  `hub.failed[server_name]` records the error text. List each server exactly once, however many
  times `tools()` and `call()` are used afterwards (a server that failed is not listed again
  either), and remember the tools.
- `call(name, arguments)` returns `{"is_error": bool, "text": str, "data": ...}`. Split `name` on
  the first `__`. A server or tool that does not exist (including a tool the hub did not list)
  raises `ValueError`.
- `text` is the result's text blocks joined with newlines: every text block, in order, and
  nothing for other block types. An `isError` result has `is_error`
  true and `data` `None`.
- When the tool has an `outputSchema`, `structuredContent` must be present and valid; if not, the
  result is `is_error` true with `data` `None` and a text starting `invalid structured output`.
  Otherwise `data` is the `structuredContent`, or `None` when there is none.
- A server that raises `McpError`, `ConnectionError` or `TimeoutError` during a call gives an
  `is_error` result carrying the error text, never an exception.
