from collections.abc import Callable, MutableMapping

from forgeway_kit import ModelClient, Tool


def run_durable(
    client: ModelClient,
    run_id: str,
    task: str,
    tools: list[Tool],
    registry: dict[str, Callable[..., object]],
    store: MutableMapping[str, str],
) -> str:
    """A tool loop that can be killed at any point and resumed from `store[run_id]`.

    Save the conversation as JSON text after the task, each model reply, each tool result and the
    final answer. On resume, run only the calls with no result yet, and never repeat a call.
    A run that already finished returns its answer without calling the model.
    """
    raise NotImplementedError("save after every step; on resume, load and run only what is left")
