### `@dataclass(frozen=True)` makes an immutable record

You list annotated fields and Python writes the constructor and `==` for you. Assigning to a field afterwards raises `FrozenInstanceError`, and the record can be used as a dict key.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    x: int
    y: int = 0  # a default


Point(3)  # Point(x=3, y=0)
```

### `re.escape` makes text safe inside a pattern

Characters such as `.` and `+` mean something to `re`, so escape any text you did not write yourself before building a pattern from it.

```python
import re

word = "c++"
re.findall(re.escape(word), "c++ and c")  # ['c++']
```

### Lookarounds check what is beside a match without including it

`(?<!x)` means "not after x" and `(?!x)` means "not before x", and `(?<=x)` and `(?=x)` are the positive forms. They suit edges that `\b` does not describe.

```python
import re

re.findall(r"(?<![\w-])fig(?![\w-])", "fig fig-tree figs")  # ['fig']
```

### The `re` module finds patterns in text

`re.findall` returns every match and `re.search` returns the first as a match object, or `None`. Write patterns as raw strings (`r"..."`), so a backslash reaches `re` unchanged. `\d` is a digit, `\w` a word character and `\b` the edge of a word.

```python
import re

re.findall(r"\d+", "3 figs, 12 pears")  # ['3', '12']
re.search(r"\d+", "no numbers")  # None
```

### A generator expression feeds a function one value at a time

It is a comprehension in round brackets, with no list built on the way. When it is the only argument, the function's own brackets are enough.

```python
total_letters = sum(len(word) for word in ["fig", "pear"])  # 7
", ".join(word.upper() for word in ["fig", "pear"])  # 'FIG, PEAR'
```
