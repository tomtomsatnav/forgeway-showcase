### Your own exception is a class that inherits from `Exception`

The class can be empty, or carry extra attributes for whoever catches it. Callers can then catch your error by name and leave other errors alone.

```python
class OutOfStock(Exception):
    def __init__(self, item: str) -> None:
        super().__init__(f"No {item} left")
        self.item = item
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

### `except Exception` catches almost everything

Use it only at a boundary, such as around code you do not control, where any failure should be turned into a result rather than a crash. It leaves `KeyboardInterrupt` alone, and `as err` gives you the error, with `str(err)` as its message.

```python
def safely(step) -> str:
    try:
        return step()
    except Exception as err:
        return f"failed: {err}"
```
