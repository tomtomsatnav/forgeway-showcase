### `typing.NamedTuple` is a tuple with named fields

You can read `book.title` or unpack it like any tuple. It is immutable, compares and sorts as a tuple, and can be used as a dict key or in a set.

```python
from typing import NamedTuple


class Book(NamedTuple):
    title: str
    pages: int = 0


title, pages = Book("Emma", 474)
```

### `re.fullmatch` checks a whole string

`re.match` only anchors the start, and even `$` lets a trailing newline through. `fullmatch` is the safe way to validate, and returns `None` when the string does not fit.

```python
import re

re.fullmatch(r"[a-z]+", "fig")  # a match
re.fullmatch(r"[a-z]+", "fig\n")  # None
re.match(r"[a-z]+$", "fig\n")  # a match, which is rarely what you meant
```

### `sorted(items, key=...)` sorts by whatever the key returns

A `lambda` is a small unnamed function, handy here. A tuple key sorts by its first item, then its second, and negating a number puts the largest first. Python's sort is stable: items with equal keys keep their order.

```python
scores = [("fig", 2), ("pear", 5), ("kiwi", 2)]
sorted(scores, key=lambda item: (-item[1], item[0]))
# [('pear', 5), ('fig', 2), ('kiwi', 2)]
```

### `dict.setdefault(key, default)` creates an entry the first time

It returns what is stored under the key, adding the default if there was nothing. That lets you build groups without checking first.

```python
groups: dict[str, list[str]] = {}
for word in ["fig", "fir", "pear"]:
    groups.setdefault(word[0], []).append(word)
# {'f': ['fig', 'fir'], 'p': ['pear']}
```
