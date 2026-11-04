# ADR 0009: Out-of-process learner code

Status: Accepted. Rolled out to every exercise, and the only mode, with all learner code as a
second user (see "Step 4 outcome")
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

**Opt in per exercise (superseded: see "Step 4 outcome").** `exercise.yaml` takes `isolation: process` (the default was `inprocess`).
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
having no `CAP_DAC_OVERRIDE`; see "Step 4 outcome" for why it now has no exceptions), and the harness makes `tests/` `0700` and `manifest.json` `0600`
before pytest runs. 
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
pipes and stderr. Outside the sandbox (tests of the bridge) the child runs as the same user. In a
container started as any other user the launcher refuses to run.

The socket-proxy's allow-list (ADR 0010) used to refuse any added capability. It now requires
`CapDrop: ["ALL"]` and `no-new-privileges`, and allows at most SETUID, SETGID and KILL back. This
was checked against the pinned proxy image: the runner's containers pass, and an extra capability,
a missing `--cap-drop ALL` or a missing `no-new-privileges` get a 403.

**gVisor.** `runsc` supports the calls the launcher makes (`setresuid`, `setgroups`,
`SCM_RIGHTS`, `SO_PEERCRED`, `prctl`), and Docker passes it the same capability set. It has not
been run under `runsc` here, as the development machine has no gVisor. Before relying on it in
production, grade the probe test and one process-mode capstone on the VPS (see "Grading time on
the production sandbox").

## Known limitations (what is not yet by construction)

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

Negative:

- Each process-mode attempt costs about 150 ms more, plus about 60 µs per crossing, and each
  `run_fresh` call one more interpreter. Exercises that restart often pay most.
- There is a second execution model to keep in mind when authoring. The survey's gaps above
  are the authoring rules for process mode.

## Alternatives considered

- **Separate containers for harness and learner code.** These give the strongest isolation, but
  need a cross-container channel and orchestration that the VPS runner does not have. A second
  UID in one container gets most of the benefit.
- **Pickle or a general RPC library** (`multiprocessing.managers`, Pyro, RPyC). Rejected.
  Unpickling child data in the parent is code execution, and general libraries expose far more of
  the parent than a guarded public face.
- **Static analysis of submissions.** Rejected. It cannot keep up with `getattr` and `exec`.
