# Phase 2 plan

Scope (from the brief): the Protocols & tools (MCP) and Orchestration branches; the talent tree
and classes; badges and streaks. Phase 1 was approved on 2026-10-25; its plan and log are in
[docs/plans/phase-1.md](docs/plans/phase-1.md). Phase 1 follow-ups folded in here: resizable
workspace panes and a world view for the RPG atlas.

Out of scope (Phase 3+): boss challenges and capstones, the remaining branches, organisations,
leaderboards, certificates, live-model grading.

The same rules as Phase 1 apply: each slice is tested before it is committed, and the gates
(`ruff`, `mypy --strict`, import-linter, ESLint, `tsc`, Vitest, pytest, content tests) stay green.

## Decisions

### Content

- **MCP is taught at the wire level.** `lattice_grader.mcp_reference` (grader-side, not part of
  the learner toolkit) provides JSON-RPC 2.0 message types, an in-memory transport pair,
  newline-delimited stdio framing and *reference* MCP server and client implementations that
  hidden tests use as the counterpart; `lattice_kit.mcp` exports only constants and `McpError`. Learners implement servers and
  clients against the protocol, not an SDK: it is deterministic, adds nothing to the sandbox
  image and teaches what SDKs hide (handshake, capability negotiation, protocol errors versus tool
  errors, pagination, framing). ADR 0005.
- **The reference implementation is proven against the official SDK (◆).** The grader's test
  suite (never the sandbox image) depends on the official `mcp` Python SDK and runs our reference
  server against the SDK client and the SDK server against our reference client, and validates
  every message against the specification's JSON schema. The spec revision is pinned
  deliberately to the latest the SDK supports and named in the branch briefs.
- **Tracer bullet first (◆).** One stdio exercise (learner server as a child process inside the
  sandbox: pids limit, read-only root, stdin already carrying the submission) is graded through
  the real `DockerSandboxRunner` before the rest of the branch is authored.
- **Protocols & tools branch (`protocols`, 9–10 exercises)**:
  - JSON-RPC dispatch.
  - The initialise handshake with version and capability negotiation.
  - `tools/list` with input schemas.
  - `tools/call`: argument validation, `isError` results versus protocol errors.
  - Resources and prompts: the remaining two server primitives.
  - Cursor pagination.
  - Stdio framing (stdout carries only protocol messages; logs go to stderr).
  - A client that bridges MCP tools into a model's tool calls.
  - Untrusted tool descriptions and results (◆): delimit tool output, never obey instructions
    embedded in it, asserted on what reached the prompt.
  - Structured output (`outputSchema` / `structuredContent`) and a multi-server client with
    namespacing.
- **Orchestration branch (`orchestration`, 9–10 exercises)**:
  - An agent loop with step and token budgets and loop detection, as one exercise (◆).
  - A router.
  - Prompt chaining with gates.
  - Parallel fan-out and aggregation. Graded on the *set* of requests and on the aggregation,
    never on ordering, because thread scheduling is non-deterministic (◆).
  - Evaluator–optimiser.
  - Orchestrator–workers.
  - Handoffs that carry the right context.
  - Checkpoint and resume, proving side-effecting tools are not re-executed (◆).
  - Human-in-the-loop interrupts.
  - Context compaction in a long loop (◆). `FakeModel`'s context window already fails
    oversized requests.

  All of these run on `FakeModel` responders, which already receive the system prompt and tools,
  so no role-keyed extension is needed (◆).
- **Both branches require only the starter zone**, so after it the learner chooses among
  Retrieval, Protocols and Orchestration.

### Progression

All new progression rules live in `lattice.domain.progression` as pure functions; the
application layer feeds them facts and persists their outputs in the grading transaction.

- **Paths and classes.** A path is `generalist` (the default) or a specialisation, stored in
  the reserved `learner_profiles.path_choice`. Each specialisation is defined in content
  (`content/progression/classes.yaml`) with a stable id, a home branch and its own talent
  subtree. The domain never says "class".

  | Path | Home branch | RPG class | Professional name |
  | --- | --- | --- | --- |
  | `generalist` | — | Wayfarer | Generalist |
  | `retrieval` | Retrieval | Loremaster | Retrieval specialist |
  | `protocols` | Protocols & tools | Artificer | Integration specialist |
  | `orchestration` | Orchestration | Conductor | Systems specialist |

  A path can be chosen once the starter zone is finished, and changing it is free. Changing it
  drops the allocations in the old subtree, refunding their points.
