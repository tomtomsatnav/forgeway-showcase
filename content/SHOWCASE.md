# Showcase content

This is the content tree of a public showcase copy of Forgeway. It holds only what a free learner
can use. The full course is at https://forgeway.dev.

- **Foundations (`branches/starter/`) and the Python primer (`branches/python-primer/`)** are
  complete: brief, starter, hidden tests, reference solution and wrong answers, so you can see how
  content proves itself in CI.
- **The other free exercises**, the first few of each track, keep `exercise.yaml`, `brief.md`,
  `starter/`, and `python.md` and `live.py` where they have them. Their hidden tests, reference
  solutions and wrong answers are not here.
- **Pro exercises, capstones and guided projects are not here at all.**

The presence of this file is what tells the content loader
(`backend/src/lattice/infrastructure/content_loader.py`) to accept exercises with none of `tests/`,
`solution/` and `wrong/`, and `forgeway content test` to skip them. They cannot be graded in this
copy. Delete this file and the loader is as strict as the product's.
