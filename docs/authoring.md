# Authoring exercises

An exercise is a directory of plain files. No code in the platform changes when you add one.

```
content/branches/<branch>/exercises/<slug>/
├── exercise.yaml      metadata, checks and hints
├── brief.md           what the learner reads
├── starter/           the files the learner starts from (every editable file lives here)
├── tests/             hidden pytest checks
├── solution/          a reference solution — must pass every check
├── notes.md           optional: commentary shown with the solution to learners who earn it
└── wrong/<case>/      a plausible mistake — must fail the check it names
    ├── <editable file(s)>
    └── expect.yaml
```

The exercise id is `<branch>.<slug>`, taken from the directory names.

## `exercise.yaml`

```yaml
version: 1                    # bump when a change could alter whether a solution passes
title: Fixed-size chunking    # sentence case, no full stop
tier: beginner                # beginner | intermediate | advanced | capstone
xp: 100                       # beginner 50–100, intermediate 100–150, advanced 150–250
prerequisites: [retrieval.what-is-retrieval]
skills: [chunking]
editable: [chunker.py]        # the only files a learner may submit
limits: { timeout_s: 20, memory_mb: 256 }   # optional; these are the defaults
isolation: process            # optional; learner code in a child process (inprocess is the default)
hints:                        # progressive: each one gives away a little more
  - "Think about what happens to a sentence that straddles a boundary."
  - "Step forward by `size - overlap` characters each time."
checks:
  - id: sizes                 # kebab-case, unique in the exercise
    title: Chunks respect the size limit
    test: test_chunker.py::test_max_size
  - id: recall
    title: Retrieval finds the answer-bearing chunk
    test: test_behaviour.py::test_recall_at_3
    kind: behavioural         # deterministic (default) | behavioural
```

## Writing checks

Each check is one pytest test function. Learners see the check's title and, when it fails, the
**assertion message** — never the test source. So every assertion carries a message that says
what was expected, what happened and, where possible, a nudge:

```python
assert len(chunks) == 4, (
    f"A 1,000-character document with size=300 and overlap=50 should give 4 chunks, "
    f"but chunk() returned {len(chunks)}. Check how far you step forward each time."
)
```

Exceptions raised by learner code are reported with their type, message and the learner's own
stack frames, so you do not need to catch them.

- Test behaviour through the public function the brief describes, not implementation details.
- Use varied inputs so hard-coding the expected output cannot pass.
- Keep each check focused; the learner should know which idea they have not got yet.
- `@pytest.mark.parametrize` is fine: every case counts towards the one check, and the first
  failing case supplies the message.
- Tests are hidden but not secret: assume a learner could read them. Grade genuine behaviour.

### Lessons from cheat reviews

Independent reviewers proved 21 ways to pass Phase 2 exercises without doing the work. They fell
into a few patterns; design against each:

- **Borrowed behaviour.** Never put the taught behaviour in `forgeway_kit`. Learners can import
  anything there, so the toolkit offers only what briefs tell them to use; reference
  implementations live on the grader side. Learner code cannot import `lattice_grader` (the
  harness fails a submission that names it, and `lattice_grader.guard` refuses the import from
  submission files, also in `run_fresh` and other child processes; ADR 0003). When your tests use
  a `*_reference` package, add a `borrows-the-grader` wrong case: the reference solution plus
  `importlib.import_module("lattice" + "_grader.<package>")` at module level.
- **Surface assertions.** Asserting that *something* was sent, or that a count matches, is not
  enough. Assert on the content that actually reached the model or tool (`FakeModel.requests`),
  with per-call values the learner cannot guess.
- **Predictable fakes.** If a scripted fake decides by keywords, the learner can use the same
  keywords and skip the model. Make the fake's answer arbitrary (a seeded table, a fresh token)
  and assert the code followed *that* answer.
- **Reachable test state.** Anything stored on an object you hand to learner code can be read
  or changed by it. Keep evidence (counters, barriers, flags) in closures or test-local objects.
- **Untested requirements.** If the brief promises behaviour (error results, list once, join
  every block), a check must exercise it, or a wrong case will slip through.
- **Unstated rules.** The reverse: if a test enforces a format, case or character set, the
  brief must say so explicitly. When the rule comes from a specification, cite it.
- **Objects that lie about equality.** A learner can return a `str` or `list` subclass whose
  `__eq__` always says yes, and a bare `assert result == expected` passes. Before comparing,
  turn what learner code returns into plain built-ins (`json.loads(json.dumps(value))`, or
  `type(value) is str` plus `str.__str__(value)`), and assert on that. `FakeModel` records what
  the wire would carry: plain built-ins, so request assertions are honest; learner return values
  still need canonicalising.
