### `collections.Counter` counts things

It is a dict from each item to its count, and a missing item counts as 0. `most_common()` gives the pairs, highest first.

```python
from collections import Counter

counts = Counter(["fig", "pear", "fig"])
counts["fig"]  # 2
counts["plum"]  # 0
counts.most_common(1)  # [('fig', 2)]
```

### `zip()` walks several sequences side by side

It stops at the shortest, unless you pass `strict=True`, which makes a length mismatch raise `ValueError`.

```python
names = ["fig", "pear"]
prices = [3, 5]
dict(zip(names, prices, strict=True))  # {'fig': 3, 'pear': 5}
```

### A generator expression feeds a function one value at a time

It is a comprehension in round brackets, with no list built on the way. When it is the only argument, the function's own brackets are enough.

```python
total_letters = sum(len(word) for word in ["fig", "pear"])  # 7
", ".join(word.upper() for word in ["fig", "pear"])  # 'FIG, PEAR'
```
