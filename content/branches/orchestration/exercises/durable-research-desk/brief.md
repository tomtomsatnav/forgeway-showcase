# The durable research desk

Every exercise in this branch built one part of a system that does real work. Here you build the
system. A request arrives at a **research desk**. A router sends it to the right desk. That desk's
orchestrator plans subtasks and fans workers out to do them at the same time, then drafts a
report. The draft is handed to a specialist who checks facts with tools and publishes the report,
but only once a person has said yes. The whole thing has to survive a crash at any moment, cost no
more than its budget, and never send an email twice.

```text
request ─► router ─► orchestrator ─► workers (parallel) ─► draft
                                                            │ handoff: request + briefing
                                                            ▼
              budgets ◄─ specialist ─► lookup, lookup, ... ─► publish ─► person says yes
              (whole run)    │                                 (needs approval)
                             └─ compacts its context when it grows
         every model reply and tool result is saved the moment you have it
```

Each stage is something you have already built, and each earlier solution works on its own. What
the stages have never had to do is share things. The budgets belong to the run, not to a stage.
The record that lets a new process carry on has to cover every stage, the pause for approval
included. A briefing, a compaction or a decision that is right in isolation can still be wrong
here. Pasting the earlier solutions together will not pass.

## The files

All five are yours to edit. `workflow.py` is the only one the tests call; the others are a
suggested split of the work, so give each a clear job.

- `contracts.py`: the shared shapes (`Desk`, `Limits`, `Outcome`, `PlanError`) and
  `conversation_tokens`. Leave it as it is.
- `journal.py`: the record of a run, which is also where the run's steps and tokens are counted.
- `planning.py`: the router, the planner, the workers and the drafting call.
- `specialist.py`: the briefing, the specialist's tool loop, compaction and approval.
- `workflow.py`: `run_workflow`, which runs the stages in order and handles resuming.

## Your task

Implement `run_workflow(client, run_id, request, *, desks, default, registry, store,
limits=None, decisions=None)` and return an `Outcome`. `desks` maps a name to a `Desk`;
`registry` maps a tool name to a function called as `function(**arguments)`; `store` is a dict of
strings; `limits` is a `Limits`, or `Limits()` when it is `None`.

**1. Route.** One call. The system prompt lists every desk as `name: description` on its own line
and asks for the desk name only; the user message is `request`. Use `max_tokens` of at most 32 and
`temperature` 0, and offer no tools. Take the first desk name in the reply, matched as a whole
word and ignoring case. A name is a whole word when no letter, digit, underscore or hyphen touches
either end of it, so `orchard` is not in `re-orchard` or `orchard_2`. If no desk is named, use
`default`.

**2. Plan.** One call. The system prompt starts with the desk's `system` text; the user message
is `request`. Remove a surrounding ```` ``` ```` or ```` ```json ```` fence, parse the JSON and
raise `PlanError` unless it is a non-empty list of non-empty strings (a string of whitespace is
empty). Trim each subtask, drop duplicates (keeping the first) and keep at most
`limits.max_subtasks`. A bad plan is refused before any worker runs.

**3. Work.** One call per subtask, run at the same time with at most `limits.max_workers` in
flight. The system prompt starts with the desk's `system` text, and the one user message is
`Goal: <request>` and `Subtask: <subtask>` on two lines, so a worker never sees what the others
found. A `ModelError` from a worker makes that subtask fail: put the subtask and the error message
in `Outcome.failed` and carry on with the others. Any other exception is a bug and propagates.
Once the fan-out has finished, who failed is part of the run and is not decided again. If every
worker failed, return status `failed` and make no further call.

**4. Draft.** One call. The system prompt starts with the desk's `system` text. The one user
message is `Goal: <request>`, then, for each subtask that succeeded, a blank line and
`Subtask: <subtask>` and `Result: <result>` on two lines. The blocks follow the plan's order, not
the order in which the workers finished.

**5. Hand over.** The specialist starts a new conversation. Its system prompt is the desk's
`specialist` text exactly, and it is offered the desk's `tools`, in the desk's order and nothing
else. The conversation holds two user messages: `request`, unchanged, then a briefing of these
lines:

