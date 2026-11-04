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

### `dataclasses.replace` copies a record with some fields changed

The original stays as it was, which is how you "change" a frozen record.

```python
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Point:
    x: int
    y: int


replace(Point(1, 2), y=5)  # Point(x=1, y=5)
```

### `str.casefold` is the right way to ignore case

It is a stronger `lower()` meant for comparing text: German `ß` folds to `ss`, for example.

```python
"Straße".casefold() == "STRASSE".casefold()  # True
```

### `dict.setdefault(key, default)` creates an entry the first time

It returns what is stored under the key, adding the default if there was nothing. That lets you build groups without checking first.

```python
groups: dict[str, list[str]] = {}
for word in ["fig", "fir", "pear"]:
    groups.setdefault(word[0], []).append(word)
# {'f': ['fig', 'fir'], 'p': ['pear']}
```

### `sorted(items, key=...)` sorts by whatever the key returns

A `lambda` is a small unnamed function, handy here. A tuple key sorts by its first item, then its second, and negating a number puts the largest first. Python's sort is stable: items with equal keys keep their order.

```python
scores = [("fig", 2), ("pear", 5), ("kiwi", 2)]
sorted(scores, key=lambda item: (-item[1], item[0]))
# [('pear', 5), ('fig', 2), ('kiwi', 2)]
```
