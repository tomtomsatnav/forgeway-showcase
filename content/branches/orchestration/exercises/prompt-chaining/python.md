### `Callable[[str], int]` is the type of a function

The list holds the argument types and the last item is the return type. Functions are ordinary values in Python, so you can take one as an argument and call it. Import it from `collections.abc`.

```python
from collections.abc import Callable


def apply_twice(step: Callable[[int], int], start: int) -> int:
    return step(step(start))


apply_twice(lambda n: n + 3, 1)  # 7
```

### `@dataclass(frozen=True)` makes an immutable record

You list annotated fields and Python writes the constructor and `==` for you. Assigning to a field afterwards raises `FrozenInstanceError`, and the record can be used as a dict key.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    x: int
    y: int = 0  # a default


Point(3)  # Point(x=3, y=0)
```

### Your own exception is a class that inherits from `Exception`

The class can be empty, or carry extra attributes for whoever catches it. Callers can then catch your error by name and leave other errors alone.

```python
class OutOfStock(Exception):
    def __init__(self, item: str) -> None:
        super().__init__(f"No {item} left")
        self.item = item
```

### `str | None` means "a string, or nothing"

The `|` builds a union type, and `None` is Python's "no value". Check for it with `is None`, because an empty string is also false in an `if`.

```python
def initial(name: str | None) -> str:
    if name is None:
        return "?"
    return name[0]
```
