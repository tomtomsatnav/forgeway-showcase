import random
import time
from collections.abc import Callable, Sequence

from forgeway_kit import Completion, Message, ModelClient, RateLimitError, ServerError


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
    for attempt in range(1, max_attempts + 1):
        try:
            return client.complete(messages)
        except (RateLimitError, ServerError):
            if attempt == max_attempts:
                raise
            retry_after = 0.0
            backoff = base_delay * 2 ** (attempt - 1)
            sleep(max(backoff, retry_after) + rand() * base_delay)
    raise ValueError("max_attempts must be at least 1")
