# ADR 0009: Out-of-process learner code

Status: Accepted. Rolled out to the three archetypes, all nine capstones and every
guided-project milestone, with learner code as a second user (see the rollout)
Date: 2026-10-26

## Context

ADR 0003 records the root weakness of in-process grading. Learner code shares an interpreter with
the hidden tests, so it can walk the test's frames (`sys._getframe`), read a fake's script
(`client.responder.__closure__`), reach a handler's closure, monkeypatch the test module or a module
the tests import, and touch the grader's own loaded modules. Authors have worked around this
exercise by exercise ("Expected values in the caller's frame" in `docs/authoring.md`). The Phase 4
plan makes the fix a spike first: a pure function, a stateful class, and an agent loop that
receives `handler=` callbacks.

A survey of every hidden test found that 63 pass responder closures, 14 pass handler or tool
callables into learner code, 17 pass `now=` clocks and 5 pass store objects. 41 define classes,
38 use `pytest.raises` on learner exceptions, 32 use iterators or generators, 11 `getattr` on
learner objects and 3 use threads. 48 already canonicalise results with a JSON round trip.

## Decision

**Opt in per exercise.** `exercise.yaml` takes `isolation: process` (the default is `inprocess`).
`Exercise.isolation` is validated in the domain model and allowed for the `python` runtime only.
`SandboxRequest` carries it, and `build_archive` writes it into `manifest.json` only when it is not
the default, so in-process archives are byte-for-byte what they were. The harness reads it and
makes one switch: `bridge.install(submission)` instead of `guard.install` plus `sys.path`.

**Two interpreters, one container.** The hidden tests, pytest and the grader stay in the parent
(the harness). Learner modules are imported in a child interpreter. The child starts at the
first learner import, from `sys.executable -s -P -c <source>`, where the source is the text of
`lattice_grader/bridge/peer.py`. It has an environment built from scratch, `close_fds`, and the
same working directory. The child never imports `lattice_grader`. It deletes the import guard
that the image's `.pth` loads, and puts a finder in front that refuses `lattice_grader` to
everyone. No test code runs there, so nothing legitimate needs it.

**Proxy modules.** A finder at the *end* of the parent's `sys.meta_path` serves any module that
exists in the submission and nowhere on the parent's path. `import store` then returns a
`ProxyModule`. Attribute reads, writes and deletes on it go to the child's real module, so
`from store import VectorStore` and `monkeypatch.setattr(store, ...)` work unchanged.

**A small symmetric RPC** (`bridge/peer.py`) runs over the child's stdin and stdout, which the
child moves to private descriptors at once. It uses newline-delimited JSON. The requests are
`call`, `getattr`, `setattr`, `delattr`, `import`, and operators: `repr`, `str`, `len`, `iter`,
`next`, `bool`, `hash`, comparisons, `getitem`, `setitem`, `delitem`, `contains`, `enter`, `exit`
and `dir`. Calls nest. While one end waits for its reply, it serves the other end's requests, so
a `FakeModel` call from inside learner code is a reverse call into the parent.

**What crosses by value.** `None`, `bool`, `int`, `float` and `str` cross by value, read with the
base types' own methods, so a `str` subclass arrives as a plain `str`. So do `bytes`, `list`,
exact `tuple`, `dict` (any keys), `set` and `frozenset`, `datetime`, `date` and `timedelta`, and
frozen `forgeway_kit` dataclasses (`Message`, `Tool`, `ToolCall`, `Completion`, `Usage`,
`Request`), which are rebuilt with their constructors. Builtin and `forgeway_kit` classes cross by
name. Names are looked up only in `builtins` and `forgeway_kit`, and only classes are accepted.

**Everything else is a handle.** Learner classes arrive as mirror classes with the learner's
name, qualified name and module, so `isinstance(store, VectorStore)` holds and `type(h).__name__`
reads `Hit`. Their instances are proxies. Functions and generators passed in become callable or
iterable proxies at the other end. A handle sent home arrives as the original object.

**Exceptions.** Builtin and `forgeway_kit` exceptions are rebuilt as the same class, with their
args and public attributes. A learner exception class arrives as a mirror exception class with
the learner's names and its builtin bases, so `pytest.raises(StoreError)` (imported through the
proxy) and `pytest.raises(ValueError)` both work. An exception that crosses and comes back, such
as a test handler's `RuntimeError("disk full")` that learner code fails to catch, arrives as the
original object. The child attaches learner-file frames (`agent.py, line 22, in _run`), and
`ReportPlugin` uses them, so messages read as they do in-process.

