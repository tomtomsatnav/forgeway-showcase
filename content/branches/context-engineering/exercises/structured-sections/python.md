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

### `str.replace` returns a new string

Strings never change in place, so you keep the result. It replaces every occurrence, and matches exact text only, case included.

```python
text = "red, red wine"
text.replace("red", "blue")  # 'blue, blue wine'
text  # still 'red, red wine'
```
