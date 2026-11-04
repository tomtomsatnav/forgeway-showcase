### `Counter` also does multiset arithmetic

`a & b` keeps each item with the smaller of its two counts, so repeats are matched up one for one. `sum(counts.values())` adds the counts up.

```python
from collections import Counter

Counter("aabc") & Counter("abbd")  # Counter({'a': 1, 'b': 1})
```

### `str.translate` swaps or removes many characters at once

`str.maketrans` builds the table. Its third argument lists characters to delete. `string.punctuation` holds the ASCII punctuation.

```python
import string

table = str.maketrans("", "", string.punctuation)
"fig, pear!".translate(table)  # 'fig pear'
```

### A generator expression feeds a function one value at a time

It is a comprehension in round brackets, with no list built on the way. When it is the only argument, the function's own brackets are enough.

```python
total_letters = sum(len(word) for word in ["fig", "pear"])  # 7
", ".join(word.upper() for word in ["fig", "pear"])  # 'FIG, PEAR'
```

### `enumerate()` gives you the index with each item

Pass `start=1` to count from one.

```python
for number, word in enumerate(["fig", "pear"], start=1):
    print(number, word)  # 1 fig, then 2 pear
```
