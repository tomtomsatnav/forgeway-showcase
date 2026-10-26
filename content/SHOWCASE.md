# Showcase content

This is the content tree of a public showcase copy of Forgeway. The live product is at
https://forgeway.dev.

- **Foundations (`branches/starter/`)** are complete: brief, starter, hidden tests, reference
  solution and wrong answers, so you can see how content proves itself in CI.
- **Every other exercise** keeps its `exercise.yaml` (without hints), `brief.md` and `starter/`.
  Its hidden tests, reference solution and wrong answers are omitted. In the guided projects, a
  milestone's starter files that would be the previous milestone's reference solution are
  replaced by a placeholder.

The presence of this file is what tells the content loader
(`backend/src/lattice/infrastructure/content_loader.py`) to accept exercises with none of `tests/`,
`solution/` and `wrong/`. Grading such an exercise fails with a message that says so. Delete this
file and the loader is as strict as the product's.
