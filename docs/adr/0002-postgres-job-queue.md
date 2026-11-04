# ADR 0002: Postgres as the job queue

Status: Accepted
Date: 2026-10-25

## Context

Grading is asynchronous. `POST /attempts` records work, a worker runs it in a sandbox for up to
tens of seconds, and the learner polls for the result. Three things must hold:

- Recording the attempt and enqueueing it are atomic. A queued job without an attempt, or an
  attempt that is never graded, is a bug.
- The grade and its progression effects (XP events, unlocks, milestones) are applied in one
  transaction, and exactly once per exercise.
- A worker that dies mid-run does not leave the attempt stuck.

Phase 1 load is modest: one in-flight attempt per learner and exercise, plus a per-learner
attempts-per-minute limit enforced in the API.

## Decision

Use the PostgreSQL database that already holds users and progress as the job queue.

- The `attempts` row is the job. Its status moves `queued → running → passed | failed | errored`.
- Enqueueing is the insert of that row, in the same transaction as the request's other writes.
  There is no separate message.
- A worker claims work with `SELECT … FOR UPDATE SKIP LOCKED` on a queued row. It sets `running`,
  `claimed_at` and `worker_id`, and commits. The claim transaction is short. The sandbox run
  happens outside any transaction, so no row lock is held while code is graded.
- Visibility timeout: a `running` attempt whose `claimed_at` is older than the timeout is
  re-queued. Each re-queue counts against a retry cap. An attempt past the cap is `errored`.
  Neither case counts against the learner.
- The grade report and its progression effects are written in one transaction. `xp_events` has a
  unique key on (user, exercise, reason), so processing the same grade twice cannot award XP twice.
- Attempts are pinned to the exact content version and hash they were graded against.

## Consequences

Positive:

- No additional service to run, monitor or secure in Phase 1.
- Enqueue and grade application are transactional with the data they affect.
- Queue state is ordinary SQL. Stuck, retried and errored attempts can be inspected with a query.
- Retry and error history is kept on the attempt itself.

Negative:

- Queue traffic shares the Postgres instance with API reads and writes. The claim query needs a
  suitable index on status and creation time, and it must be checked under load.
- Workers poll. Pickup latency is bounded by the poll interval, not by a push notification.
- A worker can lose its claim (timeout, network partition) and still finish. The grade write must
  check that the claim still belongs to that worker, so a stale result cannot overwrite a
  re-queued attempt. This is a requirement on the repository, and it needs a test.
- Visibility-timeout re-runs mean a job can run more than once. Idempotent writes (the unique XP
  key, one report per nonce) make that safe.

If queue throughput ever becomes a constraint, the `JobQueue` port allows a dedicated broker. The
transactional guarantee against attempts would then need an outbox pattern.

## Alternatives considered

- **Redis with RQ or Celery.** Rejected. It adds a service to run in Phase 1. Enqueueing would not
  be transactional with the Postgres writes, so it needs either an outbox or a dual write.
- **Google Cloud Tasks.** Rejected for Phase 1. It is managed, but it is not transactional with the
  database, it ties local development to a GCP emulator or a cloud project, and it still needs a
  result store.
- **Amazon SQS or RabbitMQ.** Rejected for the same transactional reason, plus an extra service or
  cloud dependency.
