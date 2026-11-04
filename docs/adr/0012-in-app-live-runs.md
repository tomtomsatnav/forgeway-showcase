# ADR 0012: In-app live runs on the platform's key

Status: Accepted (built; not yet run under gVisor on the VPS, see Consequences)
Date: 2026-11-03

## Context

Local live mode (docs/live-mode.md) lets a learner run their code against a real model on
their own machine with their own key. The owner wants a second way in: a "Try it live" button
that runs the learner's current code against a real model from the workspace, paid for with the
platform's key, Claude Haiku 5.5 (`claude-haiku-5-5`, $0.10 / $0.50 per million input / output
tokens up to 100K-token prompts; docs/plans/ai-tutor.md). Each learner's monthly spend may reach
half of what their plan earns. Grades always still come from the fakes.

Learner code is hostile (ADR 0003, ADR 0009). It runs in an ephemeral sandbox with
`--network none`, under gVisor (`runsc`) in production, started through a socket-proxy that
refuses any container that is not a no-network, read-only sandbox (ADR 0010). Whatever the
sandbox can see, learner code can read and try to send out. So:

1. The platform key must never enter the sandbox: not in its environment, files, arguments or
   mounts. The sandbox keeps no network.
2. Learner code may reach the model only through a narrow channel to a proxy outside the
   sandbox that adds the key, forces the model, clamps `max_tokens`, caps calls and tokens per
   run, enforces the learner's spending caps and refuses everything else.

## Decision

### The channel: framed JSON over the container's own stdio

The worker already talks to the sandbox over its attached stdin and stdout (`docker run -i`):
the nonce and a tar archive go in, the report line comes out. A live run keeps that pipe open
and uses it in both directions, one JSON object per line:

```
worker → container   <nonce> live <bytes>\n  <tar: manifest.json, submission/…, no tests>
container → worker   LATTICE-LIVE <nonce> {"type": "call", "id": 1, "request": {…}}
worker → container   {"id": 1, "completion": {…}}     or  {"id": 1, "error": {"kind", "message"}}
container → worker   LATTICE-LIVE <nonce> {"type": "done", "exit_status", "stdout", "stderr", …}
```

Why stdio, not a Unix socket mounted into the container or a network to an egress proxy:

- **It works with `--network none` and under gVisor unchanged.** gVisor reaches host Unix
  sockets only with extra runtime flags (`--host-uds`), which would have to be enabled for every
  sandbox on the host; stdio is the attach stream gVisor already serves for grading. A network,
  even a private one to an egress proxy, gives learner code a network stack to probe.
- **No new host surface.** No mount (the socket-proxy refuses every bind and volume anyway),
  no new container flag, no new image, no change to the socket-proxy allow-list: a live run's
  `docker run` command is byte for byte the grading one. The unit test asserts this on the
  command the runner builds, and that no argument and no environment variable holds the key.
- **One reader, one rule set.** Every byte from the container arrives at one place in the
  worker, which already treats it as untrusted.

### Inside the container

