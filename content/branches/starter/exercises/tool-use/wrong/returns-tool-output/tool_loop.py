from collections.abc import Callable

from forgeway_kit import Message, ModelClient, Tool


def _run(registry: dict[str, Callable[..., object]], name: str, arguments: dict) -> str:
    try:
        return str(registry[name](**arguments))
    except KeyError as error:
        if error.args == (name,):
            return f"error: unknown tool {name!r}"
        return f"error: {error}"
    except Exception as error:
        return f"error: {error}"


def run_with_tools(
    client: ModelClient,
    question: str,
    tools: list[Tool],
    registry: dict[str, Callable[..., object]],
    max_steps: int = 5,
) -> str:
    messages = [Message(role="user", content=question)]
    for _ in range(max_steps):
        completion = client.complete(messages, tools=tools)
        if completion.stop_reason != "tool_use":
            return completion.text
        results = [_run(registry, c.name, dict(c.arguments)) for c in completion.tool_calls]
        return "\n".join(results)
    raise RuntimeError(f"the model was still asking for tools after max_steps={max_steps} steps")
