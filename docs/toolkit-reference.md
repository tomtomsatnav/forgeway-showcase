# Toolkit reference

Everything your code can import from `forgeway_kit`. It is the same toolkit in the workspace, in the
grader and on your own machine. Briefs use these names without explaining them, so keep this page
open beside the editor.

```python
from forgeway_kit import FakeModel, Message, default_client, use_client
```

## Calling a model

A client has one method you always use, `complete`. The messages are positional and everything else
is a keyword.

```python
client = FakeModel(responder=lambda request: "Paris.")
reply = client.complete(
    [Message(role="user", content="Capital of France?")],
    system="Answer in one word.",
    max_tokens=50,
)
reply.text  # "Paris."
reply.stop_reason  # "end_turn"
reply.usage.input_tokens
```

- `messages` (required): A sequence of `Message`. The last one comes from the user or is a tool result.
- `system` (default `None`): The system prompt. It is not a message.
- `max_tokens` (default `512`): The most tokens the reply may have. A longer reply is cut off.
- `temperature` (default `0.0`): Sampling temperature.
- `tools` (default `()`): A sequence of `Tool` to offer. Leave it out for no tools: `None` is not accepted.
- `model` (default `None`): The name of the model to use.
- `response_format` (default `None`): A JSON Schema the reply should follow.
- `tool_choice` (default `"auto"`): `"auto"`, `"any"` (some tool), `"none"`, or `{"name": <tool>}` for that tool.
- `effort` (default `None`): `"low"`, `"medium"` or `"high"`: how much the model reasons before it answers.

`ModelClient` is the protocol for the first five arguments. `StreamingModelClient` adds `model`,
`response_format`, `tool_choice`, `effort` and `stream`. `FakeModel` and the live clients are both.

Requests travel as JSON, so anything you send must be made of `str`, `int`, `float`, `bool`, `None`,
`list` and `dict`. Anything else raises `TypeError` before the request is sent.

`default_client()` returns the client configured for this run. `use_client(client)` is a context
manager that makes `client` the default inside its block. With none configured, `default_client()`
raises `RuntimeError`, unless `FORGEWAY_LIVE` selects a live one on your own machine.

```python
with use_client(client):
    default_client().complete([Message(role="user", content="Hello")])
```

## Messages and replies

**`Message(role, content="", tool_calls=(), tool_call_id=None)`**: one turn. `role` is `"user"`,
`"assistant"` or `"tool"`. Only an assistant message can carry `tool_calls`, and a tool message, and
only a tool message, needs a `tool_call_id`.

**`Completion`**: what `complete` returns.

- `text` (`str`): The reply text; `""` when the model asks for tools.
- `stop_reason` (`str`): `"end_turn"`, `"max_tokens"`, `"tool_use"` or `"refusal"`.
- `usage` (`Usage`): The tokens used.
- `tool_calls` (`tuple[ToolCall, ...]`): The calls the model asks for; `()` if none.
- `model` (`str`): The model that answered.
- `latency_ms` (`float`): How long the call took.

**`Usage(input_tokens, output_tokens, cache_read_input_tokens=0, reasoning_tokens=0)`**:
`input_tokens` counts the whole prompt, and `cache_read_input_tokens` is the part of it read from the
prompt cache. `output_tokens` includes `reasoning_tokens`, which are billed as output.

## Tools

**`Tool(name, description, input_schema)`**: a function you offer. `input_schema` is a JSON Schema
object. MCP calls the same thing `inputSchema` on the wire; here the field is `input_schema`.

**`ToolCall(id, name, arguments)`**: the model asking for `name`. `arguments` is a dict.

Every call must be answered by a `tool` message straight after it, with its `tool_call_id` set to the
call's `id`. This is the shape of a conversation after one tool call:

```python
from forgeway_kit import Tool, ToolCall

weather = Tool(
    name="get_weather",
    description="The weather in a city.",
    input_schema={
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
)
call = ToolCall(id="call-1", name="get_weather", arguments={"city": "Leeds"})
conversation = [
    Message(role="user", content="Weather in Leeds?"),
    Message(role="assistant", content="", tool_calls=(call,)),
    Message(role="tool", content="rain, 9C", tool_call_id="call-1"),
]
```

## Streaming

`client.stream(...)` takes the same arguments as `complete` and returns an iterator of events.

- `TextDelta` (`text`): The next piece of reply text.
- `ToolCallStart` (`id`, `name`): The model began a tool call.
- `ToolCallDelta` (`id`, `partial_json`): The next piece of the call's arguments, as JSON text.
- `ToolCallEnd` (`id`): The call's arguments are complete.
- `MessageEnd` (`stop_reason`, `usage`): Always the last event.

## Counting tokens

**`tokenize(text)`** returns a list of tokens: runs of word characters, and single punctuation marks
(the regular expression `\w+|[^\w\s]`). **`count_tokens(text)`** returns how many there are. `FakeModel`
reports usage with the same counter, so budgets you compute with it are exact.

