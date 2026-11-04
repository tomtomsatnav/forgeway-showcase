### A generator expression feeds a function one value at a time

It is a comprehension in round brackets, with no list built on the way. When it is the only argument, the function's own brackets are enough.

```python
total_letters = sum(len(word) for word in ["fig", "pear"])  # 7
", ".join(word.upper() for word in ["fig", "pear"])  # 'FIG, PEAR'
```

### `Sequence[str]` accepts a list or a tuple

It says "something ordered that I will only read", so callers can pass either. `collections.abc` holds these general types, and like every hint they are not enforced when the code runs.

```python
from collections.abc import Sequence


def first_letters(words: Sequence[str]) -> str:
    return "".join(word[0] for word in words)
```
