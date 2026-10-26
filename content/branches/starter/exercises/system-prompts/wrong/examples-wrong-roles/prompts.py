from collections.abc import Sequence

from forgeway_kit import Message, ModelClient


def answer(
    client: ModelClient,
    system_prompt: str,
    question: str,
    examples: Sequence[tuple[str, str]] = (),
) -> str:
    messages = []
    for example_input, example_output in examples:
        messages.append(Message(role="user", content=f"{example_input} -> {example_output}"))
    messages.append(Message(role="user", content=question))
    return client.complete(messages, system=system_prompt).text
