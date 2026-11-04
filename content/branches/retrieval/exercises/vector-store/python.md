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

### `field(default_factory=list)` gives each instance its own list

A dataclass refuses a bare `= []` as a default, because every instance would share that one list. The factory makes a new one each time. It works for `dict` and `set` too.

```python
from dataclasses import dataclass, field


@dataclass
class Shelf:
    books: list[str] = field(default_factory=list)
```

### A `typing.Protocol` describes what an object can do

Any object with the right methods counts, with no inheritance needed. This is called structural typing, and nothing checks it while the code runs: the type checker does.

```python
from typing import Protocol


class Greeter(Protocol):
    def greet(self, name: str) -> str: ...


class Polite:  # a Greeter, without saying so
    def greet(self, name: str) -> str:
        return f"Good day, {name}"
```

### `sorted(items, key=...)` sorts by whatever the key returns

A `lambda` is a small unnamed function, handy here. A tuple key sorts by its first item, then its second, and negating a number puts the largest first. Python's sort is stable: items with equal keys keep their order.

```python
scores = [("fig", 2), ("pear", 5), ("kiwi", 2)]
sorted(scores, key=lambda item: (-item[1], item[0]))
# [('pear', 5), ('fig', 2), ('kiwi', 2)]
```

### A list comprehension builds a list in one expression

Read it as "this value, for each item, if this holds". The `if` part is optional.

```python
prices = [3, 8, 5]
cheap_doubled = [price * 2 for price in prices if price < 6]  # [6, 10]
```