```text
Handed over from orchestrator.
Answered: <k> of <n> subtasks
Unanswered: <the subtasks that failed, in plan order, joined with "; ">     (only if some failed)
Draft: <the drafting reply>
```

The workers' own replies do not travel with it. The specialist gets the draft, not what each
worker said, and a worker's notes are not for the specialist.

**6. Specialist loop.** A tool-calling loop: one `client.complete(messages, system=..., tools=...)`
per step, and each result sent back as a `tool` message, in the order of the calls. A tool that
raises, or one that is not in the registry, gives the result `error: <message>`. A reply with no
tool request is the answer: return `Outcome("done", text)`.

**7. Compact.** Before each specialist call, if `conversation_tokens(messages)` is more than
`limits.compact_at`, compact. Keep the first two messages (the request and the briefing) and the
last `limits.keep_recent` messages, moving the start of that recent part back if it would begin
with a `tool` message. Summarise everything between them with one call that offers no tools and
has one user message: those older messages written out as text. Its system prompt is yours to
choose, and the specialist's own text is fine. Replace them with one user message:
`Summary of earlier work:`, a newline, then the summary. If nothing lies between, do not compact.

**8. Approve.** When a specialist reply asks for any tool in `desk.needs_approval`, run nothing
from that request, not even its harmless calls, and return `Outcome("waiting", pending=...)` with
the calls that need a decision, in the model's order. The person answers by calling
`run_workflow` again with the same `run_id` and `decisions`, which maps each pending call id to
`True` (approve), `False` (reject) or a string (reject, with a reason). The request then runs in
the model's order: approved calls and calls that needed no approval run; a rejected call's result
is `rejected by user`, or `rejected by user: <reason>`. Then the loop carries on, and may pause
again. Calling again with `decisions=None` on a waiting run returns the same waiting outcome and
makes no call at all. `decisions` for a run that does not exist or is not waiting raises
`RuntimeError`; a missing decision or a decision for a call that is not pending raises
`ValueError`, naming the call. A refused call changes nothing.

**9. Budgets.** The limits belong to the whole run. `steps` is the number of model replies the run
has received, workers and summaries included, and `tokens_used` is the input plus output tokens of
those replies. Never make call number `max_steps + 1`, and never make another call once
`tokens_used` is more than `token_budget`. Check before the router, before the planner, before
the fan-out (if its calls would not all fit within `max_steps`, run none of them), before drafting,
and before each specialist call and each summary call: token budget first, then steps. When a
specialist reply asks for tools, decide before anything runs, in this order: tokens used more than
`token_budget` gives `token_budget`; a call already made `limits.max_repeats` times (same tool,
same arguments in any key order, counting calls earlier in the same request and calls made by
earlier processes) gives `loop_detected`; `steps` equal to `max_steps` gives `max_steps`. Only then ask for approval. A
call counts as made once its request has passed these checks. A stopped run returns that status
with an empty `text` and none of the refused request's tools run. A reply with no tool request is
the answer even if it took the run over budget.

**10. Survive.** Keep the whole record of the run in `store[run_id]` as JSON text, and keep it
up to date: after the request is recorded, after each model reply and after each tool result,
including the pause and the decisions. If `store` holds `run_id`, resume: the saved request wins
over the one passed in, nothing already recorded is done again (no model call, no tool call, no
worker), and a finished run returns its result without a call. Your tests restart the process
between steps: each step runs in a new Python interpreter, handed a copy of the store that has
been through JSON, so nothing kept in memory, in `os.environ` or on a module survives. They also
check that the record in the store holds every model reply and tool result. A `ModelError` from the router, planner, drafter or specialist
propagates, and so does anything that kills the process (a `BaseException`), with the record
written so far still valid. Different run ids share a store without sharing anything else.

`Outcome(status, text, pending, desk, plan, failed, steps, tokens_used)` reports the desk the
router chose, the tidied plan and the failed subtasks. Its `steps` and `tokens_used` are the
run's totals so far, including work done by earlier processes. `status` is `done`, `waiting`,
`failed`, `token_budget`, `max_steps` or `loop_detected`.
