"""A provider-neutral chat-completion interface and a deterministic fake implementation."""

from __future__ import annotations

import json
import os
import random
import re
import sys
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Literal, Protocol

from forgeway_kit.errors import InvalidRequestError, RateLimitError
from forgeway_kit.tokens import count_tokens, tokenize

Role = Literal["user", "assistant", "tool"]
StopReason = Literal["end_turn", "max_tokens", "tool_use", "refusal"]
Effort = Literal["low", "medium", "high"]
# "auto", "any" (some tool), "none", or {"name": tool} for that tool.
ToolChoice = Literal["auto", "any", "none"] | Mapping[str, str]


@dataclass(frozen=True)
class Tool:
    """A function the model may ask to call. `input_schema` is a JSON Schema object."""

    name: str
    description: str
    input_schema: Mapping[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """The model asking for `name` to be called with `arguments`."""

    id: str
    name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True)
class Message:
    """One turn in a conversation. The system prompt is passed separately, as most APIs do.

    An assistant message may carry `tool_calls`; each must be answered by a `tool` message whose
    `tool_call_id` names the call and whose `content` is the result.
    """

    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None

    def __post_init__(self) -> None:
        if self.tool_calls and self.role != "assistant":
            raise ValueError("only assistant messages can contain tool calls")
        if (self.role == "tool") != (self.tool_call_id is not None):
            raise ValueError("tool messages, and only tool messages, need a tool_call_id")


@dataclass(frozen=True)
class Usage:
    """Tokens a call used. `input_tokens` counts the whole prompt, cache reads included;
    `cache_read_input_tokens` is the part of it read from the prompt cache. `output_tokens`
    includes `reasoning_tokens`, which are billed as output."""

    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int = 0
    reasoning_tokens: int = 0


@dataclass(frozen=True)
class Completion:
    text: str
    stop_reason: StopReason
    usage: Usage
    tool_calls: tuple[ToolCall, ...] = ()
    model: str = ""
    latency_ms: float = 0.0


@dataclass(frozen=True)
class ModelCard:
    """A model a `FakeModel` can serve, with its prices and speed. Data only."""

    name: str
    input_usd_per_mtok: float
    output_usd_per_mtok: float
    cache_read_usd_per_mtok: float
    base_latency_ms: float
    ms_per_output_token: float
    context_window: int


@dataclass(frozen=True)
class RateLimit:
    """At most `max_requests` requests in any `per_seconds` window."""

    max_requests: int
    per_seconds: float

    def __post_init__(self) -> None:
        if type(self.max_requests) is not int or self.max_requests < 1:
            raise ValueError("max_requests must be an int of at least 1")
        if type(self.per_seconds) not in (int, float) or self.per_seconds <= 0:
            raise ValueError("per_seconds must be a positive number")


@dataclass(frozen=True)
class Refusal:
    """A responder's reply when the model declines: the completion stops with "refusal"."""

    text: str = ""


@dataclass(frozen=True)
class StreamFailure:
    """A responder's reply that makes `FakeModel.stream` raise `error` after `after_events`
    events of `reply` (never the final `MessageEnd`). `complete` raises `error` at once."""

    after_events: int
    error: Exception
    reply: str | Sequence[ToolCall] | Refusal = ""

    def __post_init__(self) -> None:
        if type(self.after_events) is not int or self.after_events < 0:
            raise ValueError("after_events must be an int of at least 0")
        if not isinstance(self.error, Exception):
            raise TypeError("error must be an exception instance, such as ServerError(...)")


@dataclass(frozen=True)
class TextDelta:
    """The next piece of reply text."""

    text: str


@dataclass(frozen=True)
class ToolCallStart:
    """The model began a tool call."""

    id: str
    name: str


@dataclass(frozen=True)
class ToolCallDelta:
    """The next piece of a tool call's arguments, as JSON text (not valid JSON on its own)."""

    id: str
    partial_json: str


@dataclass(frozen=True)
class ToolCallEnd:
    """A tool call's arguments are complete."""

    id: str


@dataclass(frozen=True)
class MessageEnd:
    """The last event of a stream."""

    stop_reason: StopReason
    usage: Usage


