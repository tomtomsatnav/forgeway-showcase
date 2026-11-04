### `json.loads` raises `ValueError` on bad input

Its own error, `json.JSONDecodeError`, is a kind of `ValueError`. It also accepts any JSON value, not only an object, so check what you got before you use it.

```python
import json

try:
    value = json.loads('{"size": 3}')
except ValueError:
    value = None
isinstance(value, dict)  # True; json.loads("[1]") would give a list
```

### `json.dumps(value, sort_keys=True)` gives repeatable text

Two equal dicts can hold their keys in different orders. Sorting the keys makes equal values give equal text, which you can compare or use as a dict key.

```python
import json

json.dumps({"b": 1, "a": 2}, sort_keys=True)  # '{"a": 2, "b": 1}'
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

### Your own exception is a class that inherits from `Exception`

The class can be empty, or carry extra attributes for whoever catches it. Callers can then catch your error by name and leave other errors alone.

```python
class OutOfStock(Exception):
    def __init__(self, item: str) -> None:
        super().__init__(f"No {item} left")
        self.item = item
```

### `Mapping` and `MutableMapping` are "anything that works like a dict"

Code written against them uses `[key]`, `.get`, `in` and `.items()`, and it works on a dict or on any object that behaves like one. Use `MutableMapping` when you will write to it. Such an object need not hold its data in memory, so stick to those operations and do not assume it is a real dict.

```python
from collections.abc import MutableMapping


def remember(store: MutableMapping[str, int], name: str) -> int:
    store[name] = store.get(name, 0) + 1
    return store[name]
```
