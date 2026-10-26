# Evaluate and gate a release

The copilot works. The question every team then faces is whether the *next* version works better,
and "it looked fine when I tried it" is not an answer. A change to the chunker, a smaller source
budget or a new shield prompt can make answers worse in ways nobody notices for weeks. This last
milestone builds the thing that decides: an eval suite that runs the whole copilot, a judge that
cannot be fooled by order, a red team that attacks the copilot as customers reach it, and a gate
that says ship or hold, with reasons.

**So far** the codebase has everything from **Index the help centre**, **Remember each customer**,
**Assemble each turn's context** and **Guard the copilot**: `chunking.py`, `kb.py`, `memory.py`,
`copilot.py` and `guardrails.py`. They are all still checked. This milestone adds `evaluation.py`
and `release.py`, drawing on **A judge that cannot be fooled by order**, **Checking an agent's
trajectory**, **Confidence intervals and a regression gate** and **A red-team suite with per-category
pass rates**. You built a pipeline like this in **Evaluating and guarding a support bot**, but
pasting it in will not pass: there the suite drove a bare bot through one function; here it must
drive the copilot you built, and the copilot's trajectories, citations and attacks are its own.

```text
eval cases ──► copilot.answer ──► shown reply ──► swap judge ──► scores ─┐
             (redact, recall, search, screen, ...)  calls, citations ─► spec ─┤
attacks ─────► copilot.answer ──► canary in the shown reply? ──────────────┼─► release_decision
                                                                           │     ship / hold
baseline run ──────────────────────────────────────────────────────────────┘
```

## Your task

### `evaluation.py`

- `judge_pair(judge, rubric, question, a, b)` makes two requests to `judge`, each a fresh
  conversation whose only message is `JUDGE_TEMPLATE` (in the starter) filled in with
  `str.format`: first with `a` as `first` and `b` as `second`, then the other way round. A reply is
  read by its first word with any trailing `.`, `,`, `:`, `;` or `)` removed, which must be `1` or
  `2` (otherwise raise `ValueError`). Return `"A"` if A won both orderings, `"B"` if B won both,
  and `"tie"` otherwise.
- `run_eval(copilot, judge, cases, rubric, *, now)`. Each case is
  `{"id", "user", "question", "reference", "spec"}`. Answer it with
  `copilot.answer(case["user"], case["question"], now=now)`. A reply with status `"ok"` is judged
  with `judge_pair`: A is the reply's `text` (what the customer saw), B the case's `reference`, and
  the question is the **redacted** question. The score is `1.0` for `"A"`, `0.5` for `"tie"` and
  `0.0` for `"B"`. A refused reply scores `0.0` and the judge is not asked. Check every case's
  trajectory (below), whatever its status. Return
  `{"cases": [{"id", "status", "score", "violations"}, ...], "scores": [...], "mean": ...,
  "trajectory_pass_rate": ...}`: one result per case in case order, the scores in the same order,
  their mean, and the fraction of cases with no violations. An empty list of cases has `mean`
  `0.0` and `trajectory_pass_rate` `1.0`.
- **Trajectory rules.** A case's `spec` may have any of these keys. The opened articles are the
  `article_id` arguments of the reply's `open_article` calls; the cited articles are the
  citations' chunk ids up to the `#`. Return the sorted, unique codes:
  - `must_open`: a list of article ids; `missing:<id>` for each one never opened;
  - `must_not_open`: `forbidden:<id>` for each one that was opened;
  - `cites`: `uncited:<id>` for each one that no citation comes from;
  - `max_calls`: `budget` if the reply made more calls than that;
  - `max_identical`: `repeat:<tool>` if any call (the same tool with equal arguments) was made more
    often than that.
- `run_red_team(copilot, attacks, canary, *, now)`. Each attack is
  `{"id", "category", "user", "question"}`; answer it with `copilot.answer`. It **leaked** if
  `canary` is a substring of the reply's `text` (exact, case-sensitive). Return `{"total",
  "passed", "pass_rate", "categories": {name: {"total", "passed", "pass_rate"}}, "failures":
  [leaked ids, in attack order]}`. An empty suite has `pass_rate` `1.0`.

### `release.py`: `release_decision`

`release_decision(baseline, candidate, red_team, *, max_drop=0.02, min_category_rate=0.9,
resamples=1000, seed=0)` takes two `run_eval` results and a `run_red_team` report.

1. **Pair by id.** The candidate may list its cases in another order. Raise `ValueError` if the
   two runs do not hold the same case ids, or hold none. The paired differences are
   `candidate score - baseline score`, one per case, in the **candidate's** case order.
2. **Bootstrap.** Make one generator, `random.Random(seed)`, and use nothing else. For each of
   `resamples` resamples, draw `rng.choices(diffs, k=len(diffs))` with one call and record its mean.
   Sort the means; the interval is `[means[floor(0.025 * resamples)],
   means[ceil(0.975 * resamples) - 1]]`, with no interpolation.
3. **Reasons**, sorted:
   - `regression` if the top of the interval is below `-max_drop`;
   - `trajectory` if the candidate's `trajectory_pass_rate` is below `1.0`;
   - `red-team:<category>` for each category whose `pass_rate` is below `min_category_rate`.

Return `{"ship": ..., "reasons": [...], "interval": [low, high]}`, with `ship` true only when there
are no reasons.

## Run it against a real model

Everything here runs against seeded fakes so that it can be graded. The same code runs against a
live provider: once live mode is enabled (Phase 4), build the copilot, shield and judge with
`forgeway_kit.default_client()` instead of fakes and nothing else changes. Watch for these when you
do:

- **Cost.** One eval case is a turn of the copilot (several model calls, plus a shield call per
  retrieved chunk) and two judge calls. Multiply by the suite before you run it, and keep a small
  smoke suite for quick checks.
- **Latency.** Shield calls run once per source; screen in parallel, or batch, if turns feel slow.
- **Non-determinism.** Real replies vary between runs even at temperature 0, so one run is a sample.
  That is what the bootstrap interval is for: gate on the interval, never on a single mean, and
  expect a re-run to move it a little.
- **Rate limits.** A full suite can hit them. Back off and retry as in **Retries and exponential backoff**, and
  do not count a rate-limited case as a failure.
- **The gate is the release process.** Re-run the eval suite and the red team for every change to
  any file, prompt or model version, and ship only when `release_decision` says so.
