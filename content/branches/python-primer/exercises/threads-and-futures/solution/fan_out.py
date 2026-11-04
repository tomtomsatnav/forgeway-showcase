from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any


def fetch_all(client: Any, queries: Sequence[str], max_workers: int = 4) -> list[Any]:
    """Call `client.fetch` for every query at once; results in the order of `queries`."""
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(client.fetch, queries))


def fetch_each(
    client: Any, queries: Sequence[str], max_workers: int = 4
) -> list[tuple[Any, str | None]]:
    """Like `fetch_all`, but each query gives `(result, None)` or `(None, str(error))`."""
    results: list[tuple[Any, str | None]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(client.fetch, query) for query in queries]
        for future in futures:
            try:
                results.append((future.result(), None))
            except Exception as err:
                results.append((None, str(err)))
    return results
