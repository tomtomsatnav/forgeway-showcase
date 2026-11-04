import random
import time
from collections.abc import Callable, Sequence

from forgeway_kit import Completion, Message, ModelClient, ModelError


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
        except ModelError:
            if attempt == max_attempts:
                raise
            sleep(base_delay * 2 ** (attempt - 1))
    raise ValueError("max_attempts must be at least 1")
