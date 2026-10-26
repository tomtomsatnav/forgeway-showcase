# Phase 1 plan — MVP

Scope (from the brief): exercise engine and grader, shared starter zone, Retrieval branch, basic
progression (XP, levels, unlocks), both presentation modes switchable via a toggle.

Out of scope for Phase 1 (designed for, not built): talent tree and classes, badges and streaks,
capstones / boss challenges, organisations, leaderboards, certificates, live-model grading,
Terraform. The schema reserves room for these so later phases are additive migrations.

Each slice is tested before it is committed: tests, `ruff`, `mypy --strict`, ESLint and `tsc`
green. The plan was reviewed independently before building; changes from that review are marked ◆.

## Decisions taken for Phase 1

- **Learner-facing toolkit (◆).** Learner code never imports grader fixtures. It imports
  `lattice_kit`, a small, stable API (`ModelClient`, `Message`, `Completion`, `Embedder`…). In the
  sandbox, `lattice_kit.default_client()` returns the deterministic fake; in Phase 4 live mode the
  same call returns a proxy-backed real client. Exercises do not change between modes.
- **Embeddings in the sandbox (◆).** Two implementations behind one `Embedder` protocol:
  `HashingEmbedder` (deterministic character n-gram hashing) for exercises where the learner
  produces arbitrary text such as chunking; `PrecomputedEmbedder` (real model vectors generated
  offline for a fixed corpus and query set, shipped as data) for exercises where dense semantics
  matter, such as dense vs hybrid search and reranking. A baked ONNX model is deferred until an
  exercise needs live dense embeddings of learner-produced text.
- **Attempt lifecycle (◆).** `queued → running → passed | failed | errored`; `errored` covers
  timeouts and sandbox faults, which are never counted against the learner. Claimed jobs record
  `claimed_at` and `worker_id`; a visibility timeout re-queues jobs from dead workers, with a
  retry cap. The grade report and its progression effects (XP events, progress) are written in one
  transaction, and `xp_events` has a unique key per (user, exercise, reason) so double-processing
  cannot double-award.
- **Versioning (◆).** `exercise_progress` is keyed by stable exercise id, so a pass on v1 still
  counts after v2 ships. Attempts are pinned to the exact version and content hash they ran
  against.
- **Tamper resistance, stated honestly (◆).** Learner code runs in the same process as the tests,
  so a determined learner can subvert grading; there is no in-process channel they cannot reach.
  Cheap real mitigations: the worker rejects reports whose check set differs from the exercise's
  or that disagree with pytest's exit status; learner files may only be the declared editable
  paths (no `conftest.py`, `pytest.ini`, `sitecustomize.py`); pytest runs with
  `-p no:cacheprovider`, `--import-mode=importlib` and a custom failure repr so hidden test source
  is never echoed. The stakes are low by design (no prizes; leaderboards are opt-in). See ADR 0003.
- **Abuse limits (◆).** One in-flight attempt per (learner, exercise) and a per-learner
  attempts-per-minute limit, enforced in the API.
- **Result delivery.** The client polls `GET /attempts/{id}` with backoff and a hard cap.
- **Starter gate.** The brief requires the starter zone to be completed first, so it gates every
  branch; it is kept deliberately tight (8–10 exercises) so the funnel stays short.
- **Mobile.** Browse, read briefs and review results on phones; the editor is optimised for tablet
  and desktop but remains operable on small screens.
- **No capstone in Phase 1.** Retrieval ships its beginner → advanced exercises; its capstone
  arrives with boss challenges in Phase 3 (`Tier.CAPSTONE` already exists in the model).
- **Deployment (◆).** Terraform for GCP (Cloud Run API and worker, Cloud SQL, Artifact Registry,
  Cloud Run Jobs sandbox) is deferred to Phase 4. Phase 1 keeps it cheap to add: twelve-factor
  config, production Dockerfiles, a `SandboxRunner` port and stateless services.

## Checklist

### 0. Foundations
- [x] Repo skeleton, uv workspace (`backend`, `grader`), npm frontend, `.editorconfig`, `.gitignore`
- [x] ruff, mypy (strict), pre-commit, import-linter contract (domain imports nothing outward)
- [x] docker-compose: postgres, api, worker, web; `.env.example`; healthchecks; migrations on start
- [x] GitHub Actions: lint, type-check, unit tests, grader integration tests, frontend checks;
      Dependabot ◆
- [x] ADRs 0001–0004 (modular monolith, Postgres queue, pytest grading + sandbox threat model,
      theme system)

### 1. Content model
- [x] Domain types: `Branch`, `Exercise`, `Tier`, `Check`, `WrongCase` (frozen Pydantic)
- [x] YAML + Markdown loader with clear errors (file and field path); content hashing
- [x] `PrerequisiteGraph`: cycles, dangling ids, branch gating, topological order, unlock queries
- [x] `lattice content validate` CLI
- [x] `tests/`, `solution/` and `wrong/` never reach the API or the database ◆

### 2. Tracer bullet ◆ — one exercise, end to end, as early as possible
- [x] `lattice_kit` (learner API) and `lattice_grader` (pytest plugin, report, fakes)
- [x] Sandbox image (non-root, minimal, pinned by digest in config)
- [x] `SandboxRunner` port + `DockerSandboxRunner`: network none, read-only root, size-capped
      tmpfs, caps dropped, no-new-privileges, default seccomp, pids/memory/CPU/nofile limits,
      wall-clock timeout, output cap; files passed in on stdin, nothing mounted
