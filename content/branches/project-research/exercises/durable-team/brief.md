# Milestone 3: a durable research team

**So far.** Milestone 1 gave the team its MCP servers: `search_server.py` (`search`, `fetch`) and
`notes_server.py` (`add_note` with an idempotency `key`, `list_notes`, a confirmed
`delete_note`), sharing `mcp_server.py`. Milestone 2 added `knowledge.py`: a `KnowledgeGraph`
that extracts typed, quoted, dated facts from fetched documents and saves itself as JSON. All of
it is in your workspace, and this milestone runs on it: the tests start your servers and the team
builds your graph. One check also holds them to everything milestones 1 and 2 promised, such as
argument checks, confirmation, pagination, date checks, entity ids, intervals and saving.

**This milestone** adds the team itself, in `client.py` and `team.py`. A question arrives. A
router picks which search server to use, a planner splits the question, workers research the
parts at the same time with that server's tools, what they fetched becomes a knowledge graph, and
a writer turns the findings and facts into a report. The report is filed as a note, but only once
a person has said yes. The run has one budget, survives being killed at any moment, and never
files a report twice.

```text
question ─► router ─► planner ─► workers (parallel) ══ search server
                                   │ fetched documents
                                   ▼
                     knowledge graph (milestone 2) ─► writer ─► waiting ─► person says yes
                                                                              │
              every reply and tool result is saved the moment you have it     ▼
                                                              add_note(key=run id) ══ notes server
```

It draws on **A router**, **Orchestrator–workers**, **Parallel fan-out and aggregation**,
**Handoffs that carry the right context**, **Checkpoint and resume**, **Human-in-the-loop
interrupts**, **An agent loop with budgets** and **The durable research desk**, and on **Bridging
MCP tools into a model** and **Untrusted tool descriptions and results** for the workers.

## `client.py`

`McpClient(argv)` starts the server, completes the `initialize` handshake (revision
`2025-11-25`) and is then ready. It has `request(method, params=None)`, `list_tools()` (following
`nextCursor`), `call_tool(name, arguments, meta=None)` returning the result dict, and `close()`.
A JSON-RPC error raises `McpError(code, message, data)` with the error's own values. Workers share one client per server from several threads, so
send one request at a time. `StdioTransport` is provided.

## `team.py`: `run_team`

`run_team(client, run_id, question, *, servers, sources, ontology, store, limits=None,
approve=None)` returns a dict `{"status", "source", "plan", "failed", "report", "note", "steps",
"tokens"}`. `servers` maps a server name to the argv that starts it: `"notes"` and one search
server per source. `sources` maps each source's name to a description. `store` is a dict of
strings. `limits` is a `Limits` (in the starter), or `Limits()` when it is `None`. Use the four
system prompts in the starter exactly as they are.

1. **Route.** One call: system prompt `ROUTER`, a newline, then `name: description` for each
   source on its own line, in order; the only message is the question; `max_tokens` at most 32,
   `temperature` 0, no tools. `source` is the first source named in the reply as a whole word
   (no letter, digit, `_` or `-` touching either end), ignoring case, or the first source when
   none is.
2. **Plan.** One call: system prompt `PLANNER`, the question as the only message. Remove a
   ```` ``` ```` or ```` ```json ```` fence and parse a JSON list of strings. Anything but a
   non-empty list of non-blank strings raises `PlanError`, before any worker runs or any server
   starts. Trim each subtask, drop repeats (keep the first), keep at most `limits.max_subtasks`.
3. **Work.** One worker per subtask, at most `limits.max_workers` at a time, all sharing one
   client to the chosen source's server. A worker is a tool loop: system prompt `WORKER`, the
   server's tools as `Tool(name, description, inputSchema)` exactly as `tools/list` gives them,
   and one first message, `Question: <question>` and `Subtask: <subtask>` on two lines. Answer
   each tool call in order with a `tool` message: `<tool-result>`, a newline, the result's text
   blocks joined with newlines (prefixed `error: ` when `isError`), a newline and
   `</tool-result>`. A reply with no tool calls is the
   worker's **finding**. A worker that has made `limits.worker_steps` calls without one fails
   with a message mentioning `worker_steps`; a `ModelError` fails it with the error's message.
   Either way the others carry on. `failed` maps each failed subtask to its message. If every
   worker failed, the status is `failed` and nothing more happens.
4. **Graph.** The `structuredContent` of every successful `fetch` is a document. Ingest each one
   once, in order of document id, into a new `KnowledgeGraph(ontology)` with your milestone 2
   `ingest` (its model call is part of the run). A document whose extraction raises `ValueError`
   is skipped.
5. **Write.** One call: system prompt `WRITER` and one user message, the briefing:

   ```text
   Question: <question>
   Findings:
   - <subtask>: <finding>                    (each answered subtask, in plan order)
   Unanswered: <failed subtasks joined with "; ">              (only if any failed)
   Facts:
   [1] <subject> | <predicate> | <object> | since <valid_from> | docs <doc ids joined with ", ">
   ```

   The facts are the graph's current `facts()`, numbered from 1 in that order, with each fact's
   source documents in order; with no facts the line after `Facts:` is `(none)`. The writer
   never sees a document or a tool result. Its reply is the `report`.
6. **Approve.** Then the run waits: status `waiting`, with the report, and nothing reaches the
   notes server. A person answers by calling `run_team` again with the same `run_id` and
   `approve=True` or `False`. `True` files the report with one `add_note` call, `{"topic":
   <source>, "text": <report>, "key": <run_id>}`, and the status becomes `done` with `note` the
   note's id. `False` gives `rejected` and files nothing. Calling with `approve=None` on a waiting
   run returns the same outcome and makes no call. `approve` for a run that does not exist or is
   not waiting raises `RuntimeError`. A finished run returns its outcome again and calls nothing.
7. **Budgets.** `steps` is the number of model replies the run has received, extraction and
   workers included, and `tokens` their input plus output tokens. Never start call number
   `max_steps + 1`, even with workers asking at the same time, and never start a call once
   `tokens` is more than `token_budget`. A refused call stops the run with status `max_steps` or
   `token_budget`; calls already in flight may finish, but nothing new starts.
8. **Survive.** Keep the whole record of the run in `store[run_id]` as JSON text, saved after
   each model reply, each tool result, the pause and the decision. If `store` holds `run_id`,
   carry on from it: the saved question wins, and nothing recorded is done again: no model call,
   no tool call, no worker. The tests run each later step in a new Python interpreter that is
   handed only a copy of the store that has been through JSON, so nothing may survive in memory,
   on `sys`, in `builtins` or in the environment. A `BaseException` that kills the process propagates, leaving the record valid. A process can
   die after the notes server filed the report but before your record saw the reply; the key
   makes the second `add_note` harmless. `steps` and `tokens` cover every process that worked on
   the run.
