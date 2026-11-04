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
├── python.md          optional: notes on the Python this exercise uses, for learners new to it
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
  harness fails a submission that names it, and learner code's user cannot read the package;
  ADRs 0003 and 0009). When your tests use
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
- **Expected values in the caller's frame.** Learner code runs in a process of its own, out of
  reach of the test's frames (ADR 0009). Still, do not build the expected answer before calling
  learner code: hand it only the inputs, and compute what you expect in a helper called after it
  returns. It costs nothing, and an answer sent over the bridge by mistake stays out of it.
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

Every exercise runs learner code in a child interpreter, as a user that cannot read the grader
package or the hidden tests, and the hidden tests reach it through a bridge (ADR 0009). There is
no other mode: a free exercise sharing the tests' user could read a paid exercise's reference
implementation. `isolation: process` in `exercise.yaml` is accepted and changes nothing. Most
tests need no special shape; these are the ones that do:

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
  tests pass in. When learner code must inspect a real function (protocols.tools-list), the test
  writes a small factory beside the submission before its first learner import, imports it through
  the bridge, and passes the functions it makes: they then live in learner code's process.
- **Private attributes read through the bridge.** A test may read a learner object's private
  attributes through its proxy, and `memory_reference.contains_text` walks them that way.
- **Threads work.** A learner thread pool's calls reach the tests' fakes at the same time, each
  on a thread of the grader's own, so a `threading.Barrier` in a fake still meets.
- **`run_fresh` bridges too.** The session function runs in the fresh interpreter and the
  learner code it imports in a process beneath it, so its frames and fakes are out of reach.
  That is two interpreter starts per call, and they are needed: with learner code in the
  session's own interpreter, a cheat that rewrites the session record passes
  every check (ADR 0009, "Grading time").
- **Re-imports run afresh.** Dropping learner modules from `sys.modules` and importing again
  re-runs them in the child, as it would in-process.
- **What the tests start runs as the learner's user too.** `ChildProcessTransport` starts a
  Python argv through the launcher, so a server under test cannot read the grader. Grader code
  that learner code must start itself cannot be imported there: give it the source
  (`tap_argv` passes it with `-c`), or keep the code on the grader's side and hand over a relay
  (`protocols_reference.PeerHost`, which needs a reference server).
- **Evidence is private.** Keep what learner code must not alter out of `tmp_path`, which it can
  write to.

A cheat that walks the test's frames, reads a fake's closure or patches the hidden test module
fails out of process. Capstones keep one or two such `cheat-*` wrong cases, and one free exercise
in each branch keeps `cheat-reads-the-grader`: it tries the grader's files by path, split-string
imports and the environment, raises if all of them fail (the expected result) and otherwise goes on
as the solution, which would pass and fail `forgeway content test`.

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
- **Process count.** A sandbox may hold 128 tasks, threads included, and under gVisor about 30 of
  those are the runtime's own. Local Docker does not count those, so a test that holds about 90
  tasks at once passes locally and fails in production, usually as a thread or `fork` error.
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

## Primers

A primer is a branch whose `branch.yaml` says `kind: primer`: optional groundwork that sits outside
the main tracks. `python-primer` is the only one. Its exercises are ordinary exercises, graded the
same way, with one free exercise keeping `cheat-reads-the-grader`. What differs:

- **It needs no capstone**, and may not have one. `--require-capstones` passes over it.
- **Every exercise is free**, whatever the plan or `free_exercises_per_branch`, and it neither uses
  up nor displaces any other track's free exercises.
- **Nothing depends on it.** It requires nothing, no branch may require it, and no exercise outside
  it may list one of its exercises as a prerequisite. The loader rejects all three.
- **No talents, badges or certificate.** Passing an exercise is enough to read its reference
  solution, and finishing the primer issues no certificate. Its exercises still award XP and count
  towards badges that count exercises.
- **Off the map.** The syllabus lists it as a labelled track, and the atlas lists it in the zone
  list only, because one more island breaks the 480 px limit on a phone. The landing page counts it
  apart from the tracks.

Leave `prerequisites` empty so learners can take only what they need, and let `xp` set the order.

## Python notes

`python.md` holds the "Python you'll need" panel, shown above the hints to learners who have turned
on *I'm new to Python* in their profile. A missing file means no panel. Write one for any exercise
that uses something beyond the basics, except in a primer, whose brief already teaches the language.
It never affects grading, the tests or the brief.

````markdown
### `@dataclass(frozen=True)` makes an immutable record

You list annotated fields and Python writes the constructor and `==` for you.

```python
@dataclass(frozen=True)
class Point:
    x: int
```
````

- **Two to five notes**, each a `###` heading naming the feature, a sentence or two, and a tiny
  Python example that parses. `backend/tests/unit/test_content_loader.py` holds the shipped files
  to this.
