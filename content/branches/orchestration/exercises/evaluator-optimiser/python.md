### `re.sub` replaces every match

It returns the new string. In the replacement, `\1` stands for the first captured group. Add `re.IGNORECASE` to ignore case.

```python
import re

re.sub(r"\d+", "#", "3 figs, 12 pears")  # '# figs, # pears'
re.sub(r"(fig)s", r"\1", "FIGS", flags=re.IGNORECASE)  # 'FIG'
```

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

### An f-string puts values into text

Anything inside braces is evaluated and turned into text. Add `!r` to show a value as Python would write it, quotes included.

```python
name = "fig"
f"{name} costs {1 + 2}"  # 'fig costs 3'
f"{name!r}"  # "'fig'"
```
