# Evaluating and guarding a support bot

You have built every part: metrics, a swap judge, agreement, intervals, trajectory checks, input
and output guardrails, a shield and a red-team runner. Each works alone. A real release works
only if they work **together**, in one pipeline, and most failures live in the gaps between the
parts. The judge sees a customer's email address because only the bot's input was redacted. The
red-team runner attacks the bare model instead of the guarded bot, so it reports a pass rate for a
system nobody ships.

Your job is to build the pipeline that decides whether a new version of a support bot may ship:

```text
question ─► redact ─► shield ─► bot ⇄ tools (results redacted) ─► reply check ─► customer
                                                                       │
 eval cases ──► guarded_reply ──► swap judge ──► scores ─┐             │
 attacks ─────► guarded_reply ──► canary check ─────────┼──► release_decision ─► ship / hold
 trajectories ─► spec check ────────────────────────────┘
```

Three files hold the work. The starter gives you the constants and the redaction patterns.
Hidden tests run seeded fakes for the bot, the shield and the judge, so nothing here can be done by
reading the wording of a message.

## `guardrails.py`: `guarded_reply`

`guarded_reply(bot, shield, question, tools, registry, banned=(), max_attempts=2, max_steps=6)`
returns `{"status", "reason", "reply", "escalate", "calls"}`. Do these in order.

1. **Redact.** `redact(question)` applies `PATTERNS` in order. Everything below uses the redacted
   text, never the original.
2. **Shield.** `classify(shield, text)` makes one request whose only message is the text, and
   returns the first word of the reply, letters only and upper-cased, if it is `SAFE`, `JAILBREAK`
   or `INJECTION`; `UNKNOWN` for any other reply; `ERROR` if the shield raises a `ModelError`.
   Anything but `SAFE` returns `status` `"blocked"`, `reason` the label in lower case, `reply`
   `REFUSAL`, `escalate` `False` and `calls` `[]`, with no request to the bot.
3. **Tool loop.** Ask the bot (`system=SYSTEM_PROMPT`, `tools=tools`) with the redacted question as
   the only first message. When it asks for tools, add every requested call to `calls` as
   `{"tool": name, "arguments": dict(arguments)}` in order, run each, and answer each with a `tool`
   message in call order. A result is `str(registry[name](**arguments))`, `error: <message>` if the
   tool raises, or `error: unknown tool`. **Redact each result** (an error message can hold a
   customer's email too). Make at most `max_steps` bot requests in total; if they run out, return
   `status` `"refused"`, `reason` `"steps"`, `reply` `REFUSAL`, `escalate` `False` and the `calls`
   so far.
4. **Reply check.** A reply with no tool calls must be, after stripping whitespace, a JSON object
   with exactly the fields `answer` (a string) and `escalate` (a boolean), and `answer` must not
   contain any phrase of `banned`, compared case-insensitively. If it passes, return `status`
   `"ok"`, `reason` `None`, `reply` the answer, `escalate` its value and `calls`. If not, and this
   was the `max_attempts`th such reply, return `"refused"` with `reason` `"output"`, `reply`
   `REFUSAL`, `escalate` `False` and `calls`. Otherwise append the rejected reply as an `assistant`
   message and a `user` message naming every problem (each field name, and each banned phrase), and
   ask again.
5. **One conversation, one budget.** The tool loop and the reply check share a single
   conversation. A retry is sent with everything so far: the question, every tool call and result,
   the rejected reply and your feedback. After a retry the bot may ask for more tools; run them,
   record them in `calls` and carry on as in step 3. Every bot request, retries included, counts
   towards `max_steps`.

## `evaluation.py`

- `run_eval(bot, shield, judge, cases, tools, registry, rubric, banned=())`. Each case is
  `{"id", "question", "reference", "spec"}`. Run `guarded_reply` for each. A reply with status `ok`
  is judged with the **swap judge** (below): answer A is the shown reply, answer B the `reference`,
  and the question is the redacted one. The score is `1.0` for A, `0.5` for a tie and `0.0` for B.
  Any other status scores `0.0` and the judge is not asked. Check each case's recorded `calls`
  against its `spec` with the **trajectory rules** (below), whatever the status. Return
  `{"cases": [{"id", "status", "score", "violations"}, ...], "scores": [...], "mean": ...,
  "trajectory_pass_rate": ...}`, where the pass rate is the fraction of cases with no violations.
- `run_red_team(bot, shield, attacks, tools, registry, canary, banned=())`. Each attack is
  `{"id", "category", "prompt"}`; send its prompt through `guarded_reply`. It **leaked** if `canary`
  is a substring of the returned `reply` (exact, case-sensitive). Return `{"total", "passed",
  "pass_rate", "categories": {name: {"total", "passed", "pass_rate"}}, "failures": [leaked ids]}`;
  an empty suite has `pass_rate` `1.0`.
- `calibrate_judge(judge, items, rubric)`. Each item is `{"question", "a", "b", "human"}`, with
  `human` one of `"A"`, `"B"` or `"tie"`. Judge each item with the swap judge, showing it the
  **redacted** question (calibration items hold personal data too), and return Cohen's kappa
  between its verdicts and the human labels.

**The swap judge** is the one you built before. A pair takes two requests, each a fresh
conversation with one `user` message holding the rubric, the redacted question and both answers
labelled `Response 1` and `Response 2`, first with A then with B first. A reply is read by its
first word with any trailing `.`, `,`, `:`, `;` or `)` removed, which must be `1` or `2`
(otherwise `ValueError`). The verdict is `A` if A won both orderings, `B` if B won both, and
`tie` otherwise.

**Kappa** is `(p_o - p_e) / (1 - p_e)`, with `p_e` the sum over every label of the two raters'
shares of it, and `1.0` when `p_e` is exactly 1.

**Trajectory rules** return sorted unique codes for optional spec keys: `required` (a tool never
called: `missing:<tool>`), `forbidden` (`forbidden:<tool>`), `order` (pairs `[before, after]`; if
`after` is called, `before` must have a first call earlier than it, else `order:<before>><after>`),
`max_calls` (`budget` when exceeded), `max_identical` (`repeat:<tool>` for a call with equal
arguments made more often) and `args` (`{tool: {key: value}}`; every call to the tool must carry
those pairs, else `args:<tool>`).

## `release.py`: `release_decision`

`release_decision(baseline, candidate, red_team, kappa, max_drop=0.02, min_category_rate=0.9,
min_kappa=0.6)` takes two `run_eval` results, a `run_red_team` result and a kappa. Compute the
paired differences `candidate score - baseline score` per case, in case order, from the two runs'
`scores` (`ValueError` if the lists are empty or differ in length), and their **percentile
bootstrap** interval. Make a generator `random.Random(0)` and use nothing else; draw each of the
1000 resamples with one call, `rng.choices(diffs, k=len(diffs))`, and record its mean
`sum(resample) / len(diffs)`; sort the means and take the bounds at index `floor(0.025 * 1000)`
(25) and `ceil(0.975 * 1000) - 1` (974), with no interpolation. That fixes the interval exactly. Return
`{"ship": ..., "reasons": [...], "interval": (low, high)}`, where `reasons` is the sorted list of:

- `regression` if the top of the interval is below `-max_drop`;
- `trajectory` if the candidate's `trajectory_pass_rate` is below `1.0`;
- `red-team:<category>` for each category whose `pass_rate` is below `min_category_rate`;
- `judge-kappa` if `kappa` is below `min_kappa`.

`ship` is `True` only when there are no reasons.
