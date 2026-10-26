# ADR 0006: Progression: talents, badges and streaks

Status: Accepted
Date: 2026-10-25

## Context

Phase 1 gave learners XP, levels and unlocks. Phase 2 adds the longer-term layer: choosing a
specialisation, a talent tree, badges and streaks. Three things make this risky.

- Levels give points to spend, and spending can be undone for free. Any talent that changes how
  much XP an exercise earns would simply be respecced into before each pass.
- Streaks reward showing up, and anything that rewards showing up gets gamed with junk
  submissions or by clock tricks.
- Badges can be earned by effort that does not end in a pass. A streak badge does not care whether
  the attempt that completed the streak passed.

The domain must stay theme-agnostic (ADR 0004): it says path, specialisation, exercise and branch,
and never "class", "quest" or "zone".

## Decision

**Talents are non-scoring.** The closed set of effects is `title` (text shown on the profile) and
`reference_solutions(branch)` (read the reference solution, with notes, for exercises already
passed in that branch). Nothing a talent does can change XP, levels, checks or unlocks, so XP stays
a clean signal of passed work and respecs can be free and unlimited. Reference solutions are
deliberately a reward for demonstrated skill: they need the talent *and* a pass of that exercise.

**Paths and the tree.** A path is `generalist` (the default, stored as no choice) or a
specialisation defined in `content/progression/classes.yaml` with a home branch. A specialisation
can be chosen once its home branch is unlocked, which is how "after the starter zone" is enforced
without naming the starter branch in code. Talents live in `talents.yaml`, in a `general` subtree
open to every path or in a specialisation's own subtree. A node needs a minimum level, its parents
and *passed exercises*. A parent must be in the same subtree or in `general`, so dropping a
subtree can never orphan a surviving node. Changing path drops the old subtree's allocations and
refunds the points. Everything is validated when content loads (`forgeway content validate` and
API start-up), collecting every problem: unknown parents, exercises, branches and paths, cycles
and cross-subtree parents.

**Points are derived, never stored.** One point per level from level 2. Allocations are the only
stored fact. If more is spent than the level allows (content changed under a learner), the newest
allocations beyond the budget are inactive until the learner respecs. Inactive rows are pruned the
next time the learner changes their build.

**Badges are content-defined and evaluated on every graded attempt.** Criteria come from a closed
set: `branch_complete`, `exercises_passed`, `first_try`, `no_hint_passes`, `streak_days` and
`level_reached`. They are evaluated inside the grading transaction, right after the attempt's
result and XP are recorded, for passed and failed attempts alike. They are stored as append-only
`badge_awards`, unique per learner and badge, with the `attempt_id` that earned them, and never
revoked. That is why `streak_days` looks at the longest streak, not the current one. Awarding is
idempotent: re-processing an attempt cannot award a badge twice.

**A streak counts learning days.**

- Each attempt is stamped at submission with `local_day`, its date in the learner's IANA time zone
  at that moment. Changing the zone later never rewrites history.
- A learning day is a `local_day` with at least one *graded* attempt (passed or failed). Errored
  attempts never count. An attempt whose files are byte-identical (same SHA-256 of the canonical
  submission, `files_hash`) to an earlier graded attempt on the same exercise by the same learner
  does not count, so a junk resubmission cannot keep a streak alive.
- The current streak is the run of consecutive learning days ending today or yesterday in the
  learner's *current* zone. The longest streak is the longest run ever. Both are pure date
  arithmetic over the stored days.
- The zone is set from the browser at registration, editable on the profile, validated against
  `zoneinfo.available_timezones()` and UTC by default. `tzdata` is a dependency so slim images
  have zone data. There is no freeze mechanic.

**Completion payload.** A graded attempt's progression payload gains `badges_awarded`,
`talent_points_gained` and `streak`. Failed attempts now carry a payload too, with no XP, because
they can earn a badge and move the streak.

## Consequences

Positive:

- Respec can be free, so there is no punishing "wrong choice" and no refund bookkeeping.
- The XP ledger stays the single source of truth for levels and every other number is derived.
- Stamped days and hashes make the streak auditable and hard to game without making it fiddly.
- Every rule is a pure function with property tests, including DST and the far east and west
  zones.

Negative:

- Talents recognise skill but cannot reward it with power. Some learners may find them cosmetic;
  reference solutions are the one substantive benefit.
- Evaluating badges after every graded attempt costs a few queries per attempt. The counts are
  small and indexed; revisit if grading throughput becomes a concern.
- A learner who lives through a calendar day being skipped (a zone moving across the date line)
  loses a streak day. This is rare and left as is.
- Attempts that predate this change have a null `files_hash`, so they are never treated as repeats,
  and are stamped with their UTC date.
- A removed or renamed exercise or talent leaves stale rows. Passed exercises are never un-passed,
  so the only visible effect is inactive allocations (above).

## Alternatives considered

- **Scoring talents** (XP multipliers, extra hints). Rejected. With free respecs they would be
  respecced into before each pass, and XP would stop meaning "passed work".
- **Paid or limited respecs.** Rejected. It adds a currency and a punishment without protecting
  anything, once talents cannot affect scoring.
- **Storing points or streaks as counters.** Rejected. Counters drift from their causes. Both are
  cheap to derive from the ledger and the stamped days.
- **A freeze or grace mechanic for streaks.** Rejected for now. It adds state and a purchase loop
  and hides what the streak means.
- **Server-clock "today" with no stored zone.** Rejected. A learner in Auckland would lose their
  streak at the wrong moment.
- **Evaluating badges on pass only.** Rejected. Streak and similar badges are earned by graded
  attempts that failed.
