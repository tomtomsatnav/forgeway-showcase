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

### The `re` module finds patterns in text

`re.findall` returns every match and `re.search` returns the first as a match object, or `None`. Write patterns as raw strings (`r"..."`), so a backslash reaches `re` unchanged. `\d` is a digit, `\w` a word character and `\b` the edge of a word.

```python
import re

re.findall(r"\d+", "3 figs, 12 pears")  # ['3', '12']
re.search(r"\d+", "no numbers")  # None
```

### `Callable[[str], int]` is the type of a function

The list holds the argument types and the last item is the return type. Functions are ordinary values in Python, so you can take one as an argument and call it. Import it from `collections.abc`.

```python
from collections.abc import Callable


def apply_twice(step: Callable[[int], int], start: int) -> int:
    return step(step(start))


apply_twice(lambda n: n + 3, 1)  # 7
```

### `sorted(items, key=...)` sorts by whatever the key returns

A `lambda` is a small unnamed function, handy here. A tuple key sorts by its first item, then its second, and negating a number puts the largest first. Python's sort is stable: items with equal keys keep their order.

```python
scores = [("fig", 2), ("pear", 5), ("kiwi", 2)]
sorted(scores, key=lambda item: (-item[1], item[0]))
# [('pear', 5), ('fig', 2), ('kiwi', 2)]
```
