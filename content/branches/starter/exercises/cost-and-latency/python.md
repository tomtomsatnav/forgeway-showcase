### `math.ceil` and `math.floor` round up and down

Each returns an `int`. Python's built-in `round()` is different: it rounds halves to the nearest even number.

```python
import math

math.ceil(2.1), math.floor(2.9)  # (3, 2)
round(2.5)  # 2
```

### A dict comprehension builds a dict the same way

It is a list comprehension with `key: value` at the front and braces around it.

```python
lengths = {word: len(word) for word in ["fig", "pear"]}  # {'fig': 3, 'pear': 4}
```

### A list comprehension builds a list in one expression

Read it as "this value, for each item, if this holds". The `if` part is optional.

```python
prices = [3, 8, 5]
cheap_doubled = [price * 2 for price in prices if price < 6]  # [6, 10]
```

### `dict.get(key, default)` reads a key that may be missing

Square brackets raise `KeyError` on a missing key. `.get` returns the default instead, or `None` if you give none.

```python
stock = {"fig": 3}
stock.get("fig", 0)  # 3
stock.get("pear", 0)  # 0
```
