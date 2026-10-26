from collections.abc import Sequence

from forgeway_kit import Message, ModelClient


def answer(
    client: ModelClient,
    system_prompt: str,
    question: str,
    examples: Sequence[tuple[str, str]] = (),
) -> str:
    """Ask `question` under `system_prompt`, preceded by few-shot `examples`.

    Each example is an (input, output) pair, sent as a user message then an assistant
    message. Returns the reply text.
    """
    messages: list[Message] = []
    for example_input, example_output in examples:
        messages.append(Message(role="user", content=example_input))
        messages.append(Message(role="assistant", content=example_output))
    messages.append(Message(role="user", content=question))
    return client.complete(messages, system=system_prompt).text
