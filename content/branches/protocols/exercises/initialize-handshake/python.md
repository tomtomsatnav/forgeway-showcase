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

### `dict.get(key, default)` reads a key that may be missing

Square brackets raise `KeyError` on a missing key. `.get` returns the default instead, or `None` if you give none.

```python
stock = {"fig": 3}
stock.get("fig", 0)  # 3
stock.get("pear", 0)  # 0
```
