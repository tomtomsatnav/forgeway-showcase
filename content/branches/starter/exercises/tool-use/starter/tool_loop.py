from collections.abc import Callable

from forgeway_kit import ModelClient, Tool


def run_with_tools(
    client: ModelClient,
    question: str,
    tools: list[Tool],
    registry: dict[str, Callable[..., object]],
    max_steps: int = 5,
) -> str:
    """Let the model call `tools` until it answers; return its final text.

    Each tool call runs `registry[call.name](**call.arguments)` and its result goes back as a
    `tool` message. Errors become `error: <message>` results. Makes at most `max_steps` model
    calls, then raises RuntimeError mentioning `max_steps`.
    """
    raise NotImplementedError("loop: ask, run requested tools, send results back")
