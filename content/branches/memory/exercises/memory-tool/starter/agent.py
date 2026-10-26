from collections.abc import MutableMapping

from forgeway_kit import ModelClient

SYSTEM = "You are a helpful assistant with a notebook."  # improve this: say when to use it


def run_with_memory(
    client: ModelClient,
    memory: MutableMapping[str, str],
    user_message: str,
    max_steps: int = 6,
) -> str:
    """A tool loop in which the model reads and writes `memory` through `remember` and `recall`.

    Returns the model's final text. Raises RuntimeError mentioning max_steps if it never finishes.
    """
    raise NotImplementedError("define the two tools, run the loop, answer every call")
