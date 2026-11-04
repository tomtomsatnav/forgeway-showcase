### `zip()` walks several sequences side by side

It stops at the shortest, unless you pass `strict=True`, which makes a length mismatch raise `ValueError`.

```python
names = ["fig", "pear"]
prices = [3, 5]
dict(zip(names, prices, strict=True))  # {'fig': 3, 'pear': 5}
```

### `sorted(items, key=...)` sorts by whatever the key returns

A `lambda` is a small unnamed function, handy here. A tuple key sorts by its first item, then its second, and negating a number puts the largest first. Python's sort is stable: items with equal keys keep their order.

```python
scores = [("fig", 2), ("pear", 5), ("kiwi", 2)]
sorted(scores, key=lambda item: (-item[1], item[0]))
# [('pear', 5), ('fig', 2), ('kiwi', 2)]
```

### A slice takes part of a list or string

`items[start:stop]` includes `start` and stops before `stop`. Either end can be left out, a negative index counts from the end, and a slice past the end is simply shorter rather than an error.

```python
letters = "abcdef"
letters[1:3]  # 'bc'
letters[:2]  # 'ab'
letters[-2:]  # 'ef'
letters[4:100]  # 'ef'
```

### `Sequence[str]` accepts a list or a tuple

It says "something ordered that I will only read", so callers can pass either. `collections.abc` holds these general types, and like every hint they are not enforced when the code runs.

```python
from collections.abc import Sequence


def first_letters(words: Sequence[str]) -> str:
    return "".join(word[0] for word in words)
```
