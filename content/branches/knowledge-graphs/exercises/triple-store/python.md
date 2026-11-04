### `typing.NamedTuple` is a tuple with named fields

You can read `book.title` or unpack it like any tuple. It is immutable, compares and sorts as a tuple, and can be used as a dict key or in a set.

```python
from typing import NamedTuple


class Book(NamedTuple):
    title: str
    pages: int = 0


title, pages = Book("Emma", 474)
```

### `str | None` means "a string, or nothing"

The `|` builds a union type, and `None` is Python's "no value". Check for it with `is None`, because an empty string is also false in an `if`.

```python
def initial(name: str | None) -> str:
    if name is None:
        return "?"
    return name[0]
```

### `dict.setdefault(key, default)` creates an entry the first time

It returns what is stored under the key, adding the default if there was nothing. That lets you build groups without checking first.

```python
groups: dict[str, list[str]] = {}
for word in ["fig", "fir", "pear"]:
    groups.setdefault(word[0], []).append(word)
# {'f': ['fig', 'fir'], 'p': ['pear']}
```

### A list comprehension builds a list in one expression

Read it as "this value, for each item, if this holds". The `if` part is optional.

```python
prices = [3, 8, 5]
cheap_doubled = [price * 2 for price in prices if price < 6]  # [6, 10]
```