- **Unseeded randomness.** Randomised inputs defeat lookup tables, but grading must be
  deterministic: the same submission always gets the same result. Seed every generator and use
  enough cases that a lookup table is no shorter than the real work.
- **Untested defaults and boundaries.** If the brief gives a default argument or an exact
  boundary (`>` versus `>=`), a check must call without the argument and hit the boundary.
- **Expected values in the caller's frame.** In-process, learner code runs in the test's
  process, so it can read the test's locals with `sys._getframe(1)` (the limit ADR 0003
  accepts). Do not build the expected answer before calling learner code: hand it only the
  inputs, and compute what you expect in a helper called after it returns. `isolation: process`
  (below) puts the frames out of reach, but keep the habit: it costs nothing.
- **Oracles in the test module.** In-process, learner code can find the hidden test module in
  `sys.modules` and call anything defined at its top level. A `reference_ci()` there let a
  one-line `gate.py` pass all seven of bootstrap-regression-gate's checks. Run an exercise whose
  tests hold a reference implementation or an answer key with `isolation: process`. Where that
  cannot work (user-isolation's checks walk the learner's private attributes), define the oracle
  inside the test that uses it. `forgeway content review` flags a top-level `reference*`,
  `expected*` or `oracle*` function in an in-process test, and a `cheat-reads-the-oracle` wrong
  case (the solution with its core replaced by a call to the oracle) proves the route is shut.
- **In-process persistence.** "Resume after a crash" in the same process can be faked with a
  module-level dict. Resume from a fresh copy of the store and a reloaded module. A reload is
  not a restart either: state stashed on `sys`, in `builtins`, on another module or in
  `os.environ` survives it. For a real restart, run each session in a new interpreter with
  `lattice_grader.isolation.run_fresh(session, *json_args, path=[submission_dir])`, where
  `session` is a module-level function in the test file that imports the learner's modules
  itself and returns plain JSON. Also assert that what must persist (a seeded marker text) is
  in the store itself, and that what was deleted is gone from it. Restart where it proves
  something: a lifetime that carries a run on from the store must be fresh, but one or two
  such restarts per property are enough, not one per sub-case, and a lifetime that starts from
  an empty store has nothing to carry over, so it can run in the test's own process.

### Out-of-process grading

`isolation: process` in `exercise.yaml` runs learner code in a child interpreter, and the hidden
tests reach it through a bridge (ADR 0009). The tests' frames, closures and modules are then
out of learner code's reach, and so is the grader. Every capstone and guided-project milestone
uses it. Most tests need no change; these are the shapes that do:

- **Stores are objects, not dicts.** A `dict` or `list` handed to learner code arrives as a
  copy, so writes to it never reach the test. A store the code must write to is an object,
  usually a `collections.abc.MutableMapping` over a private dict, which crosses as a handle.
  What learner code returns crosses by value too, which already kills `str` and `list`
  subclasses that lie about equality.
- **Callables are methods.** Learner code may call the public methods of an object the tests
  pass in and read its plain data, and properties that return plain data, nothing else. Item
  writes (`store[key] = value`) work only on a `MutableMapping` or `MutableSequence` object,
  `next()` only on an iterator, and `with` on nothing the tests pass in. A function stored on an
  instance (`SimpleNamespace(complete=fn)`, `self.complete = lambda ...`) is refused: wrap it
  in a method. A spy that forwards calls returns a bound method (`types.MethodType`).
- **Learner dataclasses are handles.** `dataclasses.is_dataclass` is false for them. Read their
  fields by name: `getattr(value, "__dataclass_fields__")` lists them.
- **No subclassing learner classes** in tests, and no `inspect.signature` on functions the
  tests pass in.
- **Threads work.** A learner thread pool's calls reach the tests' fakes at the same time, each
  on a thread of the grader's own, so a `threading.Barrier` in a fake still meets.
- **`run_fresh` bridges too.** The session function runs in the fresh interpreter and the
  learner code it imports in a process beneath it, so its frames and fakes are out of reach.
  That is two interpreter starts per call, and they are needed: with learner code in the
  session's own interpreter, personal-assistant's `cheat-rewrites-the-session-record` passes
  every check (ADR 0009, "Grading time").
- **Re-imports run afresh.** Dropping learner modules from `sys.modules` and importing again
  re-runs them in the child, as it would in-process.
- **Learner child processes are unchanged.** A server or script the tests start with
  `sys.executable` is a process of its own already; it is started by the test, beside the
  learner's bridge child.

