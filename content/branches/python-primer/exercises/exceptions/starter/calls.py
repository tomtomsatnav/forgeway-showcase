from typing import Any


def parse_count(text: str) -> int | None:
    """`int(text)`, or None if `text` is not a whole number."""
    raise NotImplementedError


class GaveUpError(Exception):
    """Raised when every attempt timed out. Keep the number in an `attempts` attribute."""


def call_with_retries(client: Any, attempts: int = 3) -> Any:
    """Call `client.fetch()`, retrying a TimeoutError, up to `attempts` calls in all."""
    raise NotImplementedError


def run_with_cleanup(task: Any, cleanup: Any) -> Any:
    """Call `task.run()`, then `cleanup.close()` whether it returned or raised."""
    raise NotImplementedError
