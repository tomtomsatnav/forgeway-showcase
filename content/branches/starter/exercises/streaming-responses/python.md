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

### Your own exception is a class that inherits from `Exception`

The class can be empty, or carry extra attributes for whoever catches it. Callers can then catch your error by name and leave other errors alone.

```python
class OutOfStock(Exception):
    def __init__(self, item: str) -> None:
        super().__init__(f"No {item} left")
        self.item = item
```

### `raise ... from` says what caused an error

`from err` records the original error, which shows in the traceback. `from None` hides it, for when it would only confuse the reader.

```python
class BadPrice(Exception):
    pass


def price_of(text: str) -> int:
    try:
        return int(text)
    except ValueError as err:
        raise BadPrice(text) from err
```

### A generator expression feeds a function one value at a time

It is a comprehension in round brackets, with no list built on the way. When it is the only argument, the function's own brackets are enough.

```python
total_letters = sum(len(word) for word in ["fig", "pear"])  # 7
", ".join(word.upper() for word in ["fig", "pear"])  # 'FIG, PEAR'
```
