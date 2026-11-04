from collections.abc import Sequence
from typing import Any


def fetch_all(client: Any, queries: Sequence[str], max_workers: int = 4) -> list[Any]:
    """Call `client.fetch` for every query at once; results in the order of `queries`."""
    raise NotImplementedError


def fetch_each(
    client: Any, queries: Sequence[str], max_workers: int = 4
) -> list[tuple[Any, str | None]]:
    """Like `fetch_all`, but each query gives `(result, None)` or `(None, str(error))`."""
    raise NotImplementedError
