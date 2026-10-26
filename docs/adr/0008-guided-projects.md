# ADR 0008: Guided projects and carried code

Status: Accepted
Date: 2026-10-26

## Context

Each branch teaches one area and closes with a capstone (ADR 0007). Practitioners rarely work in
one area at a time, and a portfolio needs something larger than any single exercise. Two guided
projects close the curriculum: a support copilot and a research agent team. Each should feel like
building one codebase over several sittings, while every step stays graded on its own and
deterministically.

## Decision

- **A project is a branch** with `kind: project` in `branch.yaml`. It `requires` the branches it
  draws on and so unlocks once they are complete. Its milestones are ordinary exercises; the last
  is its capstone, so every capstone rule applies and finishing it issues a certificate.
- **Carried code.** A milestone may declare `carry_from: <exercise id>`, which must be an earlier
  exercise in the same branch among its transitive prerequisites. When the learner has no draft,
  the workspace opens with their own files from their latest *passing* attempt of that exercise,
  for the paths this milestone edits; other paths come from its starter. A draft always wins.
  `files_source` (`starter`, `draft` or `carried`) tells the client which, and
  `DELETE /api/exercises/{id}/draft` resets to the starter behind a confirm step.
- **Grading stays self-contained.** Each milestone's starter is the previous milestone's reference
  solution plus new stubs, and its tests run only on the files submitted to it. Later milestones
  re-check what earlier briefs promised (`test_earlier.py`), so a regression is caught where it
  happens. Carrying code is a convenience, never a dependency of grading.
- **Presentation.** Professional mode labels a project "Guided project"; RPG calls it an
  "Expedition", with roads on the world atlas from every zone it requires.

## Consequences

- A learner who resets, or who never passed the earlier milestone, still gets a working starting
  point, and grading results do not depend on what they carried.
- Starters duplicate earlier solutions. That is deliberate: a milestone must be gradeable alone.
- Projects inherit the in-process grading limit of ADR 0003. Their restarts run in fresh
  interpreters (`lattice_grader.isolation.run_fresh`) and their fakes keep answers out of reach,
  but a determined learner can still subvert in-process checks until learner code runs out of
  process (Phase 4).
