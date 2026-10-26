# Milestone 1: tool servers for the team

This guided project builds one codebase in four milestones: a small **research agent team**. A
question comes in, agents search a corpus and read what they find, the facts go into a knowledge
graph, a writer turns them into a report, and the report is filed as a note once a person agrees.
In the last milestone you evaluate the whole team and attack it before it may ship.

```text
          milestone 3: the team                          milestone 1: the servers
question ─► router ─► planner ─► workers ══ stdio ══ search_server.py   (search, fetch)
                                    │
             milestone 2: graph ◄───┘ documents
                     │
                     ▼
                  writer ─► person says yes ══ stdio ══ notes_server.py  (add_note, ...)

          milestone 4: trajectory evals, a judge, injected documents and a release gate
```

Everything the agents do to the world goes through MCP tools, so the team starts with its
servers. You build two, sharing one core, at the wire level as in the Protocols & tools branch.
This milestone draws on **Serving MCP over stdio**, **The initialise handshake**, **Listing tools
with input schemas**, **Calling tools**, **Cursor pagination**, **Resources and prompts** and the
confirmation step of **The MCP gateway**.

## The files

- `mcp_server.py`: what both servers share: framing, the lifecycle, tool calls, argument checks,
  resources, pagination and confirmation.
- `search_server.py`: `python -S search_server.py CORPUS`, where `CORPUS` is a JSON file holding a
  list of `{"id", "title", "date", "text"}` documents.
- `notes_server.py`: `python -S notes_server.py NOTES_FILE`. The file need not exist yet.

The tests start each server as a child process with `python -S`, which leaves out site-packages:
use the **standard library only**. The script's own directory is still on the path, so the two
servers can import `mcp_server`.

## Both servers

**Framing and lifecycle.** Newline-delimited JSON-RPC on stdin and stdout, one message per line,
flushed straight away; stdout carries protocol messages only and logs go to stderr. Exit with
status 0 when stdin closes.

- `ping` always works and answers `{}`. Before `initialize`, anything else is -32600.
- `initialize` needs params with `protocolVersion` (a string), `capabilities` and `clientInfo`
  (objects); otherwise it is -32602 and nothing changes. The result is exactly
  `{"protocolVersion": "2025-11-25", "capabilities": {"tools": {}, "resources": {}},
  "serverInfo": {"name": "search", "version": "1.0.0"}}` (`"notes"` for the notes server). A
  second `initialize` is -32600.
- A line that is not JSON is -32700 with a null id. A message that is not a JSON-RPC 2.0 request
  or notification is -32600, with its id when that id is valid (a string or an integer) and a
null id otherwise. An unknown method is -32601.
  Notifications are never answered.

**Tools.** `tools/list` returns every tool in one page: `name`, `description`, `inputSchema` and
`annotations`, plus `outputSchema` where the tool has one. A `tools/call` without a string `name`,
with a name that is not listed, or with `arguments` that are not an object is -32602. Then check
the arguments against the tool's input schema, which uses only `type` (`string` or `integer`),
`minimum`, `maximum` and `required`:

- every required argument is present;
- a `string` is a JSON string; an `integer` is a whole number and not a boolean (`true` and `2.0`
  are not integers) within `minimum` and `maximum` where given;
- no argument the schema does not declare.

Any problem gives an ordinary result with `"isError": true` and a text that starts `Invalid
arguments` and names each argument at fault; the tool does not run. Every result has `content`
(one `text` block) and `isError`, plus `structuredContent` where the tables below say so. A tool
that fails returns `isError` true with the text given below.

**Resources.** `resources/list` returns `{uri, name, mimeType}` entries (`mimeType` is always
`text/plain`) in pages of **four**, with an opaque `nextCursor` on every page but the last. There
is no empty page at the end. Cursors must be unforgeable: accept only a cursor that this server
process issued, so one that is made up, edited, built the way yours are built, or issued by
another server process is -32602. `resources/read` with
`params.uri` returns `{"contents": [{"uri", "mimeType", "text"}]}`; a missing uri is -32602 and an
unknown one -32002 with `data: {"uri": <uri>}`.

## The search server

| Tool | Arguments | Result |
| --- | --- | --- |
| `search` | `query` (string, required), `limit` (integer 1 to 10, default 5) | `structuredContent: {"results": [{"id", "title", "date", "score"}]}`; text: one line per result, `id \| date \| title`, or `no results` |
| `fetch` | `id` (string, required) | `structuredContent`: the document's `id`, `title`, `date` and `text`; text: the document's text. An unknown id fails with `unknown document: <id>` |

Both are annotated `{"readOnlyHint": true}`, and `search` has the output schema
`{"type": "object", "properties": {"results": {"type": "array"}}, "required": ["results"]}`.

**Ranking.** A term is a run of ASCII letters and digits after lower-casing; anything else
separates terms. A document's score is the number of times the query's **distinct** terms occur
among the terms of its title and text joined by a space. Keep documents scoring above 0, sort them
by score, highest first, then by `id`, and return the first `limit`.

Each document is also a resource: uri `doc://<id>`, name its title, in corpus order.

## The notes server

| Tool | Arguments | Result |
| --- | --- | --- |
| `add_note` | `topic`, `text` (strings, required), `key` (string) | `structuredContent: {"id", "duplicate"}` |
| `list_notes` | `topic` (string) | `structuredContent: {"notes": [{"id", "topic", "text"}]}`, oldest first, only that topic's when given |
| `delete_note` | `id` (string, required) | `structuredContent: {"id"}`. An unknown id fails with `unknown note: <id>` |

- Notes are numbered `note-1`, `note-2`, ... in the order they are added. An id is **never
  reused**, even after its note is deleted and the server restarted.
- When `key` is given and a note that still exists has that key, nothing is added: the result is
  that note's id with `"duplicate": true`. Otherwise `"duplicate"` is `false`. Milestone 3 uses
  this to file a report exactly once.
- Every change is written to `NOTES_FILE` before the reply goes out, so a new server process on
  the same file carries on where the last one stopped. The format is yours.
- Each note is a resource: uri `note://<id>`, name its topic.
- Annotations: `delete_note` has `"destructiveHint": true`; the other two do not.

**Confirmation.** A call to a tool whose annotations say `"destructiveHint": true` (exactly the
boolean) that passes the argument check does not run. It gets an `isError` result whose text says
`confirmation required`, with `structuredContent: {"confirmation": {"token": "<token>"}}`. The
token is fresh for every challenge and never appears in the text, which a model will read. The
caller repeats the same call with `"_meta": {"notes/confirm": "<token>"}` in the params. If that
token was issued for exactly this tool and these arguments and has not been used, the call runs;
any other token gets a new challenge. A token is good once, and tokens live only in memory, so a
restarted server has issued none.