```python
from forgeway_kit import count_tokens, tokenize

tokenize("Hi, Ada")  # ["Hi", ",", "Ada"]
count_tokens("Hi, Ada")  # 3
```

## Embeddings

`Embedder` is the protocol: a `dimensions` property, and `embed(texts)`, which takes a list of strings
and returns a list of vectors, one per text. **`HashingEmbedder(dimensions=256)`** is the deterministic
one. It captures shared words and letters, not meaning. **`cosine_similarity(a, b)`** compares two
vectors of the same length, and gives `0.0` if either is all zeros.

```python
from forgeway_kit import HashingEmbedder, cosine_similarity

first, second = HashingEmbedder(64).embed(["red car", "red cars"])
cosine_similarity(first, second)
```

## Errors

- `ModelError`: The base class of the three below.
- `RateLimitError(message, retry_after_s=1.0)`: Slow down. Safe to retry after `retry_after_s` seconds.
- `ServerError`: A failure on the provider's side. Usually safe to retry.
- `InvalidRequestError`: The request itself is wrong, for example too many tokens. Retrying will not help.

## The fake model

`FakeModel` is the deterministic model the grader runs your code against. You can use it yourself to
try your code.

```text
FakeModel(responder, context_window=8000, models=(), default_model=None, rate_limit=None,
          clock=time.monotonic, stream_chunk_tokens=3)
```

- **`responder`** is a function of the `Request`. It returns reply text, a list of `ToolCall`s, a
  `Refusal` or a `StreamFailure`, or raises a `ModelError`.
- **`requests`** lists every `Request` it received, including those that failed.
- It rejects what a real API rejects: unanswered tool calls raise `InvalidRequestError`, and so does a
  prompt larger than `context_window` tokens.
- **Prompt cache.** `cache_read_input_tokens` is the longest prefix shared with the previous request
  to the same model: system prompt and tools as one block, then each message, while identical.
- **Effort.** `"low"`, `"medium"` and `"high"` add 16, 64 and 256 `reasoning_tokens`.

- `Request` (`messages`, `system`, `max_tokens`, `temperature`, `tools`, `model`, `response_format`, `tool_choice`, `effort`, `sample`): One recorded call. `sample` counts the earlier identical requests.
- `Refusal` (`text=""`): A reply that stops with `"refusal"`.
- `StreamFailure` (`after_events`, `error`, `reply=""`): `stream` raises `error` after that many events; `complete` raises it at once.
- `RateLimit` (`max_requests`, `per_seconds`): Past this, the fake raises `RateLimitError`.
- `ModelCard` (`name`, `input_usd_per_mtok`, `output_usd_per_mtok`, `cache_read_usd_per_mtok`, `base_latency_ms`, `ms_per_output_token`, `context_window`): A model the fake can serve. Data only: it sets `latency_ms` (`base_latency_ms + ms_per_output_token * output_tokens`) and the context window.

```python
from forgeway_kit import ModelCard

card = ModelCard(
    name="small",
    input_usd_per_mtok=1.0,
    output_usd_per_mtok=5.0,
    cache_read_usd_per_mtok=0.1,
    base_latency_ms=200.0,
    ms_per_output_token=10.0,
    context_window=4000,
)
fake = FakeModel(responder=lambda request: "Hello.", models=[card])
fake.complete([Message(role="user", content="Hi")], model="small").latency_ms
```

## `forgeway_kit.mcp`

The MCP branch has you write the protocol yourself, as plain dicts, so this module is small.

- `PROTOCOL_VERSION`: `"2025-11-25"`, the revision the branch teaches.
- `JSONRPC_VERSION`: `"2.0"`.
- `ErrorCode`: `PARSE_ERROR`, `INVALID_REQUEST`, `METHOD_NOT_FOUND`, `INVALID_PARAMS`, `INTERNAL_ERROR`, `RESOURCE_NOT_FOUND`.
- `McpError(code, message, data=None)`: A server answered with a JSON-RPC error. It has `.code`, `.message` and `.data`.

## `forgeway_kit.live`

Real clients, for your own machine with your own key. See the [live mode guide](/live-mode). They
refuse to start while grading.

- `AnthropicClient(model=..., *, base_url=None, timeout_s=...)`: The Anthropic API. Needs `ANTHROPIC_API_KEY`.
- `OpenAIClient(model, *, base_url=None, timeout_s=...)`: OpenAI, or any compatible server at `base_url`.
- `Metered(client, *, rates=None, out=None)`: Wraps a client and prints each call's tokens, latency and estimated cost.
- `client_from_env()`: The metered client `FORGEWAY_LIVE`, `FORGEWAY_MODEL` and `FORGEWAY_BASE_URL` select.

`python -m forgeway_kit.live check` makes one small call to test your set-up.
