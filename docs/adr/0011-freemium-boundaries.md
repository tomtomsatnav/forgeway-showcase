# ADR 0011: Freemium boundaries, and no billing yet

Status: Accepted; amended 2026-10-26 (free learners unlock on the free exercises; Pro unlocks everything, below); billing amended 2026-11-03 (below); Pro content withheld 2026-11-03 (below); primers and Python notes 2026-11-04 (below)
Date: 2026-10-26

## Context

Forgeway launches publicly in Phase 4a. The owner wants a free tier generous enough to learn
from, a paid tier for the work that makes a portfolio, and no spending or selling until there
is demand. The independent review (PLAN.md, 2026-10-26) settled the line: the foundations plus
the first exercises of every track are free; capstones, guided projects and certificates are
Pro; there is a waitlist, with no pre-order wording.

## Decision

- **Plans live in the domain.** `Plan` is `free`, `pro` or `team`, stored on the account and
  defaulting to `free`. Team carries the same entitlements as Pro until organisations exist.
- **The boundary is a rule over the content graph, not a list.** Free covers every exercise in a
  root branch and the first N exercises of every other standard branch in its stable order
  (N = 3, a setting), never a capstone. Guided projects are wholly Pro, and so is publishing a
  certificate. New content falls on the right side without anyone tagging it.
- **Locked by plan is separate from locked by prerequisites**, and checked first, so a free
  learner is told about Pro, not about prerequisites they could never clear on the free plan.
- **Enforced on the server; visible everywhere.** Attempts and publishing answer 403
  `plan-required`. Briefs stay readable, and Pro content carries a "Pro" mark in both modes (in
  RPG, "Guild · Pro"), so nothing is a paywall surprise.
- **Progress is never taken away.** Existing accounts become free; anything already passed, and
  any certificate already public, stays so.
- **No billing yet.** The waitlist records the email, plan of interest and time, once per
  learner; the owner exports it as CSV. Nothing is charged, no price is shown and no email is
  sent. The owner grants Pro by hand with `forgeway accounts set-plan`.
- **The future integration is a merchant of record** (Paddle or Lemon Squeezy). It handles VAT
  and sales tax, invoices and refunds, which a one-person business should not. It will call back
  a webhook that sets `users.plan`; nothing else in the entitlement model changes. It is built
  only on the owner's say-so.

## Consequences

- One function (`free_exercises`) decides the line, and unit tests pin its boundaries.
- A branch that requires a non-root branch (Knowledge graphs requires Retrieval) could not be
  unlocked on the free plan as first built, because completing Retrieval needs its capstone: its
  first exercises showed as free but locked by prerequisites, for ever.
- **Amendment (2026-10-26): free learners unlock on every free exercise passed.** For a free
  learner, the exercises their plan includes are judged with Pro exercises counted as done, so
  Knowledge graphs opens once Retrieval's free exercises are passed. Pro exercises are still
  judged on what was passed, so nothing behind the plan looks open, and a passed exercise is
  always the learner's own record. The graph is unchanged; the rule lives in the application
  layer (`plans.Unlocks`) and covers the map, the exercise page, attempts, hints, the "unlocked"
  list after a pass and the choice of a specialisation path. A paid learner still needs the
  whole required branch, capstone included: a free learner who upgrades keeps everything they
  passed, but the Pro exercises past the free ones wait for the required branch's capstone.
- **Amendment (2026-10-26, owner's decision): Pro unlocks everything.** A paid learner has every
  exercise and branch open, whatever they have passed, so an upgrade never leaves anything
  waiting on a capstone. Prerequisites still order the map and gate the free plan; on Pro they
  are guidance, not locks. The exception is a guided-project milestone: its starter is the
  previous milestone's reference solution (ADR 0008), so it opens, and its starter is shown, only
  once that milestone is passed, on every plan.
- Changing N changes the free tier for everyone at once, including learners midway through a
  track. Lowering it never removes progress, only the next attempt.
- Until billing exists, `plan` is set by hand, so it is not a revenue record.

## Amendment (2026-11-03): billing through Stripe

The owner chose Stripe (Checkout, Billing and Stripe Tax), with the owner as seller of record,
over a merchant of record; the decisions are in a private plan.
The entitlement model is unchanged: webhooks mirror the subscription into `subscriptions` and set
`users.plan` from its status (`trialing`, `active`, `past_due` are Pro; anything else, or a paused
collection, is Free). Billing is off until the Stripe keys are set, and the waitlist stays as
described above while it is. `forgeway accounts set-plan` still works, for Team and for grants.

## Amendment (2026-11-03): Pro content stays on the server

Owner's decision: a free learner has no access to Pro content in any form. This replaces "Briefs
stay readable" above. Off a paid plan, a Pro exercise shows only what the map and the public
catalogue show (title, tier, XP, skills and the Pro mark): `GET /api/exercises/{id}` answers with
an empty brief, no files, checks or hints; saving or resetting its draft, downloading it, hints,
attempts, live runs and its reference solution answer 403 `plan-required`, and that message names
nothing from the exercise. Entitlement is read from `users.plan` on every request, so a learner
whose subscription ends loses Pro content at once, though everything they passed stays passed.
A boss's lore and defeat text (RPG flavour for a capstone) go only to a paid learner; its name and
epithet stay public, like titles.

## Amendment (2026-11-04): primers are free; Python notes are not

A `kind: primer` branch requires nothing, so `free_exercises` includes all of it, as it does a root
branch, without touching any track's allowance. Its exercises are never Pro. An exercise's
`python.md` ("Python you'll need") is paid content on the same terms as its brief: it reaches a
learner only when they are entitled to that exercise, in `GET /api/exercises/{id}` and the download.
