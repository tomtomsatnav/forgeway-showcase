# Handoffs that carry the right context

A support desk is not one person who knows everything. A triage agent greets the customer,
looks up their account and passes them to billing; billing may pass them on to refunds. Each
agent has its own instructions and its own tools, so each one stays small and focused. The
moment of **handoff** is where these designs go wrong, because the next agent starts with
whatever you give it, and that has to be the right amount.

Too little and the customer must repeat themselves: the new agent has no idea what was asked.
Too much and you leak. The previous agent's system prompt, tool results and internal notes
(an account's risk flag, say) were never meant for the next agent, or for the customer, who may
see its replies.

```text
customer: "I'm customer 4417 and was charged £82 twice"
  triage:   lookup_customer(4417) → "... INTERNAL-RISK-FLAG ..."      (private to triage)
            handoff(to="billing", reason="charge dispute", summary="Customer 4417, £82 twice")
  billing receives:  the customer's original message
                     "Handed over from triage. Reason: ... Summary: ..."
```

A handoff in this design is just a tool, named `handoff`. The model chooses when to call it, but
your code decides what travels with it.

## Your task

Implement `run_with_handoffs(client, agents, start, message, max_handoffs=3)` in `handoff.py`.
`agents` maps a name to an `Agent(system, tools, registry)`.

- The conversation starts with `message` as the user message, handled by `agents[start]`. Every
  model call uses the current agent's `system` and offers its own `tools` plus a tool called
  `handoff` with required string arguments `to` (an enum of the *other* agents' names), `reason`
  and `summary`.
- Other tool calls run in the current agent's `registry` as in any loop (errors become
  `error: <message>` results). A reply with no tool request ends the run.
- A `handoff` to a valid, different agent starts a new conversation for it with two user
  messages: the original `message`, then `Handed over from <agent>.`, `Reason: <reason>` and
  `Summary: <summary>` on three lines. The old conversation is dropped.
- A `handoff` to an unknown agent, to the current one, or with no `to` at all, gets the tool
  result `error: ...` and the current agent carries on. Only successful handoffs count towards
  `max_handoffs`.
- If a single reply mixes other tool calls with a successful `handoff`, run the calls listed
  before the handoff, then hand over; calls listed after it are dropped along with the old
  conversation.
- If the model makes more than `max_handoffs` successful handoffs, raise `RuntimeError`
  mentioning `max_handoffs`.

Return `HandoffResult(text, agent, trail)`: the final text, the name of the agent that produced
it, and the names of every agent that held the conversation, starting with `start`.
