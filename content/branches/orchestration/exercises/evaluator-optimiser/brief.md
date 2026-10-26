# Evaluator–optimiser

A first draft is rarely the best one. People improve work by having it reviewed and trying
again, and you can build the same loop from two model calls: a **generator** that writes a
draft, and an **evaluator** that judges it against the brief and says what is wrong. The
generator's next attempt is given the feedback, and the loop stops when the evaluator is
satisfied.

```text
task ──► generator ──► draft ──► evaluator ──► "PASS"  ──► done
              ▲                        │
              └──── draft + feedback ◄─┘ "FAIL: too long, 9 words, limit 5"
```

Two things keep the loop honest. The generator can only improve if it sees what was wrong, so the
retry must carry the previous draft and the feedback. And a loop that waits for approval needs a
limit: an evaluator that is never satisfied would otherwise spend your budget forever.

## Your task

Implement `refine(client, task, max_rounds=3)` in `refine.py`. Each round:

1. **Generate.** One call to the generator, with its system prompt (which must not mention
   `PASS`). The first round's user message is the task. Later rounds send a single user message
   with the task, the previous draft and the evaluator's feedback.
2. **Evaluate.** One call to the evaluator. Its system prompt tells it to reply `PASS` if the
   draft meets the task, or `FAIL: <feedback>` otherwise. Its user message holds the task and
   the draft.

The two calls are told apart by their system prompts: only the evaluator's contains `PASS`.

A verdict passes when its trimmed text starts with `PASS`, in any case. Anything else is a
failure, including a reply that does not start with `FAIL` either, such as `Looks good`. Stop at
the first pass. After `max_rounds` drafts, stop anyway. Return `Refined(text, accepted, rounds,
history)`: the final draft, whether it passed, how many rounds ran, and a `Round(draft,
feedback)` for each. `feedback` is empty for a passing draft. For a failing one it is the text
after `FAIL:` (in any case), trimmed, which is also what the next generator call is shown; a
failing verdict that does not start with `FAIL` is its own feedback, trimmed.