- **Talents recognise demonstrated skill and never touch scoring (◆).** XP stays a clean signal
  of passed work: with free respecs, any scoring effect would just be respecced into before each
  pass.
  - **Points:** one talent point per level from level 2. Points are derived from XP, never stored.
  - **Node requirements:** each node requires a minimum level, its parent nodes and *passed
    exercises*. You cannot take "Hybrid ranking" without passing hybrid search.
  - **Effects** come from a closed set the engine implements:
    - `title`: a title shown on the profile.
    - `reference_solutions(branch)`: lets the learner read the reference solution, with its
      notes, for exercises they have already passed in that branch.
  - **Shared tree:** a general subtree is open to every path. Class subtrees need that path.
- **Badges** are content-defined (`content/progression/badges.yaml`), with criteria from a
  closed set: `branch_complete`, `exercises_passed(n)`, `first_try(n)`, `no_hint_passes(n)`,
  `streak_days(n)` and `level_reached(n)`.
  - They are evaluated on **every graded attempt**, passed or failed, inside the grading
    transaction (◆).
  - They are stored as append-only `badge_awards`, unique per (user, badge), with the
    `attempt_id` that earned them.
  - They are never revoked.
- **Streaks count learning days (◆).**
  - **Stamping:** each attempt is stamped at submission with `local_day`, its date in the
    learner's IANA time zone at that moment. Editing the zone later never rewrites history.
  - **Learning day:** a `local_day` with at least one graded attempt. *Errored* attempts never
    count. An attempt whose files are byte-identical to an earlier attempt on the same exercise
    does not count either, so a junk resubmission cannot keep a streak alive.
  - **Current streak:** consecutive learning days ending today or yesterday, in the learner's
    current zone. Current and longest streaks are pure date arithmetic over the stored days.
  - **Time zone:** set from the browser at registration, editable on the profile, validated
    against `zoneinfo`, and UTC by default. There is no freeze mechanic.
- **Completion payload.** The grading result's progression payload gains `badges_awarded`,
  `talent_points_gained` and `streak`; failed attempts can carry badges and the streak too.
- **ADR 0006** records the progression decisions: non-scoring talents, the streak definition and
  badge evaluation.

### Certificates (pulled forward from Phase 4 at the product owner's request, 2026-10-25)

- **Issuing.** A certificate is issued when a learner completes a branch (every exercise
  passed), starter included. It is created in the grading transaction and is idempotent, unique
  per (learner, branch). Learners who completed a branch before this shipped get theirs on first
  listing.
- **Contents.** Each certificate snapshots what it attests: the recipient's name (editable by the
  owner), the branch title, the number of exercises and the issue date. It is never revoked
  automatically, even if the branch later gains exercises.
- **Private by default.** The owner makes a certificate public to share it. Its public id is
  random and unguessable. A public certificate has a server-rendered verification page at
  `/c/{id}` with OpenGraph tags and a 1200×627 PNG image (`/c/{id}.png`). Professional styling
  only, since the audience is hiring managers. No email or other account data is exposed.
- **LinkedIn.** The frontend offers *Add to profile*, LinkedIn's add-certification URL
  prefilled with name, organisation, issue date, credential id and URL, and *Share post* (the
  share-offsite URL). Absolute URLs come from `LATTICE_PUBLIC_BASE_URL`. LinkedIn can only
  render the preview once the site is publicly reachable, which arrives with deployment in
  Phase 4.
- **Phase 4 keeps** organisation-issued certificates and signed or PDF certificates.

### Interface

- **Profile page** (`/profile`): level, class, talent tree, badges and streak. RPG calls it the
  *character sheet*; professional mode calls it *profile*. It is one page with shared components
  and a lexicon-driven vocabulary.
- **Talent tree slot.** RPG renders a constellation-style tree on parchment or night. Professional
  renders a competency matrix: an accessible table of skills with requirement and state columns,
  which is also the RPG mode's accessible equivalent (◆). That makes two renderers, not three,
  and allocation is fully keyboard operable in both.
- **World atlas.** RPG's overview becomes one world map: the starter vale in the centre, with
  routes to three zones. Selecting a zone shows its existing route of quests. Professional keeps
  the syllabus.
- **Resizable workspace.** Brief, editor and results get keyboard-operable splitters (WAI-ARIA
  `separator` with arrow keys). Sizes persist per viewer, and the workspace uses the full width.

## Checklist

### 0. Housekeeping
- [x] Dependabot: actions/checkout v7, setup-uv v7, uvicorn 0.54, psycopg 3.3.6 applied; Python
      3.15 sandbox bump declined (keep 3.12 with the backend)
