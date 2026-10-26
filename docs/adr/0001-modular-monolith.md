# ADR 0001: Modular monolith

Status: Accepted
Date: 2026-10-25

## Context

Forgeway needs an HTTP API for learners and a grading worker that runs learner code in sandboxes.
The two have different profiles. The API is request-driven and stateless. Grading is slow,
CPU-bound and runs untrusted code, so it needs its own limits and failure handling.

We could split them into separate services from the start, or build one system with clear seams.
Phase 1 is an MVP with a small team. Deployment is deferred to Phase 4, so
the cost of running and debugging distributed services would arrive before any benefit does. The
domain is also still changing: themes, progression rules and, in Phase 4, organisations. Boundaries
are cheaper to move while everything is in one process.

## Decision

Forgeway is a modular monolith.

- One codebase, `backend/src/lattice/`, with two entrypoints over it: the API (FastAPI, stateless)
  and the grading worker.
- Layers are `domain` (pure Python), `application`, `infrastructure`, `api` and `worker`.
  Dependencies point inwards only: `api → application → domain`, with `infrastructure`
  implementing domain ports.
- Ports keep the seams open: `SandboxRunner`, `JobQueue` and the repositories. Each has one
  production implementation in Phase 1, and a different one can be added later without changing
  callers. A Cloud Run Jobs sandbox runner, the scale-up path in ADR 0010, would be the first.
- An import-linter contract runs in CI. The domain imports nothing outward. The rule is checked
  by the build rather than by review.

## Consequences

Positive:

- One deployable codebase and one set of tooling (ruff, mypy, tests) for the whole backend.
- Attempt recording, grade application and progression can share one database transaction,
  because they live in the same process against the same Postgres instance.
- Moving the worker out of the API process is a packaging and wiring change, not a rewrite.
- Ports stop infrastructure details (Docker, SQLAlchemy) from leaking into domain code.

Negative:

- API and worker share a release cadence. A bad change to shared code affects both.
- Scaling is coupled: the API and worker scale as one unit until they are split.
- The worker's Docker dependencies sit in the same codebase as the API, so the image contents need
  care.
- The import-linter contract is only as good as its listed modules. It must be maintained as
  packages are added.
- Ports with a single implementation are untested in their second form until the second
  implementation exists. Their shape may need to change in Phase 4.

## Alternatives considered

- **Microservices from day one.** Rejected. It adds deployment and operational overhead before any
  scale problem exists. It also splits attempt recording and progression across services, which
  forces distributed transactions or sagas.
- **One process with in-process background tasks.** Rejected. Grading must survive API restarts,
  scale independently and be retried. An in-memory task queue gives none of these.
- **Serverless functions per endpoint, with Cloud Tasks.** Rejected for now. It ties local
  development to GCP early, and grading still needs a durable queue and a sandbox runner, so the
  architecture would not be simpler.