A cheat that walks the test's frames, reads a fake's closure or patches the hidden test module
passes in-process and fails out of process. Capstones keep one or two such `cheat-*` wrong cases,
so the isolation stays proved.

## Capstones

A capstone closes a branch with a larger project that uses everything the branch taught. Set
`tier: capstone`; the loader enforces the rest and reports every breach at once.

- **One per branch**, and none in the root branch (the one that requires nothing).
- **XP 300 to 400.** Limits at most `timeout_s: 60` and `memory_mb: 512`; ask for what the
  reference solution needs, with headroom.
- **Prerequisites cover the branch.** The capstone's prerequisites, followed transitively, must
  reach every other exercise in its branch. Listing the last exercise is enough when the chain
  runs through the rest. Nothing may list a capstone as a prerequisite.
- **Several editable files.** A project is more than one function, so `editable` usually lists
  several files, each with a starter. Give each one a clear job in the brief.
- **Checks build up.** Order them from the smallest working slice to the whole system, so a
  failing capstone tells the learner which part is not there yet.
- **Wrong cases.** Include the usual plausible mistakes, one per check where you can. Also include
  the pasted-reference-solutions shortcut: a submission stitched together from the reference
  solutions of the branch's earlier exercises, which the `reference_solutions` talent shows to
  learners who have passed them. It must fail the check that asserts on the parts working
  together (what reached the model or tool, with per-call values the learner cannot guess). A
  capstone that earlier answers can simply be pasted into has not tested anything new.
- **Grading time.** The reference solution must grade in under 15 s in the local Docker
  sandbox, and should aim for 10 s: the production sandbox (gVisor, one CPU) runs about four
  times slower, learners wait for the result, and the single grading worker serves no one else
  meanwhile. `forgeway content test --only <id> --time` prints each case's wall-clock time and
  flags a solution over 15 s. The usual costs are interpreter starts (each `run_fresh` call is
  two, each server a test starts one or two) and sleeps in fakes. Sleep only in the checks that
  need it (a stagger that makes workers finish out of plan order belongs to the check that
  asserts plan order), and wait on an event rather than for a fixed time where you can.

## Guided projects

A guided project is a branch whose `branch.yaml` says `kind: project` (the default is
`standard`). It must `require` at least one branch; the branches it draws on are the usual
choice. Its milestones are ordinary exercises and its last one is its capstone, so every capstone
rule applies. A milestone before the capstone is `tier: advanced` but carries 250 to 300 XP, more
than a track's advanced exercises, because each one builds a slice of a whole system.

Milestones build one codebase. A milestone may say `carry_from: <exercise id>`, naming an earlier
exercise in the same branch that it depends on, directly or not; the loader rejects anything
else. When a learner opens it with no draft, the workspace starts from their files in their latest
passing attempt of that exercise, for each path this milestone lets them edit, and from the
starter for the rest. They can go back to the starter at any time. Grading never sees the carried
files unless the learner submits them, so make each milestone's starter the previous milestone's
reference solution: the exercise then stands on its own for anyone who resets.

## The learner toolkit

Learner code and tests import `forgeway_kit`, never the grader:

| Name | Purpose |
| --- | --- |
| `Message`, `Completion`, `Usage` | Provider-neutral chat types |
| `ModelClient` | Protocol: `complete(messages, *, system, max_tokens, temperature)` |
| `FakeModel(responder, context_window)` | Deterministic model; records `requests`; the responder returns text, a list of `ToolCall`s, or raises |
| `Tool`, `ToolCall` | Function calling: offer tools with `complete(..., tools=[...])`; answer each call with a `Message(role="tool", content=..., tool_call_id=...)` |
| `default_client()`, `use_client(client)` | The configured client (the fake in the sandbox) |
| `RateLimitError`, `ServerError`, `InvalidRequestError` | Errors real SDKs raise |
| `count_tokens`, `tokenize` | Deterministic token counter, the same one `FakeModel` uses |
| `Embedder`, `HashingEmbedder`, `cosine_similarity` | Deterministic, lexical embeddings |
| `forgeway_kit.mcp` | `PROTOCOL_VERSION`, `JSONRPC_VERSION`, `ErrorCode` and `McpError` only. MCP is implemented by the learner at the wire level (ADR 0005) |

Hidden tests for the Protocols & tools branch use a reference MCP server and client from
`lattice_grader.mcp_reference`. Never export anything from it through `forgeway_kit` or name it in
a brief: it implements the behaviour the exercises teach. If a brief hands learners a helper, put
it in the starter file.

