# Phase 4 verification report

Date: 2026-10-26.

## Scope

Phase 4 prepared Forgeway for a public launch. It added:

- **Learner code out of process.** The capstones, every guided-project milestone and the
  exercises whose checks compute an answer learner code could look up run `isolation: process`:
  35 of 91. There, learner code runs in a child process as a second user (10002), which cannot
  read the hidden tests or the grader package ([ADR 0009](adr/0009-out-of-process-learner-code.md)).
- **Launch safety.** Email verification, Cloudflare Turnstile, rate limits and per-account
  caps (including a daily grading-seconds budget), password reset, and a per-email login limit.
- **Operations on one VPS** ([ADR 0010](adr/0010-vps-deployment.md)):
  - grading under gVisor (`runsc`), with the worker reaching Docker only through an allow-list
    socket-proxy;
  - `deploy.sh` with rollback and a smoke test that grades a real exercise;
  - nightly age-encrypted backups with a restore drill;
  - a health check with alerts, pruning and a daily purge of expired data.
- **Privacy.** `/privacy` and `/terms`, a data export, and account deletion behind the password.
- **Freemium** ([ADR 0011](adr/0011-freemium-boundaries.md)): the foundations and the first three
  exercises of every track are free; capstones, guided projects and public certificates are Pro;
  a Pro waitlist, with no billing. On Pro, every exercise is open from the start.
- **Releases.** Release notes in `content/releases/`, shown in a What's new page (the Chronicle in
  RPG mode), and tag-based deploys.
- **Authoring tooling.** `forgeway content new`, `content review` and `content probe`, and the
  authors' guide.
- **The editor.** A Python editor that behaves like a code editor: automatic indentation,
  indentation guides, closing brackets, and completion and hover documentation for
  `forgeway_kit`, generated from the toolkit and checked for drift.
- **Phase 3 follow-ups.** Hints trimmed, guided-project XP raised, and the two capstones that
  claimed prerequisites they did not use redesigned: `graphrag-service` now integrates guarded
  text-to-query and community summaries, and `context-builder` integrates few-shot selection.

The owner deferred organisations, leaderboards, signed certificates, live-model grading and the
Terraform scale-up path.

## What was verified, and how

| Area | Evidence |
| --- | --- |
| Content | `forgeway content test`, a full run on the final commit: **612 of 612 cases**. All 91 reference solutions pass, and all 521 wrong solutions fail the check they declare, with the declared message. `content validate --require-capstones` passes (10 branches, 91 exercises, 47 talents, 24 badges, 4 release notes) and `content review` is clean |
| Backend and grader | `ruff`, `ruff format`, `mypy --strict` (117 files) and import-linter (2 contracts kept) are clean. 685 pytest tests pass, plus 12 real-container sandbox tests |
| Frontend | ESLint, `tsc` strict and the build are clean. 347 Vitest tests pass. The Playwright journeys run in CI on every push |
| Accessibility and layout | An independent UI review across both modes, four palettes and phone widths found no serious axe issues and no horizontal overflow; every finding it ranked was fixed |
| Production | Deployed to the VPS behind Cloudflare and a temporary password gate, with grading under gVisor and a 2× timeout factor. Every deploy grades the first exercise for real before it is accepted. The heaviest exercises were timed there: `project-research.team-evals` 54 s against a 60 s limit, `protocols.mcp-gateway` 13–14 s. The other site on the same VPS stayed up throughout |
| Screenshots | Both modes, in [docs/screenshots/phase-4/](screenshots/phase-4/) |

## Reviews

- **Adversarial content review.** Every exercise moved out of process had its earlier probes
  re-run and gained a `cheat-*` wrong case. Both redesigned capstones were attacked by a reviewer
  trying to pass without doing the work: four shortcuts in `graphrag-service` and four plausible
  mistakes in `context-builder` became permanent wrong cases, and one unfair check (two
  equally similar examples) and two unstated rules were fixed in the briefs.
- **Fable's end-of-phase review.** Its verdict before fixes was "not yet". It found one blocker,
  three high and six medium issues, mostly in the out-of-process bridge and the socket-proxy
  rules. All were fixed and deployed, among them:
  - the bridge counting output as activity;
  - write operators and property values crossing the bridge unguarded;
  - predictable handle ids.

  Separately, one deploy left the socket-proxy on its old rules and production grading broke until
  it was restarted. Every deploy and rollback now restarts it and grades a real exercise.
- **Rename sweep.** A separate low-cost model searched the repository for "Lattice". Nothing a
  learner or reader sees is left. Internal names stay: the Python packages, `LATTICE_*` settings,
  the session cookie (renaming it would sign everyone out) and the production database user and
  name (renaming them needs a migration).

## Not verified, or verified only partly

- **Real learners.** Nobody outside the owner's friends has used the site.
- **Email.** Sending is built and tested against a fake, but no real email has been sent: the
  Resend key and a verified domain are the owner's to add.
- **Turnstile.** Built and tested; off until the owner adds the keys.
- **Off-site backups and alerts.** Backups are encrypted and restorable, but live on the VPS
  until the owner creates a bucket. Alerts go to the journal until a webhook is set.
- **Load.** One worker, one or two concurrent sandboxes. No load testing.
- **Screen readers.** Checked structurally (axe, roles, names, live regions), not with a real
  screen reader.

## Before public sign-up (the owner's)

1. A Resend key and a verified sending domain.
2. A real `privacy@forgeway.dev` inbox, and a read of `/privacy` and `/terms`.
3. The ICO data-protection fee.
4. Then: remove the password gate.

Soon after: Turnstile keys, an alert webhook and an outside uptime check, an off-site backup
bucket, a copy of the backup key in a password manager, and the first release tag.

## Known limitations and follow-ups

- **In-process exercises.** 56 exercises still run learner code in the same interpreter as the
  hidden checks, so a determined learner could tamper with the harness there. Process mode as
  the default is the next step.
- **Scripts the tests start** (the MCP gateway and research-team tool servers) run as the
  harness's user, not the learner's.
- **The bridge** has no per-message time limit; a slow learner call is bounded only by the
  exercise's overall timeout.
- **Seed-dependent helpers** in three exercises (`community-summaries`, `red-team-suite`,
  `context-compaction`): deterministic today, but their fixtures depend on a seeded generator.
- **`graphrag-service`** still claims `hybrid-graph-retrieval` without using it.
- **Slow under gVisor.** `team-evals` runs within 10% of its time limit in production. The
  redesigned capstones grade there in 12 s (`graphrag-service`) and 22 s (`context-builder`,
  limit 60 s), over the authors' 15-second guideline.
