# Phase 3 verification report

Date: 2026-10-26.

## Scope

Phase 3 added:

- **Four tracks:** Knowledge graphs, Memory, Context engineering, and Evals & guardrails.
- **Capstones:** one closing every track except the foundations, which is seven. In RPG mode each
  is a boss.
- **Two guided projects**, added at the product owner's request: *Support copilot* and *Research
  agent team*.

The product was also renamed from Lattice to **Forgeway**. The learner toolkit is now
`forgeway_kit`.

As agreed, this phase was built without a sign-off stop. The plan was reviewed before building,
Fable reviewed everything after it, and Opus did all agent work from the middle of the phase on.
Screenshots are deferred to the end of Phase 4.

## What was verified, and how

| Area | Evidence |
| --- | --- |
| Content | `lattice content test`, one full run after the final rename: **553 of 553 cases**. All 91 reference solutions pass, and all 462 wrong solutions fail the check they declare, with the declared message. The content covers 10 branches (8 tracks and 2 projects), 9 capstones, 47 talents and 24 badges, and `lattice content validate --require-capstones` passes |
| Backend | `ruff`, `ruff format`, `mypy --strict` (92 files) and import-linter (2 contracts kept) are clean. 437 pytest tests pass, plus 10 real-container sandbox tests |
| Grader | 152 tests pass. They cover the import guard, `run_fresh` isolation, the `FakeModel` snapshot of requests to plain values, the MCP interoperability tests against the official SDK, and the reference-module unit tests |
| Frontend | ESLint, `tsc` strict, Prettier and the build are clean. 225 Vitest tests pass |
| End to end | 40 Playwright tests pass against a freshly built stack, covering: <br>• the journeys in both modes; <br>• capstones on real content (the lair, the "boss defeated" moment, capstone framing); <br>• roads on the world atlas; <br>• carried files and starting over in a guided project; <br>• certificates; <br>• keyboard use, and phones at 375 and 390px; <br>• axe in all four palettes |
| CI | All jobs are green on the final commit. Content is sharded per branch, and the e2e job now mounts the project fixture so the carried-files spec runs |
| Production | Deployed to the VPS behind Cloudflare and a temporary password gate, with grading under gVisor. A smoke test through the public URL registers a learner, rejects a wrong answer, passes a right one and records XP. The other site on the VPS stayed up throughout |

## How grading quality was established

Every track, every capstone and both projects were reviewed by an adversarial reviewer who tried
to pass without doing the work, and each proven cheat or unfair check was fixed and re-proven.

Over 80 cheats and 15 unfair checks were proven across Phase 3. Each cheat became a permanent wrong
solution where it was a mistake a learner could plausibly make. Fable's end-of-phase review then
asked whether the fixes had been principled or whack-a-mole. Where it found whole classes still
open, they were fixed at the platform level.

| Class | Platform fix |
| --- | --- |
| Borrowing the reference implementation | `forgeway_kit` exports only what the briefs hand to learners. Reference code is grader-side, and an import guard (`lattice_grader.guard`) refuses it to learner code, including in child processes. 27 exercises carry a `borrows-the-grader` wrong case |
| Objects that lie about equality | `FakeModel` records requests as the wire would carry them, as plain built-ins. Tests also canonicalise learner return values |
| State that survives a "restart" | Restarts run in a fresh interpreter in an empty directory (`run_fresh`), and tests assert the store fully describes the run |
| Answer keys reachable from learner code | Expected values are computed after the learner's call returns. The tests were swept branch by branch |
| Predictable fakes, unstated rules, untested defaults and boundaries, unseeded randomness | Written up as lessons in `docs/authoring.md` and applied in every fix |

## Not verified, or verified only partly

- **Real learners.** No real learner has used the new tracks. Difficulty and time estimates are
  the authors' judgement.
- **Screen readers.** Checked structurally (axe, roles, names, live regions), not with a real
  screen reader.
- **Load.** One worker with one or two concurrent sandboxes on the VPS. There has been no load
  testing.
- **The LinkedIn preview.** It cannot work while the site is behind the password gate.

## Known limitations and follow-ups

- **In-process grading.** Learner code still runs in the same interpreter as the hidden tests. A
  determined learner can remove the import guard, read a fake's closure or import a test module.
  ADR 0003, 0005 and 0008 say so plainly. Phase 4 moves learner code out of process.
- **Unused capstone prerequisites.** The prerequisites of some capstones are claimed but not
  exercised by the capstone itself: `graphrag-service` does not use guarded text-to-query or
  community summaries, and `context-builder` does not use few-shot selection. They are deferred to
  Phase 4 content work.
- **Pedagogy.**
  - Some capstone briefs hand over more of the integration than they should.
  - Guided-project milestone XP (200–250) is low for the work involved.
  - A few briefs could be closer to current practice, for example on bitemporal edges and cache
    breakpoints.
- **Live models.** The guided projects' "run it against a real model" notes point to live mode,
  which arrives in Phase 4.
