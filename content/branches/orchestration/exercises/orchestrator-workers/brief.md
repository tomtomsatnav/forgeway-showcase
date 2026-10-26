# Orchestrator–workers

With a fan-out you know the pieces in advance: one request per document. Often you do not.
"Compare these three cities for a weekend trip" needs three research jobs, but "plan a product
launch" needs whatever jobs the launch turns out to require. In an **orchestrator–workers**
design, one model call (the orchestrator, or planner) decides the subtasks at run time, a worker
handles each, and a final call synthesises the results into one answer.

```text
goal ──► planner ──► ["Research Leeds", "Research York", "Research Hull"]
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
          worker (goal +   worker (goal +    worker (goal +
          subtask 1)       subtask 2)        subtask 3)
              └─────────────────┼─────────────────┘
                                ▼
                    synthesiser ──► answer
```

The planner is a model, so its plan is untrusted input. It may wrap its JSON in a code fence,
repeat itself, return forty subtasks or return something that is not a plan at all. Your code
must tidy what it can and refuse the rest *before* spending a call on a worker. Workers should
be kept apart too: each sees the overall goal and its own subtask, not what the others found.

## Your task

Implement `orchestrate(client, goal, max_subtasks=5)` in `orchestrate.py`.

1. **Plan.** One call whose only user message is `goal`; the system prompt asks for a JSON
   list of subtask strings. Remove a surrounding ```` ``` ```` or ```` ```json ```` fence, parse the JSON, and
   raise `PlanError` if it is not a list of non-empty strings, or is empty. A string that is
   empty or only whitespace is not a non-empty string, so one of those makes the whole plan
   invalid. Trim each subtask,
   drop duplicates (keep the first) and keep at most `max_subtasks`.
2. **Work.** For each subtask in order, one call with a worker system prompt and the single
   user message `Goal: <goal>` and `Subtask: <subtask>` on two lines.
3. **Synthesise.** One call whose single user message is `Goal: <goal>`, then for each subtask
   a blank line and `Subtask: <subtask>` and `Result: <result>` on two lines.

Return `Orchestrated(plan, results, answer)`: the tidied plan, a dict of subtask to worker
reply, and the synthesis reply.
