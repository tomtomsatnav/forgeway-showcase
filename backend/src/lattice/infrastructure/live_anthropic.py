"""The platform's model provider for in-app live runs: the Anthropic Messages API (ADR 0012).

Only the worker holds the key. A learner's call arrives as a validated `LiveCall` (the toolkit's
arguments); this module builds the request body itself, field by field, with the platform's
model and the clamped `max_tokens`, so nothing the learner sends reaches the provider unless it
is named here. It uses the standard library only, like `forgeway_kit.live`, and its base URL is
configurable so tests can point it at a stub server on the host.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from lattice.domain.live import CallUsage, LiveCall, ProviderError, ProviderReply

ANTHROPIC_VERSION = "2026-10-21"
TIMEOUT_S = 60.0

_STOPS = {
    "end_turn": "end_turn",
    "stop_sequence": "end_turn",
    "pause_turn": "end_turn",
    "tool_use": "tool_use",
    "max_tokens": "max_tokens",
    "model_context_window_exceeded": "max_tokens",
    "refusal": "refusal",
}


def request_body(call: LiveCall, *, model: str, max_tokens: int) -> dict[str, Any]:
    """The Messages API body for `call`, on `model`, with at most `max_tokens` of output."""
    messages: list[dict[str, Any]] = []
    for m in call.messages:
        if m.role == "tool":
            result = {"type": "tool_result", "tool_use_id": m.tool_call_id, "content": m.content}
            last = messages[-1] if messages else None
            if last and last["role"] == "user" and isinstance(last["content"], list):
                last["content"].append(result)  # parallel results go back in one message
            else:
                messages.append({"role": "user", "content": [result]})
        elif m.role == "assistant" and m.tool_calls:
            text = [{"type": "text", "text": m.content}] if m.content else []
            uses = [
                {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                for c in m.tool_calls
            ]
            messages.append({"role": "assistant", "content": text + uses})
        else:
            messages.append({"role": m.role, "content": m.content})
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": min(call.max_tokens, max_tokens),
        "messages": messages,
    }
    if call.system:
        body["system"] = call.system
    if call.tools:
        body["tools"] = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in call.tools
        ]
        choice = call.tool_choice
        body["tool_choice"] = (
            {"type": "tool", "name": choice["name"]}
            if isinstance(choice, dict)
            else {"type": choice}
        )
    output_config: dict[str, Any] = {}
    if call.effort:
        output_config["effort"] = call.effort
    if call.response_format is not None:
        output_config["format"] = {"type": "json_schema", "schema": call.response_format}
    if output_config:
        body["output_config"] = output_config
    return body


class AnthropicProvider:
    """POSTs to /v1/messages with the platform key. The key never leaves this object."""

    def __init__(self, api_key: str, base_url: str, timeout_s: float = TIMEOUT_S) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

        def key() -> str:
            return api_key

        self._key = key  # a closure, so vars(provider) and repr never show it

    def __repr__(self) -> str:
        return f"AnthropicProvider(base_url={self._base_url!r})"

    def complete(
        self, call: LiveCall, *, model: str, max_tokens: int, timeout_s: float | None = None
    ) -> ProviderReply:
        body = request_body(call, model=model, max_tokens=max_tokens)
        request = urllib.request.Request(  # noqa: S310 - the configured provider URL
            self._base_url + "/v1/messages",
            data=json.dumps(body).encode(),
            headers={
                "content-type": "application/json",
                "x-api-key": self._key(),
                "anthropic-version": ANTHROPIC_VERSION,
            },
            method="POST",
        )
        started = time.monotonic()
        limit = self._timeout_s if timeout_s is None else min(self._timeout_s, timeout_s)
        try:
            with urllib.request.urlopen(request, timeout=limit) as response:  # noqa: S310
                payload = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            error = _http_error(exc.code, exc.headers.get("retry-after"), exc.read())
            error.message = error.message.replace(self._key(), "[redacted]")
            raise error from None
        except (urllib.error.URLError, OSError, ValueError):
            raise ProviderError("server", "the model provider could not be reached") from None
        latency_ms = int((time.monotonic() - started) * 1000)
        return parse(payload, latency_ms, fallback_model=str(body.get("model", "")))


def parse(payload: dict[str, Any], latency_ms: int, *, fallback_model: str) -> ProviderReply:
    """A Messages API response as the toolkit's Completion (JSON) and its usage."""
    content = [b for b in payload.get("content") or [] if isinstance(b, dict)]
    raw = payload.get("usage") or {}
    cached = int(raw.get("cache_read_input_tokens") or 0)
    written = int(raw.get("cache_creation_input_tokens") or 0)
    usage = CallUsage(
        input_tokens=int(raw.get("input_tokens") or 0) + cached + written,
        output_tokens=int(raw.get("output_tokens") or 0),
        cache_read_tokens=cached,
        cache_write_tokens=written,
    )
    model = str(payload.get("model") or fallback_model)
    completion = {
        "text": "".join(str(b.get("text", "")) for b in content if b.get("type") == "text"),
        "stop_reason": _STOPS.get(str(payload.get("stop_reason")), "end_turn"),
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_input_tokens": cached,
            "reasoning_tokens": 0,
        },
        "tool_calls": [
            {"id": str(b.get("id")), "name": str(b.get("name")), "arguments": b.get("input") or {}}
            for b in content
            if b.get("type") == "tool_use"
        ],
        "model": model,
        "latency_ms": float(latency_ms),
    }
    return ProviderReply(completion, usage, model, latency_ms)


def _http_error(status: int, retry_after: str | None, raw: bytes) -> ProviderError:
    try:
        detail = str(json.loads(raw)["error"]["message"])[:500]
    except (ValueError, KeyError, TypeError):
        detail = "no detail"
    message = f"the model provider answered {status}: {detail}"
    if status == 429:
        try:
            wait = float(retry_after) if retry_after else 1.0
        except ValueError:
            wait = 1.0
        return ProviderError("rate_limit", message, wait)
    if status >= 500:
        return ProviderError("server", message)
    return ProviderError("invalid", message)
