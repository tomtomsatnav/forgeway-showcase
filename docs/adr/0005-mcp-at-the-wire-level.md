# ADR 0005: MCP at the wire level

Status: Accepted
Date: 2026-10-25

## Context

The Protocols & tools branch teaches the Model Context Protocol (MCP). Exercises are graded by
hidden pytest checks in a sandbox with no network (ADR 0003), and they must be deterministic. We
needed to decide what a learner implements, what the tests use as the other end of the
conversation, and how we know that counterpart is faithful to the real protocol.

## Decision

**Learners implement the protocol, not an SDK.** Servers, clients and the pieces between them
(JSON-RPC dispatch, the `initialize` handshake, `tools/list` and `tools/call`, resources and
prompts, cursor pagination, newline-delimited stdio framing, a client that bridges tools into a
model, and defences against untrusted descriptions and results) are written against messages. An
SDK would hide exactly what the branch teaches: capability negotiation, protocol errors versus
tool errors, pagination, framing. It would also add a dependency to the sandbox image and make
checks depend on SDK internals.

**The reference implementation is grader-side, in `lattice_grader.mcp_reference`.** It provides
typed JSON-RPC 2.0 messages, an in-memory transport pair, stdio framing helpers, a child-process
transport for the one exercise where the learner's server runs as a subprocess, and a small server
and client covering the handshake, tools (including `isError`, `structuredContent` and
`outputSchema`), resources, prompts, cursor pagination and `ping`. Hidden tests use it as the
counterpart to learner code, and tests for server-side exercises assert on the messages a learner
emits. It is dependency-free, so it adds nothing to the image beyond the grader itself. It is
`mypy --strict` and unit-tested.

**`forgeway_kit.mcp` exports only what the briefs hand to learners.** That is `PROTOCOL_VERSION`,
`JSONRPC_VERSION`, the standard error codes (`ErrorCode`) and `McpError`, the exception a client
raises for an error response. Messages are plain dicts, so no message types are needed. The
reference server, client, transports, cursor helpers, schema checker and message parser are not
in the toolkit and are not documented to learners: they are exactly the behaviour the exercises
teach, and an exported `ReferenceServer` or `paginate` let a learner wrap it and pass. (An
adversarial review proved this with wrappers that passed seven exercises.) The one helper a brief
does hand over, `check_instance` in the multi-server exercise, is provided inside that exercise's
starter file rather than exported, so it cannot be borrowed by the earlier `tools-call` exercise.

**The reference is proven against the official SDK, in the grader's tests only.** The `mcp`
package (2.3.0 at the time of writing) is a dev dependency of the workspace and never enters the
sandbox image. `grader/tests/test_mcp_interop.py` runs:

- our server, in a subprocess over stdio, driven by the SDK client;
- the SDK's server, in a subprocess over stdio, driven by our client;
- every message in both directions, validated against the specification's JSON Schema.

The schema is the specification's own `schema.json` for the pinned revision, vendored unmodified
in `grader/tests/data/mcp-schema-2025-11-25.json` with its source URL in a `$comment`. We validate
each request and notification against the schema definition for its method, and each result
against the result definition for the request it answers. Deriving validation from the SDK's types
would test the SDK against itself, so the specification is the oracle.

**The pinned revision is 2025-11-25.** The SDK's `LATEST_PROTOCOL_VERSION` is 2026-07-28, but that
revision replaces the `initialize` handshake with a stateless per-request envelope
(`server/discover`, no `notifications/initialized`). The branch teaches the handshake, so we pin
the latest revision that has one, which the SDK exposes as `LATEST_HANDSHAKE_VERSION`. The
constant is `forgeway_kit.mcp.PROTOCOL_VERSION` (the reference imports it from there), and the
first exercise's brief names the revision.
Moving to the stateless revision later is a content change with its own exercises, not a reason to
rewrite this branch.

**The proof found two real divergences, which we recorded rather than hid.**

- The specification's schema leaves out the `id` of an error response that answers a message whose
  id could not be determined. JSON-RPC itself uses `null`. Our implementation omits it, and
  exercise checks accept either.
- For an unknown tool name the specification says to return a protocol error (-32602). The SDK
  server returns an `isError` result instead. Our client copes with both; our server follows the
  specification.

**The stdio exercise runs the learner's server as a child process inside the sandbox.** The grader
starts `sys.executable` on the learner's file with pipes. This works within the existing limits
(`--pids-limit 64`, read-only root, `noexec` tmpfs: the file is run by the interpreter, not
executed) and no sandbox setting changed. The child starts with `site`, so the image's `.pth`
file installs the import guard before the learner's file runs. The exercise deliberately does not set
`PYTHONUNBUFFERED` for the child, so a server that forgets to flush fails the way it would for
real.

## Consequences

Positive:

- Checks grade protocol behaviour, which is what MCP actually is, and stay deterministic.
- A wrong reference implementation would be caught by the SDK and by the schema, not by us
  agreeing with ourselves.
- Learners see the real wire format, so SDK documentation makes sense afterwards.

Negative:

- The reference implementation is more code to maintain, and the pinned revision will age. The
  interop tests will show when the SDK drops it.
- Learner code runs in the same process as the tests, so the reference is within its reach. A
  wrapper that delegates the behaviour passes whatever it is asked, and randomised inputs or
  misbehaving peers do not change that. So the reference is kept out of the learner-facing
  toolkit and every brief, with wrong cases (`wraps-reference-*`) that pin the removal, and
  importing it is refused (ADR 0003): a submission that names `lattice_grader` fails every check
  unrun, and `lattice_grader.guard` refuses the import from submission files, in the test
  process, in `run_fresh` children and in the learner's own server when the stdio exercise or
  the gateway runs it as a child process. Each exercise here has a `borrows-the-grader` wrong
  case that proves it. The guard is still in-process (its limits are listed in ADR 0003), so
  getting round it takes deliberate evasion rather than one line. A learner who does that gains
  progress on their own account only, as with any other subversion; it must be revisited with
  ADR 0003 before grades carry external weight.
- The branch teaches a handshake that the newest revision removes.

## Alternatives considered

- **Use the SDK in the sandbox.** Rejected. It hides the protocol, bloats the image, and ties
  checks to SDK internals and its async runtime.
- **Mock MCP with ad-hoc dicts in each test.** Rejected. Each mock would encode its author's
  reading of the specification, with nothing to say which reading is right.
- **Pin 2026-07-28.** Rejected for now, for the reason above.
- **Validate against the SDK's pydantic types only.** Rejected. The specification's schema was
  fetchable, and it is the authority.
