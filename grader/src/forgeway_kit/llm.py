"""A provider-neutral chat-completion interface and a deterministic fake implementation."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from forgeway_kit.errors import InvalidRequestError
from forgeway_kit.tokens import count_tokens, tokenize

Role = Literal["user", "assistant", "tool"]
StopReason = Literal["end_turn", "max_tokens", "tool_use"]


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
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class Completion:
    text: str
    stop_reason: StopReason
    usage: Usage
    tool_calls: tuple[ToolCall, ...] = ()


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


class ModelClient(Protocol):
    """Anything that can complete a conversation."""

    def complete(
        self,
        messages: Sequence[Message],
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.0,
        tools: Sequence[Tool] = (),
    ) -> Completion: ...


Responder = Callable[[Request], "str | Sequence[ToolCall]"]


@dataclass
class FakeModel:
    """A deterministic stand-in for a real model.

    Responses come from `responder`, a function of the request that returns reply text, or a
    list of `ToolCall`s to ask for tools; it may also raise a `ModelError` to simulate
    failures. Conversations are validated as a real API would: tool calls must be answered,
    in order, before the conversation continues. Every request is recorded in `requests`,
    including ones that fail. Usage is measured with `forgeway_kit.count_tokens`. Requests
    whose input exceeds `context_window` tokens are rejected, as a real API would.

    Like a real client, it serialises each request before sending it: `requests` and the
    responder see a copy rebuilt from plain built-ins, never the caller's own objects, and a
    value JSON cannot carry raises `TypeError` before anything is sent.
    """

    responder: Responder = field(default=lambda request: "OK")
    context_window: int = 8000
    requests: list[Request] = field(default_factory=list)

    def complete(
        self,
        messages: Sequence[Message],
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.0,
        tools: Sequence[Tool] = (),
    ) -> Completion:
        request = _serialise(messages, system, max_tokens, temperature, tools)
        if not request.messages:
            raise ValueError("messages must not be empty")
        if request.messages[-1].role not in ("user", "tool"):
            raise ValueError("the last message must come from the user or be a tool result")
        if request.max_tokens < 1:
            raise ValueError("max_tokens must be at least 1")
        self.requests.append(request)
        _check_tool_protocol(request.messages)
        prompt_tokens = sum(_message_tokens(m) for m in request.messages) + count_tokens(
            request.system or ""
        )
        if prompt_tokens > self.context_window:
            raise InvalidRequestError(
                f"prompt is {prompt_tokens} tokens; the context window is {self.context_window}"
            )
        reply = self.responder(request)
        if not isinstance(reply, str):
            calls = tuple(_tool_call(c, "a tool call from the responder") for c in reply)
            known = {t.name for t in request.tools}
            unknown = [c.name for c in calls if c.name not in known]
            if unknown:
                raise ValueError(f"responder called tools that were not offered: {unknown}")
            output_tokens = sum(count_tokens(json.dumps(dict(c.arguments))) for c in calls)
            return Completion(
                text="",
                stop_reason="tool_use",
                usage=Usage(prompt_tokens, output_tokens),
                tool_calls=calls,
            )
        reply = str.__str__(reply)
        tokens = tokenize(reply)
        truncated = len(tokens) > request.max_tokens
        text = _truncate(reply, request.max_tokens) if truncated else reply
        return Completion(
            text=text,
            stop_reason="max_tokens" if truncated else "end_turn",
            usage=Usage(
                input_tokens=prompt_tokens, output_tokens=min(len(tokens), request.max_tokens)
            ),
        )


_JSON_TYPES = "str, int, float, bool, None, list and dict"


def _serialise(
    messages: Sequence[Message],
    system: str | None,
    max_tokens: int,
    temperature: float,
    tools: Sequence[Tool],
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
    )


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


def default_client() -> ModelClient:
    """The model client configured for this run (the fake in the sandbox)."""
    if not _active:
        raise RuntimeError("no model client is configured; graders set one with use_client()")
    return _active[-1]


@contextmanager
def use_client(client: ModelClient) -> Iterator[ModelClient]:
    """Make `client` the default for the duration of the block."""
    _active.append(client)
    try:
        yield client
    finally:
        _active.pop()
