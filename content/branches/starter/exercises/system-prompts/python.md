### Unpacking gives each part of a tuple its own name

It works in an assignment and at the top of a `for` loop, so a list of pairs reads cleanly.

```python
pairs = [("fig", 3), ("pear", 5)]
for name, price in pairs:
    print(name, price)
```

### `Sequence[str]` accepts a list or a tuple

It says "something ordered that I will only read", so callers can pass either. `collections.abc` holds these general types, and like every hint they are not enforced when the code runs.

```python
from collections.abc import Sequence


def first_letters(words: Sequence[str]) -> str:
    return "".join(word[0] for word in words)
```
