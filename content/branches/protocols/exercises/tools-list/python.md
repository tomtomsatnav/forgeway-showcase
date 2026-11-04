### `inspect` lets you read a function's signature

`inspect.signature(f).parameters` maps each argument name to its details, and `inspect.getdoc(f)` gives the docstring, tidied up. A parameter with no default has `inspect.Parameter.empty` as its `.default`.

```python
import inspect


def bake(item: str, minutes: int = 20) -> str:
    """Bake one item."""
    return item


inspect.signature(bake).parameters["minutes"].default  # 20
inspect.getdoc(bake)  # 'Bake one item.'
```

### `typing.get_type_hints` reads annotations as real objects

`get_origin` and `get_args` then take a generic type apart.

```python
from typing import get_args, get_origin, get_type_hints


def bake(items: list[int]) -> None: ...


hint = get_type_hints(bake)["items"]  # list[int]
get_origin(hint), get_args(hint)  # (list, (int,))
```

### `re.fullmatch` checks a whole string

`re.match` only anchors the start, and even `$` lets a trailing newline through. `fullmatch` is the safe way to validate, and returns `None` when the string does not fit.

```python
import re

re.fullmatch(r"[a-z]+", "fig")  # a match
re.fullmatch(r"[a-z]+", "fig\n")  # None
re.match(r"[a-z]+$", "fig\n")  # a match, which is rarely what you meant
```

### `isinstance(value, kind)` checks a type while the code runs

Annotations are not enforced, so this is how you test data that came from outside, or tell apart several kinds of object. The second argument can be a tuple or a union.

```python
def describe(value: object) -> str:
    if isinstance(value, str):
        return "text"
    if isinstance(value, (int, float)):
        return "a number"
    return "something else"
```
