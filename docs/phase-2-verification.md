# Phase 2 verification report

Date: 2026-10-25.

## Scope

Phase 2 covers the Protocols & tools (MCP) and Orchestration branches, the talent tree and
classes, and badges and streaks. It also includes work brought forward or carried over:

- shareable certificates, brought forward from Phase 4 at the product owner's request;
- resizable workspace panes and a world view for the RPG atlas, carried over from Phase 1.

The plan was reviewed independently before building. The changes that review prompted are
marked ◆ in `PLAN.md` (not part of this showcase).

## What was verified, and how

### Quality gates

| Area | Evidence |
| --- | --- |
| Backend quality gates | `ruff check`, `ruff format --check`, `mypy --strict` (71 files) and import-linter (2 contracts kept) are all clean |
| Frontend quality gates | ESLint (strict, type-checked), `tsc` strict, Prettier and the Vite build are all clean |
| Contrast | `scripts/contrast.py` passes in all four palettes. No new colour tokens were needed |

### Tests

| Area | Evidence |
| --- | --- |
| Backend tests | 307 pytest tests pass, up from 96 in Phase 1. Coverage: domain rules for paths, talents, badges, streaks and certificates, including Hypothesis tests across DST and time-zone edges; Postgres integration of the grading transaction (badges once, errored and duplicate submissions not counted as learning days, certificate issued exactly once, lazy backfill); API contract tests. 10 sandbox tests also pass with real containers |
| Frontend tests | 171 Vitest tests pass, up from 43. The previously flaky animation test was made deterministic, and the suite was run twice |
| Toolkit and grader | 61 grader tests pass, including MCP interoperability against the official Python SDK in both directions. Every emitted message is validated against the specification's JSON schema for revision 2025-11-25 |
| End to end | 29 Playwright tests pass against the Docker stack, covering: <br>• the Phase 1 journey in both modes; <br>• choosing a class and allocating a talent with the keyboard; <br>• a badge after the first pass, and the streak on the profile; <br>• making a certificate public, the LinkedIn links, and the public page's OpenGraph tags and escaping; <br>• a 404 after unpublishing; <br>• axe on the world atlas, profile and certificates in all four palettes; <br>• no header collisions and no horizontal overflow at 375 and 390px |

### Content

| Area | Evidence |
| --- | --- |
| Content | `lattice content test` grades 180 of 180 cases across four branches and 42 exercises: every reference solution passes, and all 138 wrong solutions fail the check they declare, with the declared message |
| Content review | An independent reviewer tried to pass each new branch without doing the work. All 10 proven cheats in Orchestration and all 11 in Protocols now fail, as do the 4 proven unfair checks; each cheat is kept as a permanent wrong solution. In Protocols the root cause was the reference implementation being importable from the learner toolkit, so it moved out of it (ADR 0005) |
| Specification accuracy | The MCP briefs' citations of tool-name rules and error handling were checked against the published 2025-11-25 specification |

### Builds and visual review

| Area | Evidence |
| --- | --- |
| Clean checkout | A fresh `git clone` from GitHub at the final commit was started with `docker compose up --build`; the smoke test and all 29 Playwright tests pass |
| CI | All four GitHub Actions jobs are green on the final commit, including the cold-build stack job |
| Visual review | The lead reviewed screenshots of every new screen in both modes, light and dark, desktop and phone. That review led to the polish round below (see `docs/screenshots/`) |

## Problems found during verification, and fixed

### Grading

- **Learners could wrap the reference implementation.** The learner toolkit exported the MCP
  reference implementation, so wrapping it passed seven exercises. The reference now lives on the
  grader side.
- **Orchestration cheats.** Ten were closed by asserting on the content of what the code actually
  sent: tool results, error results, the classifier's label and checkpoint contents. Two other
  measures hid test state from the learner:
  - resuming from a fresh process;
  - keeping concurrency evidence out of the learner's reach.
- **Four unfair checks.** In each, the brief and the test disagreed. The briefs now state the
  rule the test enforces, citing the specification where it applies.

### Interface

- **A theme choice was reverted at sign-in.** A toggle clicked before the profile loaded was
  overwritten when the saved theme arrived. The fix has a regression test.
- **Nested interactive controls.** The world map nested focusable links inside an image, an
  axe violation the end-to-end scan found.
- **Phone layout:**
  - the profile link overlapped the XP counter at 390px;
  - the talent table scrolled off-screen;
  - locked talents duplicated their requirements and showed misleading buttons;
  - links crossed in the talent constellation.

## Not verified, or verified only partly

- **The LinkedIn preview card.** It cannot be checked until the site is publicly reachable,
  because LinkedIn fetches the page itself. The page's OpenGraph tags and the 1200×627 image are
  tested; *Add to profile* works today but points at a local URL.
- **Screen readers.** The experience was checked structurally (roles, names, live regions,
  axe), not with a real screen reader.
- **Load.** There has been no load testing.
- **Announcement end to end.** The "certificate earned" announcement after the final exercise of a track
  is covered by unit tests; the end-to-end suite earns certificates through the API helper
  rather than the editor.

## Known limitations and follow-ups

- **In-process grading.** It can still be subverted by a determined learner who imports
  grader-side modules (ADR 0003, ADR 0005).
- **One skip-layer crossing in the retrieval subtree.** A talent with a parent two layers up
  crosses one link; ordering by parent position cannot fix a link that skips a layer.
- **Fan-out timing.** A sequential fan-out submission takes about five seconds to fail, waiting
  out the concurrency check's timeout.
- **Phone talent tree.** The RPG constellation is drawn at a compact size on phones, so its
  labels are small; the card list carries all the information.
- **Certificate caching.** An unpublished certificate can stay in caches for up to five minutes
  (`max-age=300`).
- **Fixed compose project name.** `docker-compose.yml` pins the project name to `lattice`, so a
  second checkout on the same machine shares, and can remove, the first one's volumes. This
  happened once during verification, destroying only the local demo database.