- **Explain the language feature, never the exercise's approach.** Set examples in a small world of
  their own (fruit, books, rooms), and show no code that solves any part of the exercise.
- **Word a repeated feature the same way each time.** Copy the note from another exercise.
- **It is paid content.** The API sends it only to a learner entitled to the exercise, exactly as it
  does the brief, and the download zip includes it on the same terms. So say nothing a Pro brief
  would not. It stays out of the public `Exercise`, like `notes.md`, and the loader does not
  validate it, as it does not validate `notes.md`.

## The learner toolkit

Learner code and tests import `forgeway_kit`, never the grader:

| Name | Purpose |
| --- | --- |
| `Message`, `Completion`, `Usage` | Provider-neutral chat types. `Usage` also has `cache_read_input_tokens` (part of `input_tokens`) and `reasoning_tokens` (part of `output_tokens`); `Completion` has `model` and `latency_ms`; `stop_reason` may be `"refusal"` |
| `ModelClient`, `StreamingModelClient` | Protocols: `complete(messages, *, system, max_tokens, temperature, tools)`; the second adds `model`, `response_format`, `tool_choice`, `effort` and `stream(...)` |
| `FakeModel(responder, context_window, models=, default_model=, rate_limit=, clock=, stream_chunk_tokens=)` | Deterministic model; records every `Request` in `requests`; the responder returns text, a list of `ToolCall`s, `Refusal(text)` or `StreamFailure(after_events, error, reply)`, or raises |
| `complete(..., model=, response_format=, tool_choice=, effort=)` | All recorded on `Request`. An unknown `model` raises `InvalidRequestError` when `models` is set; `response_format` (a JSON Schema) leaves the reply unchanged; `tool_choice` (`"auto"`, `"any"`, `"none"`, `{"name": ...}`) is enforced on the responder (`ValueError` if it breaks it); `effort` (`"low"`/`"medium"`/`"high"`) adds 16/64/256 `reasoning_tokens` |
| `Request` | `messages`, `system`, `max_tokens`, `temperature`, `tools`, `model`, `response_format`, `tool_choice`, `effort`, and `sample`: how many earlier recorded requests were identical (0 first), for varying answers across repeats |
| `ModelCard(name, input_usd_per_mtok, output_usd_per_mtok, cache_read_usd_per_mtok, base_latency_ms, ms_per_output_token, context_window)` | Data only. Sets `latency_ms` (`base_latency_ms + ms_per_output_token * output_tokens`) and the context window for that model |
| Prompt cache | `cache_read_input_tokens` is the longest common prefix with the previous recorded request to the same model: system and tools as one block, then each message, while identical |
| `RateLimit(max_requests, per_seconds)` | With `FakeModel(rate_limit=..., clock=...)`: `RateLimitError(retry_after_s=...)` past the limit, timed by `clock`; thread-safe |
| `stream(...)` events | `TextDelta(text)`, `ToolCallStart(id, name)`, `ToolCallDelta(id, partial_json)`, `ToolCallEnd(id)`, then `MessageEnd(stop_reason, usage)`. About `stream_chunk_tokens` tokens per text delta; arguments split at seeded character boundaries |
| `Tool`, `ToolCall` | Function calling: offer tools with `complete(..., tools=[...])`; answer each call with a `Message(role="tool", content=..., tool_call_id=...)` |
| `default_client()`, `use_client(client)` | The configured client (the fake in the sandbox). Outside grading only, with none configured, `FORGEWAY_LIVE` builds a live one |
| `forgeway_kit.live` | `AnthropicClient`, `OpenAIClient(model, base_url=)`, `Metered`, `client_from_env()`; `python -m forgeway_kit.live check`. Network code for local live mode: never used by graders, and refuses to start while grading |
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
title: A store, and a fix to chunking
summary: One line for the list.
added: [retrieval.vector-store]         # exercise ids; each list is optional
updated: [retrieval.metadata-filtering]
fixed: [retrieval.fixed-size-chunking]
---

The body, in Markdown, in the house voice: what changed and why it matters to a learner.
```

`forgeway content validate` checks every release note: the front matter parses, the version is
unique and matches the file name, the date is a real ISO date, and every exercise id exists. The
page links each listed exercise. Content loads at API start-up, so a release appears on the
next deploy. Once the note is merged, the release is tagged `v<version>` (`v2026.11.0`) and the
tag deployed: see "Cutting a release" in [deploy/vps/README.md](../deploy/vps/README.md).

## Style

UK spelling. Briefs are short: a paragraph of why it matters, a small example, then the task.
Use second person and plain language. Briefs and code never mention a presentation theme:
"quest" and "zone" belong in `content/themes/rpg/`, not here.