StreamEvent = TextDelta | ToolCallStart | ToolCallDelta | ToolCallEnd | MessageEnd


@dataclass(frozen=True)
class Request:
    """A recorded call, so graders can assert on what reached the model.

    `FakeModel` builds it from plain built-ins only (exact `str`, `int`, `float`, `bool`,
    `None`, `list` and `dict`), as a provider receives only serialised JSON.
    """

    messages: tuple[Message, ...]
    system: str | None
    max_tokens: int
    temperature: float
    tools: tuple[Tool, ...] = ()
    model: str = ""
    response_format: Mapping[str, Any] | None = None
    tool_choice: ToolChoice = "auto"
    effort: Effort | None = None
    sample: int = 0


class ModelClient(Protocol):
    """Anything that can complete a conversation.

    The protocol keeps the original arguments so every client still conforms;
    `StreamingModelClient` adds `model`, `response_format`, `tool_choice`, `effort` and `stream`.
    """

    def complete(
        self,
        messages: Sequence[Message],
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.0,
        tools: Sequence[Tool] = (),
    ) -> Completion: ...


class StreamingModelClient(ModelClient, Protocol):
    """A client with every toolkit argument and `stream`: `FakeModel` and the live clients."""

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
    ) -> Completion: ...

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
    ) -> Iterator[StreamEvent]: ...


Reply = str | Sequence[ToolCall] | Refusal | StreamFailure
Responder = Callable[[Request], Reply]

# Reasoning tokens the fake adds for each effort level; billed as output.
_REASONING_TOKENS = {"low": 16, "medium": 64, "high": 256}
_LOCK = threading.Lock()  # guards FakeModel bookkeeping; never held while user code runs


