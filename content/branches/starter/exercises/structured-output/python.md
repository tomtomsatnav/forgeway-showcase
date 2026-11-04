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

### `True` counts as an `int` in Python

`bool` is a subclass of `int`, so `isinstance(True, int)` is true. When only a real number will do, rule booleans out first, or test `type(value) is int`.

```python
def is_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


is_count(3), is_count(True)  # (True, False)
```

### `str.format` fills a template you keep elsewhere

Named fields suit a template stored as a constant, where an f-string would run too early.

```python
TEMPLATE = "{count} x {item}"
TEMPLATE.format(item="fig", count=2)  # '2 x fig'
```