- [x] Report validation (check set, exit status, single report per nonce)
- [x] Hostile-submission tests: infinite loop, fork bomb, network, writes outside workdir, huge
      output, memory bomb, forged report
- [x] `lattice content test`: each exercise passes with `solution/`; each `wrong/` case fails the
      check it names with the expected message
- [x] One real starter exercise graded through the runner from the CLI

### 3. Persistence
- [x] SQLAlchemy 2 models + Alembic baseline: users, sessions, learner_profiles (mode, colour
      scheme, nullable `path_choice` ◆), branches, exercises (versioned), attempts,
      exercise_progress, hint_reveals, drafts ◆, xp_events (unique per user/exercise/reason)
- [x] Idempotent content sync (hash-based versioning)
- [x] Repository tests against real Postgres

### 4. Auth
- [x] Register / login / logout / me; argon2id; server-side sessions; httpOnly SameSite cookie
- [x] CSRF protection on mutating routes; login rate limit
- [x] Tests: happy paths, wrong password, duplicate email, expiry, CSRF rejection

### 5. Attempts and grading flow
- [x] `POST /exercises/{id}/attempts`: editable paths only, size caps, unlocked check, one
      in-flight per exercise, per-minute limit ◆
- [x] Postgres queue (`SKIP LOCKED`), worker loop, graceful shutdown, visibility timeout ◆
- [x] `GET /attempts/{id}` and attempt history
- [x] Progressive hints, recorded per learner
- [x] Draft autosave per (learner, exercise) ◆

### 6. Progression
- [x] XP: base XP on first pass only; no-hint bonus; never for resubmits
- [x] Level curve (pure function, property-tested monotonic)
- [x] Unlocks from the prerequisite graph
- [x] Learner map endpoint: branches, exercises, status, XP, level
- [x] Progression applied in the same transaction as the grade ◆

### 7. API contract and ops ◆
- [x] RFC 9457 problem-details error envelope
- [x] Structured JSON logs with request and attempt ids; `/healthz` and `/readyz`
- [x] OpenAPI export; generated TypeScript client; CI check that it is up to date
- [x] Seed script: demo learner with partial progress (`lattice seed-demo`)

### 8. Design system
- [x] `DESIGN.md`: tokens, type scale, spacing, components, motion, per-mode identity
- [x] Palettes for RPG and professional, light and dark; AA contrast checked (`scripts/contrast.py`)

### 9. Frontend
- [x] Vite + React + strict TS + Tailwind on tokens; TanStack Router + Query
- [x] Theme provider: mode and colour-scheme toggles, persisted per learner
- [x] Typed lexicon with pluralisation and interpolation ◆
- [x] Auth screens
- [x] Branch overview: RPG zone map vs professional track list (same data, two layouts)
- [x] Exercise workspace: brief, CodeMirror, submit, per-check results, hints, autosave
- [x] Completion moment: level-up (RPG) vs confirmation (professional); reduced-motion aware
- [x] Progress view: XP and level in the header, completion per branch (no separate page)
- [x] Vitest + Testing Library

### 10. Content (authored in parallel from slice 2 onwards ◆)
- [x] Starter zone (8–10): LLM fundamentals, prompting, tokens and context windows,
      embeddings, calling model APIs
- [x] Retrieval (10–12): chunking, vector stores, RAG, reranking, agentic RAG
- [x] RPG flavour file for both branches
- [x] Every exercise: reference solution passes; at least one wrong case fails usefully

### 11. End to end and release
- [x] Playwright: register → exercise → fail → hint → pass → XP and unlock, both modes
- [x] axe scans in both modes, light and dark; keyboard-only run-through
- [x] `docker compose up` from a clean clone (scripted check)
- [x] README for a hiring manager
- [x] Phase 1 verification report ([docs/phase-1-verification.md](docs/phase-1-verification.md)) → stop for approval

## Progress log

- 2026-10-25 — Architecture written (`docs/ARCHITECTURE.md`); Phase 1 plan drafted and reviewed
  independently; review findings folded in (◆).
- 2026-10-25 — Tracer bullet green: a starter exercise graded through the Docker sandbox; eleven
  hostile-submission tests pass. Found and fixed: parametrised tests were not mapped to checks.
- 2026-10-25 — Backend complete through the API: accounts, queue, worker, progression; the full
  journey runs through `docker compose` (`scripts/smoke.py`). 20 exercises (9 starter, 11
  retrieval); all 20 reference solutions pass and all 39 wrong cases fail as declared.
- 2026-10-25 — Worker reaps orphaned sandbox containers on start-up (gap noted in ADR 0003).
- 2026-10-25 — Independent content review: five proven cheats and one unfair check fixed;
  tool calling added to `lattice_kit`; two new exercises (tool use, agentic search). 22
  exercises, 69/69 content cases green.
- 2026-10-25 — Frontend built (two modes, four palettes), Playwright and axe suite green; dark
  mode invisible-text bug found in review and fixed with regression tests. Clean-clone check
  passed. Phase 1 complete pending approval.
