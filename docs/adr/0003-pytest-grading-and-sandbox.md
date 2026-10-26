# ADR 0003: Pytest-only grading and the sandbox threat model

Status: Accepted
Date: 2026-10-25

## Context

Each exercise is graded by running learner code against hidden tests. Deterministic and behavioural
checks must share one mechanism. Learner code is untrusted, so the sandbox must protect the host.
The threat model follows the stakes: there are no prizes, and leaderboards are opt-in.

## Decision

**Pytest only.** Every check is a pytest test. `lattice_grader` supplies fixtures: `fake_llm`
(deterministic and recording), an offline embedder and branch helpers such as `recall_at_k`.

**Two packages with a hard boundary.** `forgeway_kit` is the learner API (`ModelClient`, `Embedder`,
`default_client()`). Learner code imports only this. `lattice_grader` is the harness. It is in the
sandbox image and hidden tests import it; learner code must not. In live mode `default_client()`
returns a proxy-backed client, so exercises do not change between modes.

**The boundary is enforced, twice.** The grader's reference implementations (`*_reference`)
contain the behaviour exercises teach, and an end-of-phase review borrowed them in one line for
memory, retrieval and protocols exercises. So:

- The harness fails every check, without running anything, when a submission file's text
  contains `lattice_grader` (comments included). This is a string test: it stops the plain
  import and nothing spelt otherwise.
- `lattice_grader.guard` refuses the import itself with a learner-facing `ImportError`
  ("lattice_grader is the grader's own code; your solution must not import it") when it comes
  from a file under the submission directory. It hooks `sys.meta_path` (first loads),
  `builtins.__import__` (every `import` statement, also for a module a test already loaded) and
  `importlib.import_module`, and decides by walking the stack: frames in the standard library,
  other installed packages and generated code (`exec`, `<frozen importlib>`) are passed over, and
  the first other frame decides. Hidden tests and the grader may import it; submission files
  may not, however they route the call.
- The harness installs the guard before pytest imports anything. `run_fresh` passes the guarded
  roots to its child, which installs the guard before loading the test file. A `.pth` file in
  the image's site-packages installs it for `/work/submission` in every other interpreter that
  starts with `site` (servers and peers the tests start), so a learner script run as a child is
  guarded too. Children started with `python -S` do not run `site`; there `lattice_grader` is
  not on the path at all.

Every exercise whose tests use a reference package has a `borrows-the-grader` wrong case: its
reference solution plus one import spelt to dodge the string test, which must fail.

**Sandbox controls.** The nonce (one line), then the submission, hidden tests and a manifest as a
tar archive, travel on stdin, so nothing is mounted and nothing secret is in the environment. `DockerSandboxRunner._command` runs the container with:

- `--network none`, `--read-only` root filesystem
- `--user 0:0`, `--cap-drop ALL`, `--cap-add SETUID SETGID KILL` and
  `--security-opt no-new-privileges`: the entrypoint, `lattice_grader.launcher`, runs the harness
  as UID 10001 and out-of-process learner code as 10002, neither with any capability (amended by
  ADR 0009; it was `--user 10001:10001` with no capabilities)
- `--tmpfs /work` (32 MB) and `--tmpfs /tmp` (8 MB), both `nosuid,nodev,noexec`
- `--memory` with `--memory-swap` equal (no swap), `--cpus 1.0`, `--pids-limit 64`. The memory
  limit is the exercise's `limits.memory_mb`, capped at `LATTICE_SANDBOX_MAX_MEMORY_MB` (default
  768) whatever the exercise declares, so several sandboxes fit on the VPS at once
- `--ulimit nofile=256:256` and `--ulimit fsize=16777216:16777216` (16 MiB per file)
- `--rm` and `--label lattice.role=grader` (no `--env`: the nonce comes on stdin)

No seccomp override is passed, so Docker's default profile applies. No volumes are mounted and the
container is not privileged. The runner adds a wall-clock deadline (`timeout_s` plus 10 seconds,
enforced with `docker kill`) and output caps of 1 MiB (stdout) and 64 KiB (stderr).

**Nonce and worker-side checks.** Each attempt gets `secrets.token_hex(16)`. The harness reads it
from the first line of stdin, before the archive, and keeps it only in a local variable. The harness
must print
exactly one `LATTICE-REPORT <nonce> <json>` line. `interpret()` grades as `errored` any run whose
report has no single matching line, is unparseable, has a check set differing from the exercise, or
whose overall pass disagrees with pytest's exit status. `errored` does not count against the
learner. `validate_submission` accepts only declared editable files, each at most 64 KB.

