# Exceptions

A model call can time out, be rate limited or return nonsense, so a lot of the code in this
course decides which errors to handle and which to let through. Python's tools for that are
compact:

```python
class OutOfStockError(Exception):
    """Your own error: a class that inherits from Exception."""

    def __init__(self, item: str) -> None:
        super().__init__(f"No {item} left")
        self.item = item


try:
    price = int(raw_price)
except ValueError as err:  # only this type; anything else carries on up
    raise OutOfStockError("tea") from err  # `from` records what caused it
finally:
    till.close()  # runs whether or not anything was raised
```

Catch the narrowest type you can. `except Exception` would also swallow your own bugs.

## Your task

Implement these in `calls.py`:

- `parse_count(text)` returns `int(text)`, or `None` if `text` is not a whole number.
- `GaveUpError`, an exception class. `GaveUpError(attempts)` keeps the number in an `attempts`
  attribute.
- `call_with_retries(client, attempts=3)` calls `client.fetch()`, with no arguments, and returns
  what it returns.
  - If `fetch` raises `TimeoutError`, try again, up to `attempts` calls in all. Do not sleep
    between them.
  - If every call times out, raise `GaveUpError(attempts)` with the last `TimeoutError` as its
    cause (`raise ... from ...`).
  - If `fetch` raises anything else, let it through at once, with no retry.
- `run_with_cleanup(task, cleanup)` calls `task.run()` and returns what it returns. It must call
  `cleanup.close()` once afterwards, whether `run` returned or raised, and an error from `run`
  must still reach the caller.
