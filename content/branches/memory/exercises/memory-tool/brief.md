# Memory as a tool

There are two ways to give an agent memory. In the **pipeline** style your code decides: it
saves things after each turn and pastes relevant memories into the prompt before the model sees
the question. In the **tool** style the model decides: it is given a `remember` tool and a `recall`
tool, and chooses when to use them, much like a person reaching for a notebook. Production agents
increasingly work in the tool style: Claude's memory tool, for example, gives the model a directory
of memory files that it views, creates and edits through tool calls. This exercise uses a simpler
pair of tools with the same idea. The style is flexible, it keeps the prompt small, and it makes
memory visible: every read and write is a tool call you can log and audit.

It also moves the risks. The model can forget to save, save the wrong thing or look the wrong key
up, and your code must not quietly paper over that. If your code pre-loads every note into the
prompt, you have built the pipeline style with extra steps. If it saves the user's message
whether or not the model asked, the model's choice means nothing. So this exercise grades two
things: **what the agent chose to store**, and **what reached later prompts** (only what a
`recall` call returned).

```text
session 1   user: "...my sister's name is Ada..."
            model -> remember(key="sister", value="Ada")      memory: {"sister": "Ada"}
session 2   (new process, memory reloaded from JSON)
            user: "What's my sister called?"
            model -> recall(query="sister")  ->  "sister: Ada"
            model: "Ada."
```

## Your task

Implement `run_with_memory(client, memory, user_message, max_steps=6)` in `agent.py`. `memory` is a
dict of text to text (the notebook of one user, persisted by the caller as JSON).

- Offer two `Tool`s on every request: `remember` with required string properties `key` and
  `value`, and `recall` with a required string property `query`. Give them clear descriptions and
  use a system prompt of your own. The only message of the first request is the user's message.
- `remember(key, value)` stores `memory[key.strip().lower()] = value.strip()` and returns `saved`.
  Both arguments must be strings that are not empty after `strip()`.
- `recall(query)` returns, for every key that contains `query.strip().lower()`, one line
  `key: value`, in sorted key order, joined with newlines. Only keys are searched, never values. An
  empty query matches every key. With no match the result is `no memories found`. `query` must be
  a string.
- A call with missing or wrongly typed arguments returns a result starting with `error:`. A call to
  any other tool returns exactly `error: unknown tool`. Neither raises, and the other calls in the
  same reply still run.
- This is the usual tool loop: answer each call with a `tool` message, in call order, and ask
  again; return the first reply that asks for no tools. Make at most `max_steps` model calls, then
  raise `RuntimeError` mentioning `max_steps`.
- On every request, not just the first, keep memory contents out of the system prompt, the
  messages and the tool definitions except as a `recall` result, and never write to `memory`
  except for a `remember` call. The tests run a later session in a new process, handed only the
  notebook as JSON, so `memory` must be the only place the notes live.
