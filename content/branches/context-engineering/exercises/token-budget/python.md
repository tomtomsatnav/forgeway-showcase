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

### `re.finditer` gives you each match as an object

Use it when you need more than the text, such as where a match sits, from `.start()` and `.end()`.

```python
import re

[m.start() for m in re.finditer(r"fig", "fig and fig")]  # [0, 8]
```

### `sorted(items, key=...)` sorts by whatever the key returns

A `lambda` is a small unnamed function, handy here. A tuple key sorts by its first item, then its second, and negating a number puts the largest first. Python's sort is stable: items with equal keys keep their order.

```python
scores = [("fig", 2), ("pear", 5), ("kiwi", 2)]
sorted(scores, key=lambda item: (-item[1], item[0]))
# [('pear', 5), ('fig', 2), ('kiwi', 2)]
```

### A generator expression feeds a function one value at a time

It is a comprehension in round brackets, with no list built on the way. When it is the only argument, the function's own brackets are enough.

```python
total_letters = sum(len(word) for word in ["fig", "pear"])  # 7
", ".join(word.upper() for word in ["fig", "pear"])  # 'FIG, PEAR'
```
