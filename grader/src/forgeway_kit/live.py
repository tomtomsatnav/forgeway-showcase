"""Live model clients: the toolkit's only network code, never used in grading.

`AnthropicClient` speaks the Messages API and `OpenAIClient` speaks Chat Completions (with
`base_url`, any OpenAI-compatible server: Ollama, LM Studio, vLLM, ...). Both use only the
standard library and implement `complete` and `stream` with every toolkit argument, so learner
code written against `FakeModel` runs unchanged.

Keys come only from the environment (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`), are read when a
client is made, and go nowhere but the provider: not into a repr, an error message or a file.

    FORGEWAY_LIVE=anthropic python -m forgeway_kit.live check      # one tiny call
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import IO, Any, TextIO

from forgeway_kit.errors import InvalidRequestError, ModelError, RateLimitError, ServerError
from forgeway_kit.llm import (
    Completion,
    Effort,
    Message,
    MessageEnd,
    StopReason,
    StreamEvent,
    StreamingModelClient,
    TextDelta,
    Tool,
    ToolCall,
    ToolCallDelta,
    ToolCallEnd,
    ToolCallStart,
    ToolChoice,
    Usage,
    _grading,
)

ANTHROPIC_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2026-10-21"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-5-5"
OPENAI_URL = "https://api.openai.com/v1"
TIMEOUT_S = 600.0

# USD per million tokens: (input, output, cache read). Pass Metered(rates=...) for others.
DEFAULT_RATES: dict[str, tuple[float, float, float]] = {
    "claude-fable-5-1": (10.0, 50.0, 0.25),
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-sonnet-5-5": (2.0, 10.0, 0.10),
}

_ANTHROPIC_STOPS: dict[str, StopReason] = {
    "end_turn": "end_turn",
    "stop_sequence": "end_turn",
    "pause_turn": "end_turn",
    "tool_use": "tool_use",
    "max_tokens": "max_tokens",
    "model_context_window_exceeded": "max_tokens",
    "refusal": "refusal",
}
_OPENAI_STOPS: dict[str, StopReason] = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "function_call": "tool_use",
    "content_filter": "refusal",
}


def _urlopen(request: urllib.request.Request, timeout: float) -> IO[bytes]:
    """The one network call; tests replace it."""
    response: IO[bytes] = urllib.request.urlopen(request, timeout=timeout)  # noqa: S310
    return response


class _Live:
    """What both clients share: the key held out of sight, the POST, and error mapping."""

    def __init__(self, model: str, base_url: str, key: str | None, timeout_s: float) -> None:
        if _grading():
            raise RuntimeError("live clients are never used while grading")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

        def secret() -> str | None:
            return key

        self._key = secret  # a closure, so vars(client) never shows the key

    def __repr__(self) -> str:
        return f"{type(self).__name__}(model={self.model!r}, base_url={self.base_url!r})"

    def __reduce__(self) -> Any:
        raise TypeError(f"{type(self).__name__} holds an API key, so it cannot be pickled")

    def _headers(self) -> dict[str, str]:
        raise NotImplementedError

    def _post(self, path: str, body: Mapping[str, Any]) -> IO[bytes]:
        request = urllib.request.Request(  # noqa: S310 - https or a URL the learner chose
            self.base_url + path,
            data=json.dumps(body).encode(),
            headers={"content-type": "application/json", **self._headers()},
            method="POST",
        )
        try:
            return _urlopen(request, self.timeout_s)
        except urllib.error.HTTPError as exc:
            raise self._http_error(exc.code, exc.headers.get("retry-after"), exc.read()) from None
        except (urllib.error.URLError, OSError) as exc:
            raise ServerError(self._scrub(f"could not reach {self.base_url}: {exc}")) from None

    def _scrub(self, text: str) -> str:
        key = self._key()
        return text.replace(key, "[redacted]") if key else text

    def _http_error(self, status: int, retry_after: str | None, raw: bytes) -> ModelError:
        try:
            detail = str(json.loads(raw)["error"]["message"])
        except (ValueError, KeyError, TypeError):
            detail = raw.decode("utf-8", errors="replace")[:500]
        message = self._scrub(f"{status} from {self.base_url}: {detail}")
        if status == 429:
            try:
                wait = float(retry_after) if retry_after else 1.0
            except ValueError:
                wait = 1.0
            return RateLimitError(message, retry_after_s=wait)
        if status >= 500:
            return ServerError(message)
        return InvalidRequestError(message)

    def _stream_error(self, error: Mapping[str, Any]) -> ModelError:
        kind = str(error.get("type", ""))
        message = self._scrub(f"stream failed: {kind}: {error.get('message', '')}")
        if kind == "rate_limit_error":
            return RateLimitError(message)
        if kind in ("overloaded_error", "api_error", "server_error", ""):
            return ServerError(message)
        return InvalidRequestError(message)


class AnthropicClient(_Live):
    """The Anthropic Messages API. Needs `ANTHROPIC_API_KEY`.

    `temperature` is accepted but not sent: API version 2026-10-21 rejects sampling
    parameters. `effort` and `response_format` go in `output_config`. Thinking blocks from a
    tool-calling turn are kept (by tool call ids) and sent back with that turn, as the API needs.
    """

    def __init__(
        self,
        model: str = DEFAULT_ANTHROPIC_MODEL,
        *,
        base_url: str | None = None,
        timeout_s: float = TIMEOUT_S,
    ) -> None:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        super().__init__(model, base_url or ANTHROPIC_URL, key, timeout_s)
        self._turns: dict[tuple[str, ...], list[dict[str, Any]]] = {}

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self._key() or "", "anthropic-version": ANTHROPIC_VERSION}

    def complete(
        self,
        messages: Sequence[Message],
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.0,
        tools: Sequence[Tool] = (),
        model: str | None = None,
        response_format: Mapping[str, Any] | None = None,
        tool_choice: ToolChoice = "auto",
        effort: Effort | None = None,
    ) -> Completion:
        body = self.body(
            messages, system, max_tokens, tools, model, response_format, tool_choice, effort
        )
        started = time.perf_counter()
        with self._post("/v1/messages", body) as response:
            payload = json.loads(response.read())
        return self.parse(payload, (time.perf_counter() - started) * 1000)

    def stream(
        self,
        messages: Sequence[Message],
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.0,
        tools: Sequence[Tool] = (),
        model: str | None = None,
        response_format: Mapping[str, Any] | None = None,
        tool_choice: ToolChoice = "auto",
        effort: Effort | None = None,
    ) -> Iterator[StreamEvent]:
        body = self.body(
            messages, system, max_tokens, tools, model, response_format, tool_choice, effort
        )
        response = self._post("/v1/messages", {**body, "stream": True})
        return self.parse_stream(response)

    def body(
        self,
        messages: Sequence[Message],
        system: str | None,
        max_tokens: int,
        tools: Sequence[Tool],
        model: str | None,
        response_format: Mapping[str, Any] | None,
        tool_choice: ToolChoice,
        effort: Effort | None,
    ) -> dict[str, Any]:
        """The JSON body sent to /v1/messages."""
        body: dict[str, Any] = {
            "model": model or self.model,
            "max_tokens": max_tokens,
            "messages": self._messages(messages),
        }
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ]
            body["tool_choice"] = (
                {"type": "tool", "name": tool_choice["name"]}
                if isinstance(tool_choice, Mapping)
                else {"type": tool_choice}
            )
        output_config: dict[str, Any] = {}
        if effort:
            output_config["effort"] = effort
        if response_format is not None:
            output_config["format"] = {"type": "json_schema", "schema": response_format}
        if output_config:
            body["output_config"] = output_config
        return json.loads(json.dumps(body))  # type: ignore[no-any-return]

    def _messages(self, messages: Sequence[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "tool":
                result = {
                    "type": "tool_result",
                    "tool_use_id": m.tool_call_id,
                    "content": m.content,
                }
                last = out[-1] if out else None
                # Parallel results go back in one user message.
                if last and last["role"] == "user" and isinstance(last["content"], list):
                    last["content"].append(result)
                else:
                    out.append({"role": "user", "content": [result]})
            elif m.role == "assistant" and m.tool_calls:
                uses = [
                    {"type": "tool_use", "id": c.id, "name": c.name, "input": dict(c.arguments)}
                    for c in m.tool_calls
                ]
                kept = self._turns.get(tuple(c.id for c in m.tool_calls))
                if kept is not None and [b for b in kept if b.get("type") == "tool_use"] == uses:
                    out.append({"role": "assistant", "content": kept})
                else:
                    text = [{"type": "text", "text": m.content}] if m.content else []
                    out.append({"role": "assistant", "content": text + uses})
            else:
                out.append({"role": m.role, "content": m.content})
        return out

    def _keep(self, content: list[dict[str, Any]]) -> None:
        ids = tuple(b["id"] for b in content if b.get("type") == "tool_use")
        if ids:
            self._turns[ids] = content
            while len(self._turns) > 256:
                self._turns.pop(next(iter(self._turns)))

    def parse(self, payload: Mapping[str, Any], latency_ms: float) -> Completion:
        """A Messages API response as a `Completion`."""
        content = list(payload.get("content") or [])
        self._keep(content)
        return Completion(
            text="".join(b["text"] for b in content if b.get("type") == "text"),
            stop_reason=_ANTHROPIC_STOPS.get(str(payload.get("stop_reason")), "end_turn"),
            usage=_anthropic_usage(payload.get("usage") or {}),
            tool_calls=tuple(
                ToolCall(b["id"], b["name"], b.get("input") or {})
                for b in content
                if b.get("type") == "tool_use"
            ),
            model=str(payload.get("model") or self.model),
            latency_ms=latency_ms,
        )

    def parse_stream(self, response: IO[bytes]) -> Iterator[StreamEvent]:
        """Server-sent events from the Messages API as toolkit events."""
        usage: dict[str, Any] = {}
        blocks: dict[int, dict[str, Any]] = {}
        stop = "end_turn"
        with response:
            for event, data in _sse(response):
                message = json.loads(data)
                kind = message.get("type", event)
                if kind == "message_start":
                    usage.update(message["message"].get("usage") or {})
                elif kind == "content_block_start":
                    block = dict(message["content_block"])
                    blocks[message["index"]] = block
                    if block["type"] == "tool_use":
                        block["input"] = ""
                        yield ToolCallStart(block["id"], block["name"])
                elif kind == "content_block_delta":
                    delta, block = message["delta"], blocks[message["index"]]
                    if delta["type"] == "text_delta":
                        block["text"] = block.get("text", "") + delta["text"]
                        yield TextDelta(delta["text"])
                    elif delta["type"] == "input_json_delta":
                        block["input"] += delta["partial_json"]
                        yield ToolCallDelta(block["id"], delta["partial_json"])
                    elif delta["type"] == "thinking_delta":
                        block["thinking"] = block.get("thinking", "") + delta["thinking"]
                    elif delta["type"] == "signature_delta":
                        block["signature"] = delta["signature"]
                elif kind == "content_block_stop":
                    block = blocks[message["index"]]
                    if block["type"] == "tool_use":
                        block["input"] = json.loads(block["input"] or "{}")
                        yield ToolCallEnd(block["id"])
                elif kind == "message_delta":
                    stop = message.get("delta", {}).get("stop_reason") or stop
                    usage.update(message.get("usage") or {})
                elif kind == "error":
                    raise self._stream_error(message.get("error") or {})
        self._keep([blocks[i] for i in sorted(blocks)])
        yield MessageEnd(_ANTHROPIC_STOPS.get(stop, "end_turn"), _anthropic_usage(usage))


def _anthropic_usage(usage: Mapping[str, Any]) -> Usage:
    """Anthropic counts cache reads and writes apart from `input_tokens`; the toolkit's
    `input_tokens` is the whole prompt."""
    cached = int(usage.get("cache_read_input_tokens") or 0)
    written = int(usage.get("cache_creation_input_tokens") or 0)
    return Usage(
        input_tokens=int(usage.get("input_tokens") or 0) + cached + written,
        output_tokens=int(usage.get("output_tokens") or 0),
        cache_read_input_tokens=cached,
    )


class OpenAIClient(_Live):
    """OpenAI Chat Completions, or any compatible server at `base_url`.

    `OPENAI_API_KEY` is required for OpenAI itself and sent to a compatible server if set.
    `effort` becomes `reasoning_effort` and `response_format` a strict `json_schema` format.
    """

    def __init__(
        self, model: str, *, base_url: str | None = None, timeout_s: float = TIMEOUT_S
    ) -> None:
        key = os.environ.get("OPENAI_API_KEY") or None
        if key is None and base_url is None:
            raise RuntimeError("OPENAI_API_KEY is not set")
        super().__init__(model, base_url or OPENAI_URL, key, timeout_s)
        self._official = self.base_url == OPENAI_URL

    def _headers(self) -> dict[str, str]:
        key = self._key()
        return {"authorization": f"Bearer {key}"} if key else {}

    def complete(
        self,
        messages: Sequence[Message],
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.0,
        tools: Sequence[Tool] = (),
        model: str | None = None,
        response_format: Mapping[str, Any] | None = None,
        tool_choice: ToolChoice = "auto",
        effort: Effort | None = None,
    ) -> Completion:
        body = self.body(
            messages, system, max_tokens, temperature, tools, model, response_format,
            tool_choice, effort,
        )  # fmt: skip
        started = time.perf_counter()
        with self._post("/chat/completions", body) as response:
            payload = json.loads(response.read())
        return self.parse(payload, (time.perf_counter() - started) * 1000)

    def stream(
        self,
        messages: Sequence[Message],
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.0,
        tools: Sequence[Tool] = (),
        model: str | None = None,
        response_format: Mapping[str, Any] | None = None,
        tool_choice: ToolChoice = "auto",
        effort: Effort | None = None,
    ) -> Iterator[StreamEvent]:
        body = self.body(
            messages, system, max_tokens, temperature, tools, model, response_format,
            tool_choice, effort,
        )  # fmt: skip
        body.update(stream=True, stream_options={"include_usage": True})
        return self.parse_stream(self._post("/chat/completions", body))

    def body(
        self,
        messages: Sequence[Message],
        system: str | None,
        max_tokens: int,
        temperature: float,
        tools: Sequence[Tool],
        model: str | None,
        response_format: Mapping[str, Any] | None,
        tool_choice: ToolChoice,
        effort: Effort | None,
    ) -> dict[str, Any]:
        """The JSON body sent to /chat/completions."""
        chat: list[dict[str, Any]] = [{"role": "system", "content": system}] if system else []
        for m in messages:
            if m.role == "tool":
                chat.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content})
            elif m.tool_calls:
                calls = [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": json.dumps(dict(c.arguments))},
                    }
                    for c in m.tool_calls
                ]
                chat.append(
                    {"role": "assistant", "content": m.content or None, "tool_calls": calls}
                )
            else:
                chat.append({"role": m.role, "content": m.content})
        body: dict[str, Any] = {"model": model or self.model, "messages": chat}
        # shortcut: OpenAI's reasoning models reject max_tokens and non-default temperatures,
        # while compatible servers take both; send each only where it is understood.
        if self._official:
            body["max_completion_tokens"] = max_tokens
        else:
            body["max_tokens"] = max_tokens
            body["temperature"] = temperature
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in tools
            ]
            body["tool_choice"] = (
                {"type": "function", "function": {"name": tool_choice["name"]}}
                if isinstance(tool_choice, Mapping)
                else {"auto": "auto", "any": "required", "none": "none"}[tool_choice]
            )
        if response_format is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": response_format, "strict": True},
            }
        if effort:
            body["reasoning_effort"] = effort
        return json.loads(json.dumps(body))  # type: ignore[no-any-return]

    def parse(self, payload: Mapping[str, Any], latency_ms: float) -> Completion:
        """A Chat Completions response as a `Completion`."""
        choice = payload["choices"][0]
        message = choice.get("message") or {}
        refusal = message.get("refusal")
        stop = _OPENAI_STOPS.get(str(choice.get("finish_reason")), "end_turn")
        return Completion(
            text=refusal or message.get("content") or "",
            stop_reason="refusal" if refusal else stop,
            usage=_openai_usage(payload.get("usage") or {}),
            tool_calls=tuple(
                ToolCall(c["id"], c["function"]["name"], self._arguments(c["function"]))
                for c in message.get("tool_calls") or []
            ),
            model=str(payload.get("model") or self.model),
            latency_ms=latency_ms,
        )

    def _arguments(self, function: Mapping[str, Any]) -> dict[str, Any]:
        try:
            arguments = json.loads(function.get("arguments") or "{}")
        except ValueError:
            arguments = None
        if not isinstance(arguments, dict):
            raise ServerError(f"the model sent arguments for {function.get('name')} that are not "
                              "a JSON object")  # fmt: skip
        return arguments

    def parse_stream(self, response: IO[bytes]) -> Iterator[StreamEvent]:
        """Server-sent chunks from Chat Completions as toolkit events."""
        calls: dict[int, str] = {}
        stop: StopReason = "end_turn"
        usage = Usage(0, 0)
        refused = False
        with response:
            for _, data in _sse(response):
                if data.strip() == "[DONE]":
                    break
                chunk = json.loads(data)
                if chunk.get("error"):
                    raise self._stream_error(chunk["error"])
                if chunk.get("usage"):
                    usage = _openai_usage(chunk["usage"])
                for choice in chunk.get("choices") or []:
                    delta = choice.get("delta") or {}
                    if delta.get("content"):
                        yield TextDelta(delta["content"])
                    if delta.get("refusal"):
                        refused = True
                        yield TextDelta(delta["refusal"])
                    for call in delta.get("tool_calls") or []:
                        index, function = call.get("index", 0), call.get("function") or {}
                        if index not in calls:
                            calls[index] = call.get("id") or f"call_{index}"
                            yield ToolCallStart(calls[index], function.get("name", ""))
                        if function.get("arguments"):
                            yield ToolCallDelta(calls[index], function["arguments"])
                    if choice.get("finish_reason"):
                        stop = _OPENAI_STOPS.get(choice["finish_reason"], "end_turn")
        for call_id in calls.values():
            yield ToolCallEnd(call_id)
        yield MessageEnd("refusal" if refused else stop, usage)


def _openai_usage(usage: Mapping[str, Any]) -> Usage:
    prompt = usage.get("prompt_tokens_details") or {}
    completion = usage.get("completion_tokens_details") or {}
    return Usage(
        input_tokens=int(usage.get("prompt_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or 0),
        cache_read_input_tokens=int(prompt.get("cached_tokens") or 0),
        reasoning_tokens=int(completion.get("reasoning_tokens") or 0),
    )


def _sse(lines: Iterable[bytes]) -> Iterator[tuple[str, str]]:
    """(event, data) for each server-sent event."""
    event, data = "", list[str]()
    for raw in lines:
        line = raw.decode("utf-8").rstrip("\r\n")
        if not line:
            if data:
                yield event, "\n".join(data)
            event, data = "", []
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[6:] if line.startswith("data: ") else line[5:])
    if data:
        yield event, "\n".join(data)


class Metered:
    """Wraps a client and prints each call's model, tokens, cache reads, latency and an
    estimated cost to stderr. `rates` adds to or overrides `DEFAULT_RATES`."""

    def __init__(
        self,
        client: StreamingModelClient,
        *,
        rates: Mapping[str, tuple[float, float, float]] | None = None,
        out: TextIO | None = None,
    ) -> None:
        if _grading():
            raise RuntimeError("Metered is never used while grading")
        self.client = client
        self.rates = {**DEFAULT_RATES, **(rates or {})}
        self._out = out

    def __repr__(self) -> str:
        return f"Metered({self.client!r})"

    def complete(self, messages: Sequence[Message], **options: Any) -> Completion:
        started = time.perf_counter()
        completion = self.client.complete(messages, **options)
        latency = completion.latency_ms or (time.perf_counter() - started) * 1000
        self._report(completion.model or self._model(options), completion.usage, latency)
        return completion

    def stream(self, messages: Sequence[Message], **options: Any) -> Iterator[StreamEvent]:
        started = time.perf_counter()
        events = self.client.stream(messages, **options)
        return self._watch(events, self._model(options), started)

    def _watch(
        self, events: Iterator[StreamEvent], model: str, started: float
    ) -> Iterator[StreamEvent]:
        for event in events:
            if isinstance(event, MessageEnd):
                self._report(model, event.usage, (time.perf_counter() - started) * 1000)
            yield event

    def _model(self, options: Mapping[str, Any]) -> str:
        return str(options.get("model") or getattr(self.client, "model", ""))

    def _report(self, model: str, usage: Usage, latency_ms: float) -> None:
        if _grading():  # also reachable without __init__, as Metered._report(anything, ...)
            raise RuntimeError("Metered is never used while grading")
        rate = self.rates.get(model)
        if rate is None:
            cost = "cost unknown (pass Metered(rates=...))"
        else:
            fresh = usage.input_tokens - usage.cache_read_input_tokens
            usd = (fresh * rate[0] + usage.output_tokens * rate[1]
                   + usage.cache_read_input_tokens * rate[2]) / 1_000_000  # fmt: skip
            cost = f"~${usd:.4f}"
        print(
            f"[forgeway] {model}  in {usage.input_tokens} (cache {usage.cache_read_input_tokens})"
            f"  out {usage.output_tokens} (reasoning {usage.reasoning_tokens})"
            f"  {latency_ms:.0f} ms  {cost}",
            file=self._out or sys.stderr,
        )


def client_from_env() -> Metered:
    """The metered live client `FORGEWAY_LIVE`, `FORGEWAY_MODEL` and `FORGEWAY_BASE_URL` select."""
    kind = os.environ.get("FORGEWAY_LIVE", "").strip().lower()
    model = os.environ.get("FORGEWAY_MODEL") or None
    base_url = os.environ.get("FORGEWAY_BASE_URL") or None
    client: StreamingModelClient
    if kind == "anthropic":
        client = AnthropicClient(model or DEFAULT_ANTHROPIC_MODEL, base_url=base_url)
    elif kind in ("openai", "openai-compatible"):
        if not model:
            raise RuntimeError("set FORGEWAY_MODEL to the model to use")
        if kind == "openai-compatible" and not base_url:
            raise RuntimeError(
                "set FORGEWAY_BASE_URL to the server, for example http://localhost:11434/v1"
            )
        client = OpenAIClient(model, base_url=base_url)
    else:
        raise RuntimeError(
            f"FORGEWAY_LIVE must be anthropic, openai or openai-compatible, not {kind!r}"
        )
    return Metered(client)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args != ["check"]:
        print("usage: python -m forgeway_kit.live check", file=sys.stderr)
        return 2
    try:
        client = client_from_env()
        effort: Effort | None = "low" if isinstance(client.client, AnthropicClient) else None
        completion = client.complete(
            [Message("user", "Reply with the single word: ready")], max_tokens=256, effort=effort
        )
    except (ModelError, RuntimeError) as exc:
        print(f"live check failed: {exc}", file=sys.stderr)
        return 1
    print(f"{completion.model}: {completion.text!r} (stop: {completion.stop_reason})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