- [x] Phase 1 plan archived to `docs/plans/phase-1.md`
- [x] Plan reviewed independently; changes marked ◆
- [x] Resizable workspace panes (keyboard splitters, persisted sizes, full width)

### 1. Progression engine (backend)
- [x] Domain: paths, talent tree validation (cycles, unknown exercises and branches), allocation
      and respec rules, talent points from level
- [x] Domain: badge criteria evaluation; streaks from stored local days (Hypothesis tests);
      stamping `local_day` across DST and zone edges
- [x] Content: `classes.yaml`, `talents.yaml`, `badges.yaml`, validated by `lattice content
      validate`
- [x] Persistence: migration for `talent_allocations`, `badge_awards` (with `attempt_id`),
      profile `time_zone`, attempt `local_day` and a files hash for duplicate detection
- [x] Application: choose a path, allocate and respec talents, award badges on every graded
      attempt in the grading transaction, gate reference solutions on the talent
- [x] API: profile, talents, badges and reference-solution endpoints; enriched progression
      payload; OpenAPI regenerated
- [x] `lattice seed-demo` gives the demo learner a path, allocations, badges and a live streak
- [x] ADR 0006 (progression)

### 2. Protocols & tools branch
- [x] `lattice_grader.mcp_reference` (JSON-RPC types, transports, stdio framing, reference server
      and client; grader-side) and the small `lattice_kit.mcp`
      with unit tests; sandbox image rebuilt
- [x] Interoperability tests against the official SDK and the spec schema (grader tests only)
- [x] Tracer bullet: one stdio exercise graded through the real sandbox
- [x] ADR 0005
- [x] Remaining exercises (9–10 in all), each with solution and wrong cases; `lattice content
      test` green
- [x] RPG flavour: zone and quest titles

### 3. Orchestration branch
- [x] 9–10 exercises, each with solution and wrong cases; `lattice content test` green
- [x] RPG flavour: zone and quest titles

### 4. Content review
- [x] Independent cheat and fairness review of both branches; findings fixed and re-proven

### 5. Frontend
- [x] RPG world atlas, with an accessible list equivalent
- [x] Profile and character sheet: class choice, talent tree slot (both modes), badges, streak
- [x] Completion moment shows badges, talent points and the streak
- [x] Vitest coverage for the new components; lexicon entries for every new term; contrast
      script covers any new tokens (no new tokens were needed)

### 5b. Certificates
- [x] Backend: model, migration, issuing in the grading transaction and lazily, owner API (list,
      publish or unpublish, recipient name), public JSON, verification page with OpenGraph tags,
      PNG image, nginx route; tests incl. HTML escaping and private → 404
- [x] Frontend: certificates on the profile, the completion moment links to the new
      certificate, publish toggle, LinkedIn *Add to profile* and *Share post*; Vitest and e2e

### 6. End to end and release
- [x] Playwright: choose a class, earn a level, allocate a talent, earn a badge, streak shown;
      axe on the profile and world atlas in all four palettes; keyboard allocation; mobile
- [x] Every exercise attempted with correct and wrong solutions (content test, CI)
- [x] Clean checkout → `docker compose up` → smoke and e2e pass; CI green
- [x] Screenshots, README, ARCHITECTURE and verification report updated

## Progress log

- 2026-10-25 — Phase 1 approved. Phase 2 plan drafted and reviewed independently. Accepted: non-scoring
  talents, SDK interoperability proof, an MCP tracer bullet, badges on every graded attempt,
  stamped local days, duplicate-submission rule, tool-poisoning, compaction and idempotent-resume
  exercises, fewer budget exercises, two talent renderers. Declined: deferring resizable panes
  (already built and merged).
- 2026-10-25 — Progression engine (backend) built: paths, talent tree, badges, streaks, migration,
  API and demo seed, ADR 0006. Only the `retrieval` path and its talents are defined.
- 2026-10-25 — Orchestration (10 exercises) and Protocols & tools (10 exercises, MCP revision
  2025-11-25: the latest revision with the initialise handshake; the SDK's newest, 2026-07-28, is
  stateless) merged. Paths, talent subtrees, RPG class names and completion badges added for
  both. Certificates backend merged.
- 2026-10-25 — Independent cheat reviews of both new branches; every proven cheat and unfair
  check fixed and re-proven. Certificates (brought forward), profile and talent screens, polish
  from visual review. Phase 2 complete and verified ([report](docs/phase-2-verification.md));
  awaiting sign-off.
