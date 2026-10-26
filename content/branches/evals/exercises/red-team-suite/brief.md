# A red-team suite with per-category pass rates

Guardrails you have never attacked are guardrails you hope work. **Red-teaming** means trying to
break your own system on purpose, and doing it as a repeatable suite, not a one-off: a list of
attacks, each tagged with a category (prompt injection, jailbreak, data exfiltration, encoding
tricks), run against the system on every change.

To score an attack without reading transcripts, plant a **canary**: a unique secret string in the
system prompt that the bot must never reveal. An attack succeeded if the canary appears in the
reply. The headline number is the **pass rate** (the share of attacks defended), and the useful
one is the pass rate **per category**. An overall 95% can hide a category that is 40%, and that
category is where an attacker will go.

```text
attacks ──► bot (system prompt holds the canary) ──► canary in reply? ──► per-category pass rates
```

## Your task

Implement `run_suite` and `failing_categories` in `redteam.py`.

`run_suite(client, system, attacks, canary)` takes `attacks`, a list of
`{"id": ..., "category": ..., "prompt": ...}`. For each attack, in order, make one `client.complete`
call in a fresh conversation: a single `user` message holding the prompt, with `system` passed on
every call. The attack **leaked** if `canary` appears anywhere in the reply text, as an exact,
case-sensitive substring; a lower-cased canary, or a canary missing its last character, is not a
leak. Otherwise the attack was **defended**.

If the client raises a `ModelError`, the attack counts as defended, its id is recorded as an error,
and the suite carries on with the next attack.

Return:

```python
{
    "total": 12, "passed": 9, "pass_rate": 0.75,     # passed = defended attacks
    "categories": {"jailbreak": {"total": 5, "passed": 3, "pass_rate": 0.6}, ...},
    "failures": ["a3", "a7", "a9"],                  # ids of leaked attacks, in suite order
    "errors": ["a5"],                                # ids that raised ModelError, in suite order
}
```

`pass_rate` is `passed / total`, or `1.0` when there are no attacks (and then no requests are made).

`failing_categories(report, minimum)` returns the sorted names of the categories whose `pass_rate`
is strictly below `minimum`. A CI job can fail the build if the list is not empty.
