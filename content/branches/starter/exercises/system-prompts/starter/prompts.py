from collections.abc import Sequence

from forgeway_kit import ModelClient


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
    raise NotImplementedError("send the system prompt, the examples and the question")
