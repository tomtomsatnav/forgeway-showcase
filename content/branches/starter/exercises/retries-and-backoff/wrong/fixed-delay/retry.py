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
    for attempt in range(1, max_attempts + 1):
        try:
            return client.complete(messages)
        except (RateLimitError, ServerError):
            if attempt == max_attempts:
                raise
            sleep(base_delay)
    raise ValueError("max_attempts must be at least 1")
