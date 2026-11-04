# ADR 0007: Capstones and bosses

Status: Accepted
Date: 2026-10-26

## Context

Every branch so far ends with an advanced exercise, which is graded like any other. Phase 3 adds a
closing project to each branch: a capstone, larger than the exercises before it, that can only be
reached by passing all of them. In the RPG theme the capstone is a boss. The pieces are already
there (`Tier.CAPSTONE`, certificates, badges, theme flavour), so the questions are about rules.

- A capstone that does not depend on the rest of its branch is just a big exercise that can be
  skipped to.
- Anything that depends on a capstone makes it a gate, and a gate on a project is a different
  product.
- Capstones are the heaviest checks in the sandbox. Without limits, one could starve the others.
- Capstones will be added branch by branch, so the rules cannot require them all on day one.
- Certificates are issued on branch completion. Adding a capstone to a completed branch changes
  what "complete" means after the fact.

The domain must stay theme-agnostic (ADR 0004): it says capstone, and never "boss" or "lair".

## Decision

**Capstone rules** are checked when content loads, in `PrerequisiteGraph`, which collects every
problem rather than stopping at the first:

- A branch has at most one capstone.
- The root branch, the one that requires nothing, has none. It is the way in, and a capstone
  there would sit in front of every other branch. The rule is stated by structure, not by naming
  `starter`.
- A capstone's transitive prerequisites include every other exercise in its own branch.
- No exercise lists a capstone as a prerequisite. Other branches reach it only through `requires`.
- XP is 300 to 400 inclusive, and limits are at most 60 s and 512 MB. Ordinary exercises may go to
  the schema's 120 s and 2048 MB, but those are not meant for a project.

The completeness rule, that every branch which requires another has exactly one capstone, is a
keyword argument of the graph, `require_capstones`. Its default, the module constant
`REQUIRE_CAPSTONES`, stays `False`, so small test graphs need no capstones and both modes are
tested. The shipped content is held to the rule by `forgeway content validate
--require-capstones`, which CI's sandbox job and `make content-check` run: every branch
but the root now has its capstone, and a new branch without one fails the build. The constant is
not flipped.

**Ordering.** A capstone sorts last in its branch. The tier rank already puts it after every other
tier among exercises that are ready, and the prerequisite rule means everything else in the branch
is done first, so the order needs no special case.

**Completion.** A branch is complete when every exercise in it, the capstone included, is passed.
Nothing else in progression changes: XP is awarded once, on first pass, as for any exercise, and
the only bonus is the existing no-hint bonus. The new badge criterion `capstones_passed(n)` counts
passed capstone exercises.

**Certificates snapshot the claim.** `includes_capstone` is recorded when a certificate is issued,
from whether the branch has a capstone at that moment. The verification page and image say
"including its capstone project" only when it is true. Like the rest of the snapshot it never
follows later content changes.

**Boss flavour** lives in the RPG theme's `flavour.yaml` under `bosses:`, keyed by capstone
exercise id, each with `name`, `epithet`, `lore` and `defeat`. Loading rejects a key that is not a
capstone exercise, and unknown fields. Flavour is presentation only; nothing in grading or
progression reads it.

**Retro-fit.** Capstones are added to branches that learners have already completed.

- Re-opening: the branch is no longer complete, its dependants relock if they require it, and the
  capstone is available at once because the rest of its branch is passed. Passes are never undone.
- Certificates and badges persist. They are append-only records of what was true when they were
  earned, and are never revoked.
- Old certificates have `includes_capstone` false (the migration sets existing rows so) and render
  as before, with no mention of a capstone. Passing the capstone later does not issue a second
  certificate, because there is one per learner and branch.

**Trust.** Capstones and certificates still rest on in-process grading (ADR 0003): learner code
runs in the same process as the hidden tests. A capstone is a harder exercise, not a more secure
one. Phase 4 moves the harness out of process, and until then a certificate attests to passing the
checks, with no stronger claim.

## Consequences

Positive:

- A capstone is a real test of the whole branch, since nothing earlier can be skipped.
- Authors get every capstone mistake in one validation run.
- The rollout could proceed one branch at a time, and the CI flag now turns a missing capstone
  into a failure.
- Old certificates stay true, with no data rewrite.

Negative:

- Learners who finished a branch find it open again when its capstone lands, and a dependent branch
  may relock until they pass it. We accept that, since the alternative is a branch that is complete
  without its project.
- A certificate issued before a capstone existed cannot be upgraded, so it says less than a new one.
- The capstone's limits and XP are a range, not a measure of effort. Authors have to judge size.
- Until Phase 4, a capstone can be passed by subverting the harness, as any exercise can.

## Alternatives considered

- **Naming `starter` in the rule.** Rejected. "Requires nothing" says the same thing without a
  magic id, and keeps the domain free of content names.
- **Letting exercises depend on a capstone.** Rejected. It turns a project into a gate.
- **Grandfathering completed branches.** Rejected. It needs a per-learner record of which version of
  a branch was completed, for a one-off gain. Re-opening is simple and honest.
- **Issuing a new certificate when the capstone is passed.** Rejected. Uniqueness per learner and
  branch is what makes issuing idempotent, and a second credential for one branch would confuse
  the people who check them.
- **An `is_capstone` field in the API.** Rejected. `tier` already says it.
- **Requiring capstones from the start.** Rejected. It would block the build until all seven
  branches have one.