Grade the system around the model, not the model: assert on what reached the prompt, how the
code reacted to an error or a truncated reply, which chunks came back — never on prose quality.

The sandbox has Python 3.12, `pytest`, `numpy` and the toolkit. It has no network.

## Wrong cases

Each `wrong/<case>/` holds a believable mistake and an `expect.yaml`:

```yaml
fails: sizes                       # the check this mistake must fail
message_contains: should give 4    # text the learner-facing message must include
```

Write the mistakes learners actually make (off-by-one overlap, forgetting the system prompt,
retrying non-retryable errors), not obviously broken code.

## Checking your work

```bash
make sandbox-image                                   # once, or after toolkit changes
uv run forgeway content validate                      # schema, files and prerequisite graph
uv run forgeway content test --only retrieval.chunk   # grade solution and wrong cases for real
```

CI runs both for every exercise on every push.

## Shipping a patch

1. **Scaffold.** `uv run forgeway content new <branch> <slug> --title "..."` writes a complete
   exercise, graded out of process: `exercise.yaml`, a brief with the usual sections, one
   editable file, one check whose test canonicalises with `plain()` and works out the expected
   value after the learner call, a solution that passes it and a `wrong/` case that fails it. It refuses to overwrite,
   and adds the new exercise to the branch capstone's prerequisites. Use `--tier capstone` for
   a capstone and, in a project branch, `--carry-from <milestone>` to start from the previous
   milestone's reference solution.
2. **Write** the brief, starter, tests, solution and wrong cases, replacing the scaffold's
   example.
3. **Test.** `uv run forgeway content test --only <branch>.<slug>` grades the solution and every
   wrong case in the sandbox.
4. **Review.** `uv run forgeway content review <branch>.<slug>` prints the checklist from
   [Lessons from cheat reviews](#lessons-from-cheat-reviews) with a ✓ or ⚠ and `file:line` for
   each item a cheap heuristic can judge, and a · for those you must read for yourself. It is
   advisory and always exits 0: a ✓ means nothing was found, not that nothing is there (the
   limits are listed in `backend/src/lattice/application/content_review.py`). Fix what it finds. When you
   have read a finding and judged it safe, say why on the flagged line, `# review-ok: <why>` in
   a test or `<!-- review-ok: <why> -->` in the brief, and the review counts it as accepted.
   Without an id, `forgeway content review` reviews every exercise and prints only what to look
   at; keep it clean.
5. **Probe.** Write the shortcuts a learner might take, each as a directory of editable files,
   and grade them: `uv run forgeway content probe <branch>.<slug> probes/a probes/b`. Each probe
   is laid over the starter, or over the solution with `--base solution` so it need only replace
   one file. Every check's result and message is printed. A probe that passes is a cheat: fix
   the tests and keep it as a wrong case.
6. **Release notes.** Describe the change in `content/releases/<version>.md` (see
   [Release notes](#release-notes)), and bump the exercise's `version` if a solution could now
   pass or fail differently.
7. **Pull request**, with the commands above passing: CI runs `content validate` and
   `content test` again.

### Release notes

Each content release is one Markdown file, `content/releases/<version>.md`, shown on the What's
new page (the Chronicle in RPG mode) with an unread marker until a learner opens it. The version
is a calendar version, `YYYY.MM.N` (`2026.10.0`, then `2026.10.1` or `2026.11.0`), and the file
is named after it. YAML front matter comes first, then the body:

```markdown
---
version: 2026.11.0
date: 2026-11-09          # ISO date
title: Reranking, and a fix to chunking
summary: One line for the list.
added: [retrieval.reranking]         # exercise ids; each list is optional
updated: [retrieval.hybrid-search]
fixed: [retrieval.fixed-size-chunking]
---

The body, in Markdown, in the house voice: what changed and why it matters to a learner.
```

`forgeway content validate` checks every release note: the front matter parses, the version is
unique and matches the file name, the date is a real ISO date, and every exercise id exists. The
page links each listed exercise. [`2026.10.0.md`](../content/releases/2026.10.0.md) is the first
release and a model for the rest. Content loads at API start-up, so a release appears on the
next deploy. Once the note is merged, the release is tagged `v<version>` (`v2026.11.0`) and the
tag deployed: see "Cutting a release" in [deploy/vps/README.md](../deploy/vps/README.md).

## Style

UK spelling. Briefs are short: a paragraph of why it matters, a small example, then the task.
Use second person and plain language. Briefs and code never mention a presentation theme:
"quest" and "zone" belong in `content/themes/rpg/`, not here.
