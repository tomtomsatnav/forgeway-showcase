import random
import time
from collections.abc import Callable, Sequence

from forgeway_kit import Completion, Message, ModelClient


def complete_with_retries(
    client: ModelClient,
    messages: Sequence[Message],
    *,
    max_attempts: int = 4,
    base_delay: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    rand: Callable[[], float] = random.random,
) -> Completion:
    """Call the model, retrying rate-limit and server errors with exponential backoff.

    Makes at most `max_attempts` calls. Before retry n (counting from 1) the code calls
    `sleep(max(base_delay * 2 ** (n - 1), retry_after) + rand() * base_delay)`, where
    `retry_after` is the error's `retry_after_s` for a RateLimitError and 0 otherwise. The last
    error is re-raised if all attempts fail; other errors are raised immediately.
    """
    raise NotImplementedError("loop over attempts, back off between transient failures")
