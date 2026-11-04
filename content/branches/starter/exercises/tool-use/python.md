### `f(**options)` turns a dict into keyword arguments

Each key becomes an argument name, which lets you call a function when the arguments arrive as data. A wrong name raises `TypeError`.

```python
def order(item: str, count: int = 1) -> str:
    return f"{count} x {item}"


order(**{"item": "fig", "count": 2})  # '2 x fig'
```

### `except Exception` catches almost everything

Use it only at a boundary, such as around code you do not control, where any failure should be turned into a result rather than a crash. It leaves `KeyboardInterrupt` alone, and `as err` gives you the error, with `str(err)` as its message.

```python
def safely(step) -> str:
    try:
        return step()
    except Exception as err:
        return f"failed: {err}"
```

### `Callable[[str], int]` is the type of a function

The list holds the argument types and the last item is the return type. Functions are ordinary values in Python, so you can take one as an argument and call it. Import it from `collections.abc`.

```python
from collections.abc import Callable


def apply_twice(step: Callable[[int], int], start: int) -> int:
    return step(step(start))


apply_twice(lambda n: n + 3, 1)  # 7
```