**Deployment split.** Mounting `docker.sock` is root-equivalent on the host, so only local
development and CI give the worker the socket. Production is a single shared VPS (ADR 0010): the
same Docker runner starts every sandbox under gVisor (`--runtime runsc`), and the worker runs
unprivileged and reaches Docker only through a socket-proxy. The proxy allows the few calls the
runner makes, and only sandbox-shaped containers. Cloud Run Jobs on gVisor, behind the same
`SandboxRunner` port, is the scale-up path if the VPS stops being enough. Live-model mode routes
through an egress proxy that holds the platform key, so the key never enters the sandbox.

**Hidden tests leave the disk before learner code runs.** Once pytest has collected the hidden
tests (importing every test module and, through them, the learner's modules), a harness plugin
(`pytest_collection_finish`) reads each test file's source into memory and deletes `/work/tests`.
Learner code that runs at call time finds no test files to read. Two things re-read test files
and are handled:

- `run_fresh` loads the test file afresh in a child interpreter. The harness hands the sources
  to `lattice_grader.isolation.remember_sources` before deleting them, and `run_fresh` sends the
  child that source, compiled under the original file name, instead of the path.
- Exercises that start children (the protocols peers and stdio servers, the project-research
  tool servers) start learner scripts from `/work/submission` or the grader's own modules, never
  a file under `/work/tests`, so nothing else needs the files. No test file reads a data file
  beside it; a future one that does must embed the data instead.

Every shipped exercise still grades with this in place (`forgeway content test`, all branches).

## Known limitation

Learner code runs in the same process as the hidden tests, as the same user, in the same
container. A determined learner can subvert grading:

- The nonce is no longer in the environment or on disk, but it is in the harness's memory. Learner
  code in the same process can find it (walking the stack's frames to the harness's `main`, or
  reading `/proc/self/mem`), print a correct report line and call `os._exit(0)`, so the
  consistency checks pass. Reading it now takes deliberate evasion rather than one file read.
- Hidden tests leave the disk after collection, but the test modules stay in memory (they must,
  to run), and learner code imported at collection time runs before they are deleted. Learner
  code can still reach expected values through `sys.modules`, the test functions' code objects
  or the source kept for `run_fresh`.
- Anything the harness imports can be monkeypatched in-process.
- The import guard is in-process too. Learner code can remove its hooks, take a module the tests
  already loaded straight from `sys.modules`, compile code under a hidden test's file name, or
  put site-packages back on the path of a `python -S` child. Each takes deliberate evasion of a
  stated rule; the guard stops borrowing, not an attacker.
- Scripted fakes are reachable too. A fake model's responder is a closure, and learner code can
  walk its cells (`client.responder.__closure__`) or the test's frames (`sys._getframe`). Tests
  therefore compute expected values only after learner code returns, and keep inputs, not
  answers, in their frames and in the objects they hand over (see "Expected values in the
  caller's frame" in `docs/authoring.md`). A fake's script is still in its closure: the Retrieval
  capstone seals its verdict plan with a per-model key, but the closure holds the key too, so
  that only stops a casual read. Code that unseals it learns each verdict before the verifier is
  asked; that is the in-process limit above, not a new one.

The checks catch careless tampering and harness bugs. They are not an adversarial boundary.

The stdin nonce and the deleted test files (Phase 4) raise the cost of the easy, one-line routes;
they do not change this conclusion.

Exercises that set `isolation: process` run learner code in a child interpreter instead, so the
test's frames, fakes, closures and modules are out of its reach. ADR 0009 records the bridge and
what is still not by construction.

This is acceptable for now: a subversion gains a learner progress on their own account only, and the
sandbox still protects the host. It must be revisited before grades carry external weight, such as
certificates (Phase 4). The harness must then run in a different container or OS identity, with the
hidden tests off the learner's filesystem.

## Consequences

Positive:

- One mechanism for deterministic and behavioural checks. Authors write pytest.
- Controls are verified by hostile-submission tests (fork bomb, infinite loop, network access,
  forged report, and others).
- The `SandboxRunner` port lets production change runners (gVisor on the VPS today, Cloud Run
  Jobs later) without changing exercises.

Negative:

- The Docker runner can be used in production only under gVisor and behind the socket-proxy
  (ADR 0010); the raw socket stays a development convenience.
- Grades are advisory. The UI must not present them as authoritative.
- Hidden tests are reachable in memory by learner code, so checks must not rely on secrecy of
  expected values.
- The wall-clock kill runs in the worker. If the worker dies mid-run, the container ends only on its
  own limits. The worker reaps such orphans when it starts, and the VPS health check alerts on a
  stale worker heartbeat or an old queued attempt.

## Alternatives considered

- **Plain subprocess.** Rejected. It gives no network, filesystem or resource isolation.
- **A declarative assertion DSL.** Rejected. Behavioural checks need arbitrary Python.
- **Separate containers for harness and learner code now.** Deferred. It needs a secure result
  channel the stakes do not justify in Phase 1. It is the expected answer when the revisit condition
  is met.
- **Grading inside the API process.** Rejected. Untrusted code would share a process with
  authentication and the database pool.