**The guarded end.** Every object the parent hands over is reachable only through its public
face. Learner code may call it, use its read operators (`len`, `==`, `in`, `[key]`, iteration),
and read public bound methods and plain-data attributes and properties. Private and dunder
attributes are refused (except `__name__`, `__qualname__` and `__doc__`). So are attributes and
properties holding functions or objects (`FakeModel.responder`, `Meter.model`) and every
attribute write. Item writes and deletes apply only to a store, a `MutableMapping` or
`MutableSequence` object (the tests' `StrictData` and `Rows`), `next()` only to an iterator, and
`with` to no test object. Handles are random 53-bit numbers, so learner code can name only
objects it was given, never one given to another call or prepared for a send that failed. Each
child message is untrusted input: a malformed message, a handle never issued, or a class outside
`builtins` and `forgeway_kit` breaks the channel and kills the child. An exception's private
attributes (`__class__`, `__cause__`, `__learner_frames__`) are never set from what the child
sends; its learner frames come in a field of their own, at most five lines of 500 characters.

**Failures are learner-facing.** The parent waits at most 10 seconds for any one message.
Silence means "Your code did not finish within 10 seconds, so the grader stopped it…". A child
that dies is reported by its signal ("killed by SIGKILL; it may have used too much memory") or
its exit status ("exited with status 3 … sys.exit() or os._exit()?"). These are
`LearnerProcessError`, a `BaseException`, so a test's `pytest.raises(Exception)` or
`except Exception` cannot mistake a dead child for the error it expected; pytest fails the test
and `ReportPlugin` shows the message as written. Later calls in the same run say the process
"stopped earlier in this run". Learner `print` output is forwarded to the parent's
`sys.stdout`, so pytest still captures it per test, up to 100,000 characters a run, then a note
that the rest was dropped. Output is not activity: a loop that prints and sleeps still times out.

**Threads.** Each thread's calls, with the calls nested in them, are one conversation, tagged
on every message (`p0` is the parent's main thread, `c3` a learner thread). A reader thread
at each end hands each message to the thread waiting on its conversation. A call that opens
a new conversation is served by a new thread at the other end, so a learner thread pool's
calls are in the tests' fakes at the same time, and a `threading.Barrier` there still meets.
The parent serves at most 32 learner threads at once; more breaks the channel. The 10-second
limit is silence on the whole channel, not on one conversation, so a main thread waiting on a
busy pool is not timed out. A parent thread counts as busy only while it runs a test's code
for the child, not while it waits on the child, so two ends waiting on each other (a reflected
`__eq__` that hangs in learner code) time out after 10 seconds.

**`run_fresh` and re-imports.** When the harness bridges a submission, `run_fresh` bridges it
too: the session function runs in the fresh interpreter, and the learner modules it imports
run in a bridge child beneath it. A learner module that a test drops from `sys.modules` and
imports again runs afresh in the child. When the tests drop every learner module they hold,
the child drops all of them (the usual `for name in MODULES: sys.modules.pop(name)`).

**A test's own `BaseException`** (a simulated crash) stays a `BaseException` in the child, so
learner `except Exception` cannot swallow it. Only the guarded end turns `BaseException`
look-alikes into ordinary exceptions.

**Identity: a second user.** The container starts as root (`--user 0:0`) with
`--cap-drop ALL --cap-add SETUID --cap-add SETGID --cap-add KILL` and `no-new-privileges`. Its
entrypoint, `lattice_grader.launcher`, stays root and does no grading. It starts the harness as
UID 10001 and steps off stdin and stdout. It then serves one request over a Unix socket: start a
bridge child as UID 10002 on the pipes the asker passes (`SCM_RIGHTS`), report its exit status,
and kill it on request. Only UID 10001 is served (`SO_PEERCRED`), and only the interpreter may be
started. The harness and every `run_fresh` session ask it, so learner code beneath a session is
10002 too. Every process it starts calls `setgroups([])` and sets all three uids and gids, so it
keeps no capability, and `no_new_privs` means no exec regains one. As PID 1 it reaps orphans,
and when the harness exits it kills whatever is left.

The image makes the grader package `root:10001`, `0750` and `0640` (root reads it as its owner,
having no `CAP_DAC_OVERRIDE`), and the harness makes `tests/` `0700` and `manifest.json` `0600`
before pytest runs. Two parts stay readable, because servers that learner code starts run them:
the package's docstring-only `__init__`, and `project_research_reference`, which holds only the
tap (a stdio relay that logs what reaches a learner's server). The package's file names stay
listable, as Python's importer lists a directory to find a module in it.

What the tests share with learner code stays shared. The submission is world-readable and
`/work` world-writable, so learner code reads its own files and writes beside them. Each
`tmp_path` is opened (`0777`, with `0711` above it, so other tests' directories cannot be
listed), and in process mode the harness sets its umask to 0 once the tests are private, so
the files and directories the tests make there are writable by learner code, as they were
in-process. `run_fresh` opens each session's scratch directory in the same way. The image's
`.pth` guard skips itself quietly when 10002 cannot read the guard; that user needs no guard.

So learner code in a bridge child cannot read the hidden tests, even during collection, nor the
grader or its `*_reference` packages. It cannot open `/proc/<pid>/environ`, `mem`, `fd`, `maps`
or `cwd` of the launcher or the harness, signal them, or `setuid` back to 10001. The proof is
`test_out_of_process_learner_code_cannot_reach_the_tests_or_the_grader` in
`backend/tests/integration/test_sandbox_hostile.py`. Its probe runs at import time, while the
tests are still on disk, and tries each of these. Started as 10001, the same probe reads the
test file, lists and reads the grader package and signals the harness.

The parent still sets `PR_SET_DUMPABLE` to 0, and the child still inherits no descriptor but its
pipes and stderr. Outside the sandbox, or in a container started as any other user, the launcher
execs the harness in its place and the bridge starts the child itself as the same user, as before.

The socket-proxy's allow-list (ADR 0010) used to refuse any added capability. It now requires
`CapDrop: ["ALL"]` and `no-new-privileges`, and allows at most SETUID, SETGID and KILL back. This
was checked against the pinned proxy image: the runner's containers pass, and an extra capability,
a missing `--cap-drop ALL` or a missing `no-new-privileges` get a 403.

**gVisor.** `runsc` supports the calls the launcher makes (`setresuid`, `setgroups`,
`SCM_RIGHTS`, `SO_PEERCRED`, `prctl`), and Docker passes it the same capability set. It has not
been run under `runsc` here, as the development machine has no gVisor. Before relying on it in
production, grade the probe test and one process-mode capstone on the VPS (see "Grading time on
the production sandbox").

## Results on the archetypes

The tests are unchanged in all three. Every solution passes and every existing wrong case fails
its declared check with its declared message in process mode. New `cheat-*` wrong cases pin the
following (graded in Docker with `lattice-sandbox-python:oop`):

| Exercise | Cheat | In-process | Out of process |
| --- | --- | --- | --- |
| first-completion | rewrites the test's `model.requests` found via `sys._getframe` | passes `sends-question` | fails, "exactly the question" |
| first-completion | reads the reply from `client.responder` | passes `returns-reply` | fails, "completion's text unchanged" |
| first-completion | patches `forgeway_kit.llm._serialise`, which the tests' `FakeModel` uses | passes `sends-question` | fails, "exactly the question" |
| vector-store | replaces the hidden test module's `plain()` helper | passes `cosine` | fails, "raw dot product" |
| agent-loop-budgets | edits the test's `Tools.ran`, found via `sys._getframe` | passes `token-budget` | fails, "must not run" |
| agent-loop-budgets | edits `Tools.ran` through a handler's `__closure__` | passes `token-budget` | fails, "must not run" |

The grader's modules are another cheat surface. In-process, `lattice_grader.harness`, `plugin`,
`report` and `guard` sit in `sys.modules` beside learner code. In the child, `sys.modules` holds
no `lattice_grader` and no test module, and importing either is refused (`grader/tests/test_bridge.py`).

**Overhead.** These are medians of five Docker runs of each solution:

| Exercise | In-process | Out of process |
| --- | --- | --- |
| first-completion | 409 ms | 558 ms |
| vector-store | 454 ms | 635 ms |
| agent-loop-budgets | 449 ms | 584 ms |

That is about 135–180 ms per attempt. Outside Docker, the child starts and imports in about
40 ms. A round trip costs about 60 µs, or about 300 µs for a 256-float vector.

## What the survey's categories need

- **Responder closures (63).** They work. The fake stays in the parent, and learner code sees a
  proxy with `complete`. Requests and completions are `forgeway_kit` values.
- **Handler and tool callables (14).** They work as reverse calls (proven by agent-loop-budgets).
  Learner code that inspects a handler (`inspect.signature`, `__code__`, `__defaults__`) is
  refused. Exercises that build schemas from functions must pass schemas, or stay in-process.
- **`now=` clocks (17).** They work. A clock is a reverse call, and `datetime` and `float`
  values cross by value. Each tick is one round trip.
- **Store objects (5).** Their methods and properties work. Attribute writes are refused, and a
  `list` or `dict` passed in arrives as a copy. A test that checks how learner code *mutated* a
  container it was given must use a store object or a return value.
- **Classes defined in tests (41).** Instances passed in work through their methods and plain
  data. Learner classes are mirrored for `isinstance`. Subclassing a learner class in a test is
  not supported, and constructing the subclass raises a clear `TypeError`.
- **`pytest.raises` on learner exceptions (38).** These work through mirror classes, builtins
  and kit classes. A custom `__str__` is kept as the message. Custom attributes cross if they
  can.
- **Iterators and generators (32).** They work by handle, with each `next()` a round trip and
  `StopIteration` values kept. Parent generators are consumed by the child. `send` and `throw`
  are ordinary method calls but are not yet exercised.
- **`getattr` on learner objects (11).** It works: reads return values or handles.
- **Threads (3).** They work: each thread is a conversation of its own (see Decision). The
  durable research desk, durable-team and team-evals run their worker pools out of process.
- **JSON canonicalisation (48).** This is compatible. The bridge already rebuilds plain built-ins,
  so these round trips become belt and braces.

Other gaps:

- `from learner import *` imports nothing.
- `inspect.getsource` works on proxy modules (they have `__file__`) but not on proxied functions.
- `dict` and `list` subclasses arrive as plain containers. A `NamedTuple` is a handle.
- A learner dataclass instance is a handle, so `dataclasses.is_dataclass` is false in the
  parent. Its `__dataclass_fields__` (a dict) crosses, so tests read fields by name.
- A function stored on an instance the tests pass in (`SimpleNamespace(complete=fn)`) is
  refused like any function-valued attribute. Tests wrap it in a method.
- `forgeway_kit.default_client()` and `use_client` are not forwarded (no hidden test uses them).
- Handles are never released during a run.

## Known limitations (what is not yet by construction)

- **Scripts the tests start** (the mcp-gateway, its peers and the project-research tool
  servers) are learner code run with `sys.executable` by the tests, so they run as 10001, beside
  the harness. They can read what the harness can, and are guarded by the image's `.pth` only.
  Starting them through the launcher too is the next step.
- **In-process exercises** are unchanged: learner code shares the harness's interpreter and user.
- **A runner that does not start as root** silently falls back to one user. The probe test
  above fails if that happens.
- **Inside the child**, learner code can write anything to the pipe. That is why the parent
  treats every message as untrusted and fails closed.
- **The 10-second limit is per message, not per call.** Learner code that keeps calling a test's
  fake (a loop polling `model.complete`) is activity, so only the container's wall clock stops
  it. Printing and nested waits no longer count (see "Failures are learner-facing").

Closed after an independent review (26 October), each with a regression test in
`grader/tests/test_bridge.py`:

- The silence limit could be held open forever: a parent thread serving a learner thread
  counted itself as busy while it waited on that learner thread (a reflected `__eq__` hanging
  in the child), and every `print` reset the clock. Now only threads running test code count,
  output does not, and output is capped.
- Write operators (`[key] = value`, `del`, `next`, `with`) applied to any test object; property
  values skipped the plain-data check; a forged exception could set `__class__`, `__cause__` or
  `__learner_frames__`; handles were sequential, so learner code could name an object it had
  never been given. Each is refused as described under "The guarded end".
- `LearnerProcessError` was an `AssertionError`, so `pytest.raises(Exception)` accepted a dead
  child as the error a test expected. It is now a `BaseException`.

## Consequences

Positive:

- The fixes from ADR 0003's known limitation (computing expected values after learner code
  returns, sealing scripts) stop being needed for exercises in process mode. Tests need no
  changes for the common shapes.
- Results are canonicalised by construction, which kills `str`-subclass and `__eq__` tricks.
- The default path is untouched, so the rollout can be gradual.

Negative:

- Each process-mode attempt costs about 150 ms more, plus about 60 µs per crossing, and each
  `run_fresh` call one more interpreter. Exercises that restart often pay most: the durable
  research desk (63 restarts) went from 23 s to 32 s of its 60 s limit.
- There is a second execution model to keep in mind when authoring. The survey's gaps above
  are the authoring rules for process mode.

## Rollout plan

1. **Capstones and guided projects first.** They carry the most weight, and their tests are the
   richest (clocks, stores, handlers). Each flip re-runs that exercise's wrong cases plus the
   Phase 3 probes, which should now fail by construction, and adds a `cheat-*` wrong case where a
   probe used to pass.
2. **Then branch by branch.** The threaded exercises no longer need to stay in-process.
3. **The second UID.** Done (see "Identity: a second user"), apart from scripts the tests
   start.
4. **Make process mode the default**, once every exercise either passes in it or records why it
   cannot.

### Step 1 outcome: capstones and guided projects

Done. All 9 capstones and every guided-project milestone (16 exercises, as two milestones are
also capstones) run with `isolation: process`; none is left in-process. Every solution passes and every wrong case fails its declared check with its
declared message (`lattice content test`, image built from this branch). Three bridge changes
made that possible, all in `lattice_grader/bridge/` with unit tests: per-thread conversations,
a test's `BaseException` kept as one in the child, and fresh re-imports. `run_fresh` bridges a
bridged submission in its own child (`lattice_grader/isolation.py`).

Test changes, all for the shapes listed in "What the survey's categories need":

- **Stores became objects.** `StrictData`/`StrictStore` were `dict` subclasses that learner code
  wrote to; they are now `MutableMapping`s over a private dict (customer-memory,
  personal-assistant, durable research desk, durable-team, team-evals). The copilot milestones'
  `test_earlier.py` hands `CustomerMemory` a `Rows` mapping instead of `{}`.
- **Function attributes became methods.** The desk's `SimpleNamespace(complete=fn)` client is a
  `Client` with one method; durable-team's `Metered.complete` lambda is a method; the
  guardrails `Spy` returns bound methods.
- **Dataclass fields by name.** personal-assistant's `canon` reads `__dataclass_fields__`.
- **One message moved.** context-builder's `sources-lookalike-list` (a `list` subclass equal to
  anything) now arrives as a plain empty list, so it fails `citations` on the ordinary message
  ("sources should be the cited document ids") rather than "must be a plain list".

Learner child processes are unchanged: the gateway in mcp-gateway, its peers, and the
project-research tool servers are scripts the tests start with `sys.executable`. They run beside
the bridge child, guarded by the image's `.pth` as before. `run_fresh` sessions (customer-memory,
personal-assistant, desk, the copilot and research milestones) keep the session function in the
fresh interpreter and the learner code in a bridge child beneath it.

The Phase 3 probes (rag, gateway, desk, graph, memory, evals, context, copilot and research
reviews, the answer-key sweep) were re-run over the solution in both modes (`lattice content
probe ... --base solution`, and the same grading forced in-process). Each one that the hardened
tests already failed in-process still fails, on the same checks (context-builder's
`sources-anything` fails fewer: its look-alike list now arrives plain); the controls and fair
variants still pass. None passed in-process, so each capstone gained new `cheat-*` wrong cases that pass every targeted check in-process and
fail it, with the original message, out of process:

| Exercise | Test changes | Cheat cases (technique) | Solution in-process → process |
| --- | --- | --- | --- |
| retrieval.rag-service | none | `cheat-rewrites-the-test-log` (frames), `cheat-blanks-the-test-module` (test module) | 1.2 s → 2.6 s |
| protocols.mcp-gateway | none | `cheat-blanks-the-test-module` | 7.7 s → 7.8 s |
| orchestration.durable-research-desk | store object, client method | `cheat-reads-the-client-closure` (closure), `cheat-blanks-the-test-module` | 23.1 s → 32.3 s |
| knowledge-graphs.graphrag-service | none | `cheat-blanks-the-test-module` | 0.5 s → 1.0 s |
| memory.personal-assistant | store object, fields by name | `cheat-rewrites-the-session-record` (`run_fresh` session frames) | 9.5 s → 14.0 s |
| context-engineering.context-builder | one wrong-case message | `cheat-blanks-the-test-module` | 0.6 s → 1.3 s |
| evals.support-bot-pipeline | none | `cheat-blanks-the-test-module` | 0.6 s → 0.8 s |
| project-copilot.help-centre-index | none | — | 0.7 s → 1.1 s |
| project-copilot.customer-memory | store object | — | 4.1 s → 7.1 s |
| project-copilot.turn-context | `Rows` in `test_earlier` | — | 0.9 s → 1.6 s |
| project-copilot.guardrails | `Rows`, bound-method spy | — | 0.9 s → 1.5 s |
| project-copilot.release-gate (capstone) | `Rows` in `test_earlier` | `cheat-blanks-the-test-module` | 1.0 s → 1.9 s |
| project-research.tool-servers | none | — | 1.7 s → 1.7 s |
| project-research.research-graph | none | — | 1.1 s → 1.7 s |
| project-research.durable-team | store object, `Metered` method | — | 16.1 s → 17.9 s |
| project-research.team-evals (capstone) | store object | `cheat-blanks-the-test-module` | 22.9 s → 25.2 s |

Times are medians of three Docker runs of each solution on a quiet machine. The cost is about
0.4 to 1.4 s for most exercises, and grows with `run_fresh` restarts and crossings (the
desk, personal-assistant and customer-memory). The desk is the tightest, at 54% of its limit.
Under heavy host load, the restart-heavy exercises (desk, personal-assistant, customer-memory)
ran past their limits in both modes alike; on a quiet host every one passed. Process mode leaves
less slack, so the desk is the first candidate for fewer restarts if production hosts are slower.

`cheat-blanks-the-test-module` swaps every hidden test function's body for one that does
nothing, from the first learner call onwards. In-process it passes every check that runs after
that call, whatever the code does. It is the bluntest proof that the test module is out of reach.

### Grading time on the production sandbox

Production grades under gVisor (`runsc`) on a 2-vCPU VPS, with the sandbox capped at one CPU.
There the four restart-heavy exercises took 65 to 128 s, past their 60 s limits, and passed
only with `LATTICE_SANDBOX_TIMEOUT_FACTOR=3`. Learners waited, and the single worker served no
one else meanwhile.

**The cause was compiling, not restarting.** The `python:3.12-slim` base image ships the
standard library without `.pyc` files, and the sandbox's root filesystem is read-only, so
every interpreter compiled `re`, `enum`, `pathlib` and the rest from source on every start:
a bare start took 56 ms in the local Docker sandbox, `import pytest` 222 ms. The image now
runs `compileall` over the standard library (19 MB more). A bare start takes 12 ms and
`import pytest` 61 ms. That helps every interpreter: the harness, each bridge child, each
`run_fresh` session and each server a test starts.

**A `run_fresh` child no longer imports pytest** unless the session uses it. Test modules
import it for their marks, and importing it was about half of a session's start. The child
puts a stand-in in `sys.modules`: `pytest.mark.<name>(...)` leaves the function as it is, and
any other attribute imports the real pytest (`grader/tests/test_isolation.py`). A bridged
session went from 91 to 55 ms.

**Learner code stays beneath the session.** We considered letting `run_fresh` import the
submission straight into the session's interpreter (`bridge=False`), which saves one
interpreter start per call. We rejected it. That interpreter holds the session's fakes and
the evidence it returns: the requests a model received, the events, the tool effects and the
store. Learner code there can walk up to the session's frames, or find those objects with
`gc`, and rewrite them before they are returned. personal-assistant's
`cheat-rewrites-the-session-record` does this: with `bridge=False` it passes all 8 checks,
and bridged it fails `tool-access` as declared. The bridge child costs about 35 ms a call
locally, which is the price of keeping that evidence out of reach.

**Test changes, none weakening a check:**

- **The desk's worker stagger only where it proves something.** Each worker slept
  `0.02 × (subtasks − position)` s, so later subtasks finished first. That was about half the
  desk's time, paid on every run. The stagger now runs only in `fan-out` and `handoff`, which
  assert plan order against finishing order, and in lifetimes that crash during the fan-out,
  where it fixes the crash point. Elsewhere workers answer at once. No other check compares
  finishing order.
- **The desk's first lifetimes run in the test's process.** A `step` that starts from an
  empty store has nothing to carry over. It runs in the harness's own process, with the
  project imported afresh and learner code in the bridge child. Every step that carries a run
  on from the store is still a new interpreter: 36 of the 63.
- **personal-assistant's isolation check runs its six interleaved turns in one process**, not
  six. Then the recall runs in a new one. Persistence is proved by the checks that own it, and
  in-memory leaks between users are now visible too.
- **durable-team's `max_workers` meter waits on an event.** The first two workers wait for
  each other, then 0.4 s for a third that a pool ignoring `max_workers` would start. Before,
  each worker slept 0.4 s.

Every solution passes and every wrong case, `cheat-*` and `borrows-the-grader` included,
fails its declared check with its declared message (`forgeway content test --time`, factor
1). These are the solution times in the local Docker sandbox (one CPU):

| Exercise | Before | Image + `run_fresh` | + test changes | Production estimate |
| --- | --- | --- | --- | --- |
| orchestration.durable-research-desk | 33.4 s | 15.9 s → 7.8 s | 6.1 s | ~23 s (×3.8) |
| project-research.team-evals | 26.2 s | 7.2 s → 6.8 s | (unchanged) | ~33 s (×4.8) |
| project-research.durable-team | 18.1 s | 6.7 s → 6.1 s | 5.3 s | ~24 s (×4.5) |
| memory.personal-assistant | 13.7 s | 4.2 s → 2.8 s | 2.5 s | ~12 s (×4.75) |

"Image + `run_fresh`" shows the time with the compiled standard library, then with the pytest
stand-in as well. The estimates scale each local time by that exercise's measured ratio of
production to local time before the change. gVisor makes process starts and pipe I/O dearer
than compute, so the true ratio may now be higher. Measure on production before setting
`LATTICE_SANDBOX_TIMEOUT_FACTOR` back to 1. The budget for new content is in
`docs/authoring.md` ("Grading time").

### Step 3 outcome: the second UID

Every process-mode exercise's solution and wrong cases were graded again with the launcher image
(`forgeway content test --only <id> --time`, local Docker, default runtime): all 193 cases
graded as declared, no solution over the 15 s budget. Two scripts the tests hand to learner code
needed the permission changes above: project-research's tap (`python -m
lattice_grader.project_research_reference.tap`) and the `tmp_path` files its servers read and
write.

The table gives median solution times over three runs, with the same image started as root (two
users) and as 10001 (one user, the fallback). The difference is within run-to-run noise: the
launcher costs one interpreter start per attempt and a socket round trip per bridge child.

| Exercise | One user (s) | Two users (s) |
| --- | --- | --- |
| context-engineering.context-builder | 1.8 | 1.8 |
| evals.support-bot-pipeline | 0.8 | 0.7 |
| knowledge-graphs.graphrag-service | 1.4 | 1.4 |
| memory.personal-assistant | 3.9 | 3.9 |
| orchestration.agent-loop-budgets | 0.5 | 0.5 |
| orchestration.durable-research-desk | 8.7 | 8.8 |
| project-copilot.customer-memory | 3.2 | 3.7 |
| project-copilot.guardrails | 1.6 | 1.4 |
| project-copilot.help-centre-index | 1.4 | 1.5 |
| project-copilot.release-gate | 2.0 | 1.9 |
| project-copilot.turn-context | 1.5 | 1.6 |
| project-research.durable-team | 7.7 | 7.5 |
| project-research.research-graph | 1.1 | 1.1 |
| project-research.team-evals | 13.8 | 12.5 |
| project-research.tool-servers | 1.0 | 1.4 |
| protocols.mcp-gateway | 4.9 | 4.5 |
| retrieval.rag-service | 5.3 | 4.9 |
| retrieval.vector-store | 0.5 | 0.5 |
| starter.first-completion | 0.4 | 0.4 |

## Alternatives considered

- **Separate containers for harness and learner code.** These give the strongest isolation, but
  need a cross-container channel and orchestration that the VPS runner does not have. A second
  UID in one container gets most of the benefit.
- **Pickle or a general RPC library** (`multiprocessing.managers`, Pyro, RPyC). Rejected.
  Unpickling child data in the parent is code execution, and general libraries expose far more of
  the parent than a guarded public face.
- **Static analysis of submissions.** Rejected. It cannot keep up with `getattr` and `exec`.
