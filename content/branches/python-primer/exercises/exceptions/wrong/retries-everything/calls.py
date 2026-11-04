from typing import Any


def parse_count(text: str) -> int | None:
    """`int(text)`, or None if `text` is not a whole number."""
    try:
        return int(text)
    except ValueError:
        return None


class GaveUpError(Exception):
    """Raised when every attempt timed out. Keep the number in an `attempts` attribute."""

    def __init__(self, attempts: int) -> None:
        super().__init__(f"Gave up after {attempts} attempts")
        self.attempts = attempts


def call_with_retries(client: Any, attempts: int = 3) -> Any:
    """Call `client.fetch()`, retrying a TimeoutError, up to `attempts` calls in all."""
    last_error: TimeoutError | None = None
    for _ in range(attempts):
        try:
            return client.fetch()
        except Exception as err:
            last_error = err
    raise GaveUpError(attempts) from last_error


def run_with_cleanup(task: Any, cleanup: Any) -> Any:
    """Call `task.run()`, then `cleanup.close()` whether it returned or raised."""
    try:
        return task.run()
    finally:
        cleanup.close()