The harness (UID 10001) reads the header, extracts the archive (the learner's files laid over
the starter, plus the exercise's `live.py`, no tests), and starts the learner's program in a
child interpreter, as UID 10002 through the launcher (ADR 0009), on a pair of pipes. The child
runs `lattice_grader/live/child.py` from source (`-s -P -c`), so it never imports
`lattice_grader`. It moves the pipes to private descriptors, points stdout and stderr at two
output files, and runs `live.py` with `ProxyClient` made the default by `use_client()`, which
always wins over the environment fallback. `FORGEWAY_GRADING=1` stays set, so `forgeway_kit`'s
live clients still refuse to be built, and `ProxyClient` sends no key, holds none and names no
provider. `stream()` is the completed reply played back as events: the proxy does not stream.

The harness relays: each child line must be at most 512 KB, an object with exactly `id`
(counting up from 1) and `request` (an object); anything else stops the run (`bad-message`). It
forwards valid calls to the worker and the worker's reply back. The learner's user cannot read
or write the container's stdio, the harness's `/proc` entries or the output files' directory
(ADR 0009), so the only thing learner code can put on the channel is a call the harness
accepts and the worker checks again.

### The proxy, in the worker

`DockerSandboxRunner.run_live` reads the container's lines (each at most 640 KB, at most 500
frames, prefixed with the run's nonce, ids in order, only `call` and `done`); anything else ends
the run (`protocol`). Each call goes to `LiveProxy` (`application/live_runs.py`), which:

1. refuses a request over 400 KB of JSON (about 100K tokens, past which Haiku costs five times
   as much);
2. validates it against `LiveCall` (`domain/live.py`): the toolkit's arguments, strict types,
   `extra="forbid"` at every level, bounded lengths. Only fields named there can reach the
   provider; `temperature` is accepted and never sent;
3. refuses once the run has made `LATTICE_LIVE_MAX_CALLS_PER_RUN` calls or used
   `LATTICE_LIVE_MAX_TOKENS_PER_RUN` tokens;
4. refuses at the learner's monthly cap or daily burst limit, with the reset time;
5. builds the Messages API body itself (`infrastructure/live_anthropic.py`), forcing
   `LATTICE_LIVE_MODEL` and clamping `max_tokens` to the smallest of the request, the per-call
   limit and what is left of the run's token budget, adds the key, and POSTs with the standard
   library;
6. records the call (`live_calls`: user, run, exercise, model, input, output, cache read and
   write tokens, cost in USD, latency, outcome, time) in its own transaction before replying.

Refusals come back to learner code as `forgeway_kit` errors: `InvalidRequestError` for limits
and invalid requests (retrying will not help), `RateLimitError` and `ServerError` for the
provider's own. The worker's docker CLI is started with an allow-listed environment (`PATH`,
`HOME`, `DOCKER_*` and proxy settings), so no key is even in the process that starts a
sandbox. In production the key is in `.env.live`, which only the worker reads; the API
gets `LATTICE_LIVE_RUNS_ENABLED=true` instead.

### Metering and caps

Cost is priced from the rate card (`LATTICE_LIVE_RATE_CARD`, USD per million tokens, with a
long-context price past 100K input tokens). A subscriber's monthly cap is what they pay
(`LATTICE_BILLING_MONTHLY_PRICE_MINOR`, or a twelfth of `LATTICE_BILLING_ANNUAL_PRICE_MINOR`, in
pence) × `LATTICE_GBP_TO_USD` (1.27) × `LATTICE_LIVE_SPEND_CAP_FRACTION` (0.5): about $12.07 on
£19 a month and $10.05 on £190 a year. A paid plan with no billing price behind it (billing off,
or granted by hand) has `LATTICE_LIVE_PRO_MONTHLY_CAP_USD` ($10). A subscription in `trialing` has
`LATTICE_LIVE_TRIAL_USD` ($1) for the whole trial, counted from its start, in place of the monthly
cap. The free plan's is `LATTICE_LIVE_FREE_MONTHLY_USD`, none by default. No more than `LATTICE_LIVE_DAILY_CAP_FRACTION` (0.1) of it in one day. Months and days
are UTC calendar periods; the caps are summed from `live_calls`. A cap is checked before each
call, so one call can overshoot it by at most its own cost (about $0.0005 at the defaults).

Money is not the only thing a run spends: it holds the worker. `LATTICE_LIVE_SECONDS_PER_DAY`
(600) limits the time an account's runs may hold it in any 24 hours, from claim to finish, checked
before queueing (429 `live-cap`, scope `time`). It is a budget of its own rather than a share of
`LATTICE_GRADING_SECONDS_PER_DAY`, so live experiments can never use up a learner's checks. Each
provider call's timeout is what is left of the run (at least a second).

### The run as a job

`live_runs` is a second job table on the Postgres queue (ADR 0002): the row is the job, the
same worker claims it with `SKIP LOCKED`, taking the oldest queued job of either kind. A run still
queued after 10 minutes is `errored`, so the learner is not locked out. One live run in flight per
learner (a partial unique index, 409 `live-run-in-flight`), an hourly cap per account
(`LATTICE_LIVE_RUNS_PER_HOUR`), and `LATTICE_MAX_QUEUE_DEPTH` queued runs. A live run is never
retried: it spends money, so one a dead worker held is `errored` by the sweep, not re-queued,
with the calls it recorded and their total cost in its result.
Starting one needs a verified email, the entitlement the exercise view judges, the exercise
open to the learner (a guided-project milestone's starter is a reference solution a live
program could print), a `live.py`, an allowance with something left, and the data notice
acknowledged.

### Data protection (UK GDPR)

- **Processor.** Anthropic, PBC runs the model as Forgeway's processor under its commercial
  terms and Data Processing Addendum. Under those terms it does not train on API inputs and
  outputs, and deletes them within 30 days (up to 2 years only when its safety systems flag
  them).
- **Transfer.** Anthropic processes in the United States. The restricted transfer relies on the
  UK International Data Transfer Addendum incorporated in Anthropic's DPA. The owner must accept
  the DPA before the key is configured (docs/legal/compliance-review-2026-11.md, M4).
- **Transparency.** Before a learner's first live run they acknowledge a notice saying what is
  sent, to whom and where, what Anthropic keeps, what Forgeway keeps and that nothing is used
  for grading (`LIVE_NOTICE`, versioned by `LIVE_NOTICE_VERSION`; a new wording asks again). The
  acknowledgement is recorded (`live_notice_acknowledgements`: user, wording version, time).
- **Retention.** A run's files and output (`live_runs`) are deleted after 30 days; usage and
  cost records (`live_calls`) after 13 months, for cap enforcement and accounts. Both run in the
  daily `forgeway accounts purge-unverified` (forgeway-purge.timer).
- **Access and erasure.** The account export includes live runs, usage records and
  acknowledgements. Deleting the account deletes all three (`ON DELETE CASCADE`); usage records
  are not kept past erasure, as they are platform costs, not a learner's billing record.

## Consequences

- No container, image, socket-proxy or runtime change; the live path is the grading path with
  stdin kept open. The docker-marked end-to-end test runs a real sandbox against a stub provider
  on the host and checks the program cannot see the key in any process's environment or command
  line, has no network, and reaches the model only through the proxy.
- Streaming is buffered: `stream()` yields the finished reply's events.
- Not yet verified under gVisor. stdio attach is what grading already uses there, but run
  `tests/integration/test_live_runs_docker.py` against the VPS's runtime before turning the key
  on in production.
- While a live run holds the single worker, attempts wait (up to `LATTICE_LIVE_RUN_TIMEOUT_S`,
  60 s, scaled by the sandbox timeout factor). Attempts are claimed first.

## Alternatives considered

- **An egress proxy on a private network** (the old ARCHITECTURE.md sketch). Gives learner code
  a network stack and needs the socket-proxy to allow a network; rejected.
- **A host Unix socket mounted into the container.** Needs a bind mount (refused by the
  socket-proxy) and gVisor's `--host-uds`; rejected.
- **The key in the container behind a guard.** Learner code reads anything the container holds;
  rejected outright.
- **Reusing `forgeway_kit.live.AnthropicClient` in the worker.** It reads the key only from
  `ANTHROPIC_API_KEY` and refuses to construct where `lattice_grader` is imported (the test
  suite); and the proxy should name every forwarded field itself. A small explicit body builder
  instead.