@dataclass
class FakeModel:
    """A deterministic stand-in for a real model.

    Responses come from `responder`, a function of the request that returns reply text, a
    list of `ToolCall`s to ask for tools, a `Refusal`, or a `StreamFailure`; it may also raise
    a `ModelError` to simulate failures. Conversations are validated as a real API would: tool
    calls must be answered, in order, before the conversation continues. Every request is
    recorded in `requests`, including ones that fail. Usage is measured with
    `forgeway_kit.count_tokens`. Requests whose input exceeds `context_window` tokens are
    rejected, as a real API would.

    Like a real client, it serialises each request before sending it: `requests` and the
    responder see a copy rebuilt from plain built-ins, never the caller's own objects, and a
    value JSON cannot carry raises `TypeError` before anything is sent.

    Optional behaviour, all deterministic:

    - `models` (`ModelCard`s) and `default_model`: an unknown `model=` raises
      `InvalidRequestError`; the card sets `Completion.latency_ms` (`base_latency_ms` plus
      `ms_per_output_token` per output token) and overrides `context_window`.
    - `Usage.cache_read_input_tokens`: the tokens of the longest common prefix with the previous
      recorded request to the same model, compared block by block (system and tools as one
      block, then each message), counted while they are identical.
    - `effort="low" | "medium" | "high"` adds 16, 64 or 256 `reasoning_tokens` (billed as output).
    - `Request.sample` counts the earlier requests to this fake identical to this one.
    - `rate_limit` raises `RateLimitError(retry_after_s=...)` past the limit, timed by `clock`;
      a rate-limited request is still recorded.
    - `tool_choice` is enforced on the responder: under "any" or {"name": ...} it must ask for
      tools (only that one, for a name) and under "none" it must not; breaking this is a test
      bug and raises `ValueError`.
    """

    responder: Responder = field(default=lambda request: "OK")
    context_window: int = 8000
    requests: list[Request] = field(default_factory=list)
    models: Sequence[ModelCard] = ()
    default_model: str | None = None
    rate_limit: RateLimit | None = None
    clock: Callable[[], float] = time.monotonic
    stream_chunk_tokens: int = 3
    _sent_at: list[float] = field(default_factory=list, init=False, repr=False, compare=False)
    _samples: dict[str, int] = field(default_factory=dict, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.models = tuple(self.models)
        names = [card.name for card in self.models]
        if not all(isinstance(card, ModelCard) for card in self.models):
            raise TypeError("models must be ModelCard instances")
        if len(set(names)) != len(names):
            raise ValueError(f"model names must be unique: {names}")
        if self.default_model is not None and self.models and self.default_model not in names:
            raise ValueError(f"default_model {self.default_model!r} is not one of {names}")
        if type(self.stream_chunk_tokens) is not int or self.stream_chunk_tokens < 1:
            raise ValueError("stream_chunk_tokens must be an int of at least 1")

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
        sent = self._send(
            messages, system, max_tokens, temperature, tools, model, response_format,
            tool_choice, effort,
        )  # fmt: skip
        reply = sent.reply
        if isinstance(reply, StreamFailure):
            raise reply.error
        return self._finish(sent, reply)

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
        """Like `complete`, but the reply arrives as events: `TextDelta`s of about
        `stream_chunk_tokens` tokens, `ToolCallStart` / `ToolCallDelta` / `ToolCallEnd` per
        call, then `MessageEnd`. The request is sent (and recorded) when this is called."""
        sent = self._send(
            messages, system, max_tokens, temperature, tools, model, response_format,
            tool_choice, effort,
        )  # fmt: skip
        reply = sent.reply
        failure: StreamFailure | None = None
        if isinstance(reply, StreamFailure):
            failure = reply
            reply = failure.reply
        completion = self._finish(sent, reply)
        return _play(_events(completion, self.stream_chunk_tokens), failure)

    def _send(
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
    ) -> _Sent:
        request = _serialise(
            messages, system, max_tokens, temperature, tools, model, response_format,
            tool_choice, effort,
        )  # fmt: skip
        if not request.messages:
            raise ValueError("messages must not be empty")
        if request.messages[-1].role not in ("user", "tool"):
            raise ValueError("the last message must come from the user or be a tool result")
        if request.max_tokens < 1:
            raise ValueError("max_tokens must be at least 1")
        cards = {card.name: card for card in self.models}
        name = request.model or self.default_model or (self.models[0].name if cards else "")
        request = replace(request, model=name)
        with _LOCK:
            previous = self.requests[-1] if self.requests else None
            key = json.dumps(asdict(request), sort_keys=True)
            request = replace(request, sample=self._samples.get(key, 0))
            self._samples[key] = request.sample + 1
            self.requests.append(request)
            if self.rate_limit is not None:
                self._check_rate(self.rate_limit)
        _check_tool_protocol(request.messages)
        if cards and name not in cards:
            raise InvalidRequestError(f"unknown model {name!r}; this API serves {list(cards)}")
        _check_tool_choice(request)
        card = cards.get(name)
        window = card.context_window if card else self.context_window
        prompt_tokens = sum(_message_tokens(m) for m in request.messages) + count_tokens(
            request.system or ""
        )
        if prompt_tokens > window:
            raise InvalidRequestError(
                f"prompt is {prompt_tokens} tokens; the context window is {window}"
            )
        cached = _prefix_tokens(previous, request) if previous else 0
        return _Sent(request, self.responder(request), prompt_tokens, cached, card)

    def _check_rate(self, limit: RateLimit) -> None:
        now = self.clock()
        self._sent_at[:] = [t for t in self._sent_at if t > now - limit.per_seconds]
        if len(self._sent_at) >= limit.max_requests:
            wait = self._sent_at[0] + limit.per_seconds - now
            raise RateLimitError(
                f"rate limited: at most {limit.max_requests} requests per "
                f"{limit.per_seconds} s; retry after {wait:g} s",
                retry_after_s=wait,
            )
        self._sent_at.append(now)

    def _finish(self, sent: _Sent, reply: str | Sequence[ToolCall] | Refusal) -> Completion:
        request = sent.request
        choice = request.tool_choice
        forced = choice != "auto" and choice != "none"
        calls: tuple[ToolCall, ...] = ()
        stop: StopReason
        if isinstance(reply, Refusal):
            text = _text(reply.text, "Refusal.text")
            stop, output_tokens = "refusal", count_tokens(text)
        elif isinstance(reply, str):
            if forced:
                raise ValueError(
                    f"tool_choice is {choice!r}, so the responder must ask for a tool, not reply"
                    " with text"
                )
            reply = str.__str__(reply)
            tokens = tokenize(reply)
            truncated = len(tokens) > request.max_tokens
            text = _truncate(reply, request.max_tokens) if truncated else reply
            stop = "max_tokens" if truncated else "end_turn"
            output_tokens = min(len(tokens), request.max_tokens)
        else:
            calls = tuple(_tool_call(c, "a tool call from the responder") for c in reply)
            known = {t.name for t in request.tools}
            unknown = [c.name for c in calls if c.name not in known]
            if unknown:
                raise ValueError(f"responder called tools that were not offered: {unknown}")
            if choice == "none" and calls:
                raise ValueError('tool_choice is "none", so the responder must not ask for tools')
            if forced and not calls:
                raise ValueError(f"tool_choice is {choice!r}, so the responder must ask for a tool")
            if isinstance(choice, Mapping) and any(c.name != choice["name"] for c in calls):
                raise ValueError(f"tool_choice is {choice!r}, so the responder may call only it")
            text, stop = "", "tool_use"
            output_tokens = sum(count_tokens(json.dumps(dict(c.arguments))) for c in calls)
        reasoning = _REASONING_TOKENS[request.effort] if request.effort else 0
        output_tokens += reasoning
        card = sent.card
        latency = card.base_latency_ms + card.ms_per_output_token * output_tokens if card else 0.0
        return Completion(
            text=text,
            stop_reason=stop,
            usage=Usage(sent.prompt_tokens, output_tokens, sent.cached, reasoning),
            tool_calls=calls,
            model=request.model,
            latency_ms=float(latency),
        )


@dataclass(frozen=True)
class _Sent:
    request: Request
    reply: Reply
    prompt_tokens: int
    cached: int
    card: ModelCard | None


def _check_tool_choice(request: Request) -> None:
    """What a provider rejects with a 400: forcing a tool when none, or not that one, is offered."""
    choice = request.tool_choice
    names = [t.name for t in request.tools]
    if choice == "any" and not names:
        raise InvalidRequestError('tool_choice "any" needs at least one tool')
    if isinstance(choice, Mapping) and choice["name"] not in names:
        raise InvalidRequestError(f"tool_choice names {choice['name']!r}, which is not offered")


def _prefix_tokens(previous: Request, request: Request) -> int:
    """Tokens of the leading blocks `request` shares with `previous`, as a prompt cache reads."""
    if previous.model != request.model or (previous.system, previous.tools) != (
        request.system,
        request.tools,
    ):
        return 0
    total = count_tokens(request.system or "")
    for before, now in zip(previous.messages, request.messages, strict=False):
        if before != now:
            break
        total += _message_tokens(now)
    return total


def _events(completion: Completion, chunk_tokens: int) -> list[StreamEvent]:
    events: list[StreamEvent] = [TextDelta(p) for p in _chunks(completion.text, chunk_tokens)]
    for call in completion.tool_calls:
        events.append(ToolCallStart(call.id, call.name))
        arguments = json.dumps(dict(call.arguments))
        events.extend(ToolCallDelta(call.id, p) for p in _pieces(arguments, call.id))
        events.append(ToolCallEnd(call.id))
    events.append(MessageEnd(completion.stop_reason, completion.usage))
    return events


def _chunks(text: str, size: int) -> list[str]:
    """`text` cut after every `size` tokens; the pieces join back to `text` exactly."""
    cuts = [m.end() for m in re.finditer(r"\w+|[^\w\s]", text)][size - 1 :: size]
    pieces, start = [], 0
    for cut in cuts:
        pieces.append(text[start:cut])
        start = cut
    rest = text[start:]
    if rest and pieces and not rest.strip():
        pieces[-1] += rest
    elif rest:
        pieces.append(rest)
    return pieces


def _pieces(text: str, seed: str) -> list[str]:
    """`text` split at arbitrary, but seeded, character boundaries."""
    rng = random.Random(seed)  # noqa: S311 - deterministic chunking, not security
    pieces, start = [], 0
    while start < len(text):
        end = start + rng.randint(1, 8)
        pieces.append(text[start:end])
        start = end
    return pieces


def _play(events: list[StreamEvent], failure: StreamFailure | None) -> Iterator[StreamEvent]:
    if failure is None:
        yield from events
        return
    yield from events[: min(failure.after_events, len(events) - 1)]
    raise failure.error


_JSON_TYPES = "str, int, float, bool, None, list and dict"


def _serialise(
    messages: Sequence[Message],
    system: str | None,
    max_tokens: int,
    temperature: float,
    tools: Sequence[Tool],
    model: str | None = None,
    response_format: Mapping[str, Any] | None = None,
    tool_choice: ToolChoice = "auto",
    effort: Effort | None = None,
) -> Request:
    """The request as a provider would receive it: rebuilt from plain built-ins only.

    A real client sends JSON, so a `str` subclass arrives as its true characters and its
    overridden methods (`__eq__`, `__contains__`, ...) never reach the model, or the graders
    that assert on what reached it.
    """
    if type(max_tokens) is bool or not isinstance(max_tokens, int):
        raise TypeError(f"max_tokens must be an int, not {type(max_tokens).__name__}")
    if type(temperature) is bool or not isinstance(temperature, int | float):
        raise TypeError(f"temperature must be a number, not {type(temperature).__name__}")
    return Request(
        messages=tuple(_message(m, f"messages[{i}]") for i, m in enumerate(messages)),
        system=None if system is None else _text(system, "system"),
        max_tokens=_json(max_tokens, "max_tokens"),
        temperature=_json(temperature, "temperature"),
        tools=tuple(_tool(t, f"tools[{i}]") for i, t in enumerate(tools)),
        model="" if model is None else _text(model, "model"),
        response_format=(
            None if response_format is None else _object(response_format, "response_format")
        ),
        tool_choice=_tool_choice(tool_choice),
        effort=_effort(effort),
    )


def _tool_choice(value: object) -> ToolChoice:
    if isinstance(value, str):
        choice = str.__str__(value)
        if choice not in ("auto", "any", "none"):
            raise ValueError(
                f"tool_choice must be 'auto', 'any', 'none' or {{'name': ...}}, not {choice!r}"
            )
        return choice  # type: ignore[return-value]
    if isinstance(value, Mapping):
        named = _object(value, "tool_choice")
        if set(named) != {"name"} or type(named["name"]) is not str:
            raise ValueError("a tool_choice dict must be exactly {'name': '<tool name>'}")
        return named
    raise TypeError(f"tool_choice must be a str or a dict, not {type(value).__name__}")


def _effort(value: object) -> Effort | None:
    if value is None:
        return None
    effort = _text(value, "effort")
    if effort not in _REASONING_TOKENS:
        raise ValueError(f"effort must be 'low', 'medium', 'high' or None, not {effort!r}")
    return effort  # type: ignore[return-value]


def _message(message: Message, where: str) -> Message:
    tool_call_id = message.tool_call_id
    return Message(
        role=_text(message.role, f"{where}.role"),  # type: ignore[arg-type]
        content=_text(message.content, f"{where}.content"),
        tool_calls=tuple(
            _tool_call(c, f"{where}.tool_calls[{i}]") for i, c in enumerate(message.tool_calls)
        ),
        tool_call_id=None if tool_call_id is None else _text(tool_call_id, f"{where}.tool_call_id"),
    )


def _tool(tool: Tool, where: str) -> Tool:
    return Tool(
        name=_text(tool.name, f"{where}.name"),
        description=_text(tool.description, f"{where}.description"),
        input_schema=_object(tool.input_schema, f"{where}.input_schema"),
    )


def _tool_call(call: ToolCall, where: str) -> ToolCall:
    return ToolCall(
        id=_text(call.id, f"{where}.id"),
        name=_text(call.name, f"{where}.name"),
        arguments=_object(call.arguments, f"{where}.arguments"),
    )


def _text(value: object, where: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{where} must be a str, not {type(value).__name__}")
    return str.__str__(value)


def _object(value: object, where: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{where} must be a dict, not {type(value).__name__}")
    result: dict[str, Any] = _json(value, where)
    return result


def _json(value: Any, where: str) -> Any:
    """`value` as exact built-in JSON types, read with the base types' own methods so a
    subclass cannot change what is seen. Anything JSON cannot carry is a `TypeError`, as it
    would be when a real SDK serialises the request."""
    if value is None or type(value) is bool:
        return value
    if isinstance(value, str):
        return str.__str__(value)
    if isinstance(value, int):
        return int.__int__(value)
    if isinstance(value, float):
        return float.__float__(value)
    if isinstance(value, Mapping):
        items = dict.items(value) if isinstance(value, dict) else value.items()
        result = {}
        for key, item in items:
            name = _key(key, where)
            result[name] = _json(item, f"{where}[{name!r}]")
        return result
    if isinstance(value, list | tuple):
        elements = list.__iter__(value) if isinstance(value, list) else tuple.__iter__(value)
        return [_json(item, f"{where}[{i}]") for i, item in enumerate(elements)]
    raise TypeError(
        f"{where} is a {type(value).__name__}, which cannot be sent to a model: requests "
        f"travel as JSON, so use only {_JSON_TYPES} (convert it first, for example with str())"
    )


def _key(key: Any, where: str) -> str:
    """A dict key as JSON writes it: strings as they are; numbers, booleans and None as text."""
    if isinstance(key, str):
        return str.__str__(key)
    if key is None or isinstance(key, int | float):
        return json.dumps(_json(key, where))
    raise TypeError(
        f"{where} has a {type(key).__name__} key, which cannot be sent to a model: JSON object "
        "keys must be strings"
    )


def _message_tokens(message: Message) -> int:
    calls = sum(count_tokens(c.name + json.dumps(dict(c.arguments))) for c in message.tool_calls)
    return count_tokens(message.content) + calls


def _check_tool_protocol(messages: Sequence[Message]) -> None:
    """Every tool call must be answered by tool messages immediately after it, and every
    tool message must answer a pending call — the rule real provider APIs enforce."""
    pending: list[str] = []
    for index, message in enumerate(messages):
        if message.role == "tool":
            if message.tool_call_id not in pending:
                raise InvalidRequestError(
                    f"message {index} answers tool call '{message.tool_call_id}', "
                    "which is not awaiting a result"
                )
            pending.remove(message.tool_call_id)
            continue
        if pending:
            raise InvalidRequestError(
                f"message {index} arrived before tool call(s) {pending} were answered"
            )
        pending = [c.id for c in message.tool_calls]
    if pending:
        raise InvalidRequestError(f"tool call(s) {pending} were never answered")


def _truncate(text: str, max_tokens: int) -> str:
    """The prefix of `text` containing exactly `max_tokens` tokens, original spacing kept."""
    matches = list(re.finditer(r"\w+|[^\w\s]", text))
    return text[: matches[max_tokens - 1].end()]


_active: list[ModelClient] = []
_live: list[ModelClient] = []


def _grading() -> bool:
    """True inside the grader, where only the clients the hidden tests configure exist."""
    return bool(os.environ.get("FORGEWAY_GRADING")) or "lattice_grader" in sys.modules


def default_client() -> ModelClient:
    """The model client configured for this run (the fake in the sandbox).

    Outside grading, with no client configured, `FORGEWAY_LIVE=anthropic|openai|
    openai-compatible` builds a metered live client (see `forgeway_kit.live`).
    """
    if _active:
        return _active[-1]
    if os.environ.get("FORGEWAY_LIVE") and not _grading():
        if not _live:
            from forgeway_kit.live import client_from_env  # network code, imported only here

            _live.append(client_from_env())
        return _live[0]
    raise RuntimeError(
        "no model client is configured; graders set one with use_client(), and outside grading "
        "FORGEWAY_LIVE=anthropic|openai|openai-compatible selects a live one"
    )


@contextmanager
def use_client(client: ModelClient) -> Iterator[ModelClient]:
    """Make `client` the default for the duration of the block."""
    _active.append(client)
    try:
        yield client
    finally:
        _active.pop()
