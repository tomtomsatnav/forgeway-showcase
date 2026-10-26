# Phase 1 verification report

Date: 2026-10-25. Commit: see `git log` on `main` at the time of the Phase 1 sign-off request.

Phase 1 scope: exercise engine and grader, shared starter zone, Retrieval branch, basic
progression (XP, levels, unlocks), both presentation modes switchable via a toggle.

## What was verified, and how

| Area | Evidence |
| --- | --- |
| Backend quality gates | `ruff check`, `ruff format --check`, `mypy --strict` (51 files), import-linter (2 contracts kept) — all clean |
| Backend tests | 96 pytest tests pass: unit (content model, prerequisite graph, grading interpretation, progression incl. Hypothesis property tests, toolkit), Postgres integration (accounts, submissions, queue concurrency, stale-claim recovery, idempotent XP, content sync), API contract tests, and 12 sandbox tests with real containers. Line coverage 80% excluding the in-sandbox harness, which runs inside containers and is exercised by the sandbox tests instead |
| Sandbox security | Real-container tests: infinite loop, fork bomb, memory bomb, stderr flood, network access, writes to the read-only root, non-root UID, forged report — each contained and reported as a learner failure, never a pass |
| Content | `lattice content test`: all 22 reference solutions pass; all 47 wrong solutions fail the check they declare, with the declared message — 69/69 |
| Content review | An independent reviewer graded seven cheat or edge-case submissions. All five cheats it proved, plus two weak-validation probes, now fail; one valid solution the old checks wrongly rejected now passes |
| Frontend quality gates | ESLint (strict, type-checked), `tsc` strict, Vite build — clean; 43 Vitest tests pass |
| End to end | Playwright (9 tests) against the Docker stack: the full journey (register → wrong answer fails with a message → hint behind its cost warning → correct answer passes → completion moment with XP → next exercise unlocked) in both modes; axe in all four mode × scheme palettes on the map, the workspace and graded results — no serious or critical violations; keyboard-only navigation with visible focus and an escape route from the editor; no horizontal overflow at 375px in either mode. Three consecutive green runs |
| Clean checkout | Fresh `git clone` from GitHub → `docker compose up --build` → smoke test and the full Playwright suite pass; demo login works |
| Visual review | Screenshots of both modes, light and dark, desktop and mobile, reviewed by the lead (see `docs/screenshots/`) |
| Contrast | `scripts/contrast.py`: every text pair ≥ 4.5:1, control borders ≥ 3:1 on every surface, in all four palettes |

## Problems found during verification, and fixed

- Parametrised pytest checks were not mapped to their check, so a correct solution could be
  reported as inconsistent. Fixed in the grader, with a regression test.
- Exercise order came from an arbitrary topological order (an intermediate exercise appeared
  second). Now a stable, tier-aware order.
- Check titles and the hint heading were invisible in dark mode: a Tailwind colour named `base`
  collided with the `text-base` font-size class. Fixed; a unit test now forbids colour and
  font-size name collisions, and the axe scans now cover graded results.
- Five proven ways to game exercise checks (and one unfair check) found by independent review.
  Fixed and re-proven.
- A layering violation (the CLI importing the API) caught by CI. The CLI is now the declared
  composition root.

## Not verified, or verified only partly

- **Cold builds** are proven in CI rather than locally: the local clean-clone run reused
  Docker's build cache, while the CI `stack` job builds every image from scratch on a fresh
  runner and then runs the smoke test and the full Playwright suite (about two minutes).
- **GitHub Actions** runs every check above on each push, and all four jobs are green.
- **Screen-reader experience** was checked structurally (roles, names, live region, axe), not
  with a real screen reader.
- **Load.** No load or soak testing; the worker processes one attempt at a time per process.

## Known limitations and follow-ups

- **In-process grading can be subverted** by a determined learner (documented in ADR 0003);
  the stakes are low by design. Production would run sandboxes on gVisor (Cloud Run Jobs).
- **The local worker mounts the Docker socket**, which is root-equivalent on the host —
  acceptable for local development only (ADR 0003).
- **The login rate limiter is per process**; several API instances would need a shared store.
- **The workspace is capped at 1200px**, so long code lines scroll inside the editor on laptop
  screens. Resizable panes would be a better answer.
- **The RPG atlas** renders each zone as its own framed map with a route of waypoints, rather
  than one continuous world map. A world view fits better once Phase 2 adds zones.
- **Starlette's test client** prefers the newer `httpx2` package; the project uses `httpx`,
  which works with a deprecation warning. Adding `httpx2` was held back for a decision.
- **Signed-out start-up** logs one expected 401 from `GET /api/auth/me` in the browser console.
