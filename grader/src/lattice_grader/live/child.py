"""The learner's side of an in-app live run (ADR 0012). Never imported: its source is run.

The harness hands this file's source to a fresh interpreter (`-s -P -c`), started as the
learner's user (10002) where the launcher serves the sandbox, and calls `main(config)`. It
imports only the standard library and `forgeway_kit`, never `lattice_grader`, which that user
cannot read.

It takes the pipes it was started on (stdin and stdout) as its private channel to the harness,
points stdout and stderr at the two output files the harness made, and runs the exercise's
`live.py` with `ProxyClient` made the default client by `use_client`, which always wins over the
environment. `FORGEWAY_GRADING` stays set, so `forgeway_kit`'s live clients still refuse to be
built here, and there is no key anywhere in this process to send.

**Wire format.** One JSON object per line. The child sends ``{"id": n, "request": {...}}``, the
toolkit's arguments as `forgeway_kit`'s `Request` holds them; the reply is ``{"id": n,
"completion": {...}}`` or ``{"id": n, "error": {"kind": ..., "message": ...}}``. Calls are one at
a time. `stream()` is the completed reply played back as events, as the proxy does not stream.
"""

from __future__ import annotations

import dataclasses
import json
import os
import runpy
import sys
import threading
from collections.abc import Iterator, Mapping, Sequence
from typing import IO, Any

from forgeway_kit.errors import InvalidRequestError, RateLimitError, ServerError
from forgeway_kit.llm import (
    Completion,
    Effort,
    Message,
    StreamEvent,
    Tool,
    ToolCall,
    ToolChoice,
    Usage,
    _events,
    _serialise,
    use_client,
)

STREAM_CHUNK_TOKENS = 8


class ProxyClient:
    """A model client whose every call goes through the live channel to Forgeway's proxy.

    It holds no key and names no provider: the proxy, outside the sandbox, chooses the model,
    adds the key, and decides whether the call is made at all.
    """

    model = "forgeway-live"

    def __init__(self, reader: IO[bytes], writer: IO[bytes]) -> None:
        self._reader = reader
        self._writer = writer
        self._lock = threading.Lock()
        self._next = 0

    def __repr__(self) -> str:
        return "ProxyClient()"

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
        request = _serialise(
            messages, system, max_tokens, temperature, tools, model, response_format,
            tool_choice, effort,
        )  # fmt: skip
        body = dataclasses.asdict(request)
        body.pop("sample", None)
        return _completion(self._call(body))

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
        completion = self.complete(
            messages, system=system, max_tokens=max_tokens, temperature=temperature, tools=tools,
            model=model, response_format=response_format, tool_choice=tool_choice, effort=effort,
        )  # fmt: skip
        return iter(_events(completion, STREAM_CHUNK_TOKENS))

    def _call(self, request: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._next += 1
            call_id = self._next
            line = json.dumps({"id": call_id, "request": request}, separators=(",", ":"))
            self._writer.write(line.encode() + b"\n")
            self._writer.flush()
            raw = self._reader.readline()
        if not raw:
            raise ServerError("the live channel closed: this run has ended")
        reply: dict[str, Any] = json.loads(raw)
        if reply.get("id") != call_id:
            raise ServerError("the live channel answered out of turn")
        if "error" in reply:
            error = reply["error"]
            kind, message = str(error.get("kind", "")), str(error.get("message", ""))
            if kind == "rate_limit":
                raise RateLimitError(message, retry_after_s=float(error.get("retry_after_s", 1.0)))
            if kind == "server":
                raise ServerError(message)
            raise InvalidRequestError(message)  # "invalid" and "limit": retrying will not help
        completion: dict[str, Any] = reply["completion"]
        return completion


def _completion(data: Mapping[str, Any]) -> Completion:
    usage = data.get("usage") or {}
    return Completion(
        text=str(data.get("text", "")),
        stop_reason=data.get("stop_reason", "end_turn"),
        usage=Usage(
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            cache_read_input_tokens=int(usage.get("cache_read_input_tokens", 0)),
            reasoning_tokens=int(usage.get("reasoning_tokens", 0)),
        ),
        tool_calls=tuple(
            ToolCall(str(c["id"]), str(c["name"]), dict(c.get("arguments") or {}))
            for c in data.get("tool_calls") or []
        ),
        model=str(data.get("model", "")),
        latency_ms=float(data.get("latency_ms", 0.0)),
    )


def main(config: Mapping[str, str]) -> None:
    # The channel moves to private descriptors before any learner code runs, so `print` and
    # anything written to fd 1 or 2 lands in the output files, never on the channel.
    reader_fd, writer_fd = os.dup(0), os.dup(1)
    null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null, 0)
    os.close(null)
    for target, path in ((1, config["stdout"]), (2, config["stderr"])):
        fd = os.open(path, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
        os.dup2(fd, target)
        os.close(fd)
    client = ProxyClient(os.fdopen(reader_fd, "rb"), os.fdopen(writer_fd, "wb"))
    sys.path.insert(0, config["root"])
    sys.argv = [config["script"]]
    with use_client(client):
        runpy.run_path(config["script"], run_name="__main__")
