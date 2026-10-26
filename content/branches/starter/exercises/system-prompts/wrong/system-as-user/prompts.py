from collections.abc import Sequence

from forgeway_kit import Message, ModelClient


def answer(
    client: ModelClient,
    system_prompt: str,
    question: str,
    examples: Sequence[tuple[str, str]] = (),
) -> str:
    messages = [Message(role="user", content=system_prompt)]
    for example_input, example_output in examples:
        messages.append(Message(role="user", content=example_input))
        messages.append(Message(role="assistant", content=example_output))
    messages.append(Message(role="user", content=question))
    return client.complete(messages).text
