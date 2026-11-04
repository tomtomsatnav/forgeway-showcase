import json
from collections.abc import Callable, Iterable, Sequence

from forgeway_kit import (
    Completion,
    Message,
    MessageEnd,
    ModelError,
    RateLimitError,
    ServerError,
    StreamingModelClient,
    TextDelta,
    Tool,
    ToolCall,
    ToolCallDelta,
    ToolCallStart,
)


class StreamInterrupted(Exception):
    """The stream broke after some of the reply had already been shown to the user."""

    def __init__(self, partial_text: str, error: Exception) -> None:
        super().__init__(f"the stream broke after {len(partial_text)} characters: {error}")
        self.partial_text = partial_text  # exactly the text passed to on_text
        self.error = error  # the error the stream raised


def _assemble(events: Iterable, on_text: Callable[[str], None], shown: list[str]) -> Completion:
    names: dict[str, str] = {}
    fragments: dict[str, list[str]] = {}
    for event in events:
        if isinstance(event, TextDelta):
            shown.append(event.text)
            on_text(event.text)
        elif isinstance(event, ToolCallStart):
            names[event.id] = event.name
            fragments[event.id] = []
        elif isinstance(event, ToolCallDelta):
            fragments[list(fragments)[-1]].append(event.partial_json)  # the call in progress
        elif isinstance(event, MessageEnd):
            calls = tuple(
                ToolCall(call_id, name, json.loads("".join(fragments[call_id]) or "{}"))
                for call_id, name in names.items()  # dicts keep the order the calls started in
            )
            return Completion("".join(shown), event.stop_reason, event.usage, calls)
    raise ServerError("the stream ended without a MessageEnd")


def stream_completion(
    client: StreamingModelClient,
    messages: Sequence[Message],
    on_text: Callable[[str], None],
    *,
    tools: Sequence[Tool] = (),
) -> Completion:
    """Stream a reply, showing its text through `on_text` as it arrives.

    Returns the whole reply as a `Completion`. Starts again once if the stream breaks before
    any text was shown; raises `StreamInterrupted` if it breaks after.
    """
    for attempt in (1, 2):
        shown: list[str] = []  # fresh for each attempt: nothing carries over from a broken one
        try:
            return _assemble(client.stream(messages, tools=tools), on_text, shown)
        except ModelError as error:
            if shown:
                raise StreamInterrupted("".join(shown), error) from error
            if attempt == 2 or not isinstance(error, ServerError | RateLimitError):
                raise
    raise AssertionError("unreachable")
