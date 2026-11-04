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
    while True:
        completion = client.complete(messages, tools=tools)
        if completion.stop_reason != "tool_use":
            return completion.text
        messages.append(
            Message(role="assistant", content=completion.text, tool_calls=completion.tool_calls)
        )
        for call in completion.tool_calls:
            result = _run(registry, call.name, dict(call.arguments))
            messages.append(Message(role="tool", content=result, tool_call_id=call.id))
