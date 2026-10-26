# Cursor pagination

A server with hundreds of tools or resources cannot send them all in one message. MCP lists use
**cursor-based pagination**: the response carries at most one page of results plus an opaque
`nextCursor`, and the client sends that cursor back to get the next page.

```text
client -> server  {"method": "tools/list"}
server -> client  {"result": {"tools": [... 5 tools ...], "nextCursor": "b2Zmc2V0OjU="}}
client -> server  {"method": "tools/list", "params": {"cursor": "b2Zmc2V0OjU="}}
server -> client  {"result": {"tools": [... 2 tools ...]}}            <- no nextCursor: the end
```

The rules are small but easy to get wrong:

- The cursor is **opaque** to the client. It must hand back exactly what it was given and never
  construct or inspect one. The server may encode anything it likes, such as a position.
- The **last page has no `nextCursor`**. A cursor that leads to an empty page wastes a round trip
  and confuses clients that stop on a short page.
- A cursor the server did not issue is an error: JSON-RPC -32602, invalid params.
- A client must not trust the server to end. A buggy server can return the same cursor for ever,
  and an unbounded loop of requests is a denial of service against yourself.

## Your task

Implement both halves in `paging.py`.

`page(items, cursor, page_size)` is the server side. It returns `(chunk, next_cursor)`: the
`page_size` items starting where `cursor` says (the beginning when `cursor` is `None`), and a
string cursor for the following page, or `None` when this was the last one. An empty list is one
empty page with no cursor. Be stateless: the same arguments always give the same answer. Raise
`InvalidCursor` for a cursor you did not issue (not a string, garbage, tampered with, or pointing
outside this list) and `ValueError` for a `page_size` below 1. You only ever hand out a cursor
for a page that has items, and the first page needs none, so a cursor that points at the very
start of the list or at its end (one past the last item) was never issued either: it is invalid.

`fetch_all(send, method, key, max_pages=50)` is the client side. `send(method, params)` performs
one request and returns its result dict. Collect `result[key]` from every page: the first request
has no `cursor` at all, and each later one passes back the previous `nextCursor` unchanged. Stop
when a result has no `nextCursor`. Raise `RuntimeError` mentioning `cursor` if the server repeats a
cursor, and `RuntimeError` mentioning `max_pages` if it is still going after `max_pages` requests.
