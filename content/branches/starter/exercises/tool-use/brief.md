# A tool-calling loop

A model on its own cannot check the weather, query a database or do reliable arithmetic. **Tool
use** (also called function calling) lets it ask your code to do those things. You describe the
tools you offer; instead of answering, the model may reply "please call `get_weather` with
`{"city": "Leeds"}`". Your code runs the function, sends the result back, and the model carries
on, possibly asking for more tools, until it finally answers in text.

That makes the **loop** the heart of every agent:

```text
user question ──► model ──► tool_use?  ── no ──► return the text
                    ▲           │ yes
                    │           ▼
                    └── run each call, send results as tool messages
```

Three details separate a toy from something you can run in production:

- The model's request is part of the conversation. Append it as an assistant message carrying its
  `tool_calls`, then answer **every** call with a `tool` message naming the call's `id`. Real
  APIs reject a conversation where a call is left unanswered.
- Tools fail, and the model can often recover if it is told what went wrong. Return the error as
  the result rather than crashing.
- A confused model can ask for tools forever. Cap the number of model calls.

```python
completion = client.complete(messages, tools=tools)
if completion.stop_reason == "tool_use":
    for call in completion.tool_calls:  # call.id, call.name, call.arguments
        ...
```

## Your task

Implement `run_with_tools(client, question, tools, registry, max_steps=5)` in `tool_loop.py`.
`tools` is the list of `Tool` definitions to offer; `registry` maps a tool name to the Python
function that implements it, called as `function(**call.arguments)`.

- Start with the user's `question`. Each step is one `client.complete(messages, tools=tools)`.
- If the reply is not a tool request, return its text.
- Otherwise append the assistant's request, run the calls in order, and append one `tool`
  message per call, with the result as a string.
- If a function raises (or the name is not in `registry`), the result is
  `error: <message>` and the loop carries on.
- Make at most `max_steps` model calls. If the model is still asking for tools after the last
  one, raise `RuntimeError` whose message mentions `max_steps`.
