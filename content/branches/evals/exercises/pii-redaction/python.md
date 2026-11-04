### `re.compile` gives a pattern a name

The compiled pattern has the same methods (`.findall`, `.search`, `.sub` and so on), and keeping it in a constant at the top of the file makes it easy to find and reuse.

```python
import re

NUMBER = re.compile(r"\d+")
NUMBER.findall("3 figs, 12 pears")  # ['3', '12']
```

### Lookarounds check what is beside a match without including it

`(?<!x)` means "not after x" and `(?!x)` means "not before x", and `(?<=x)` and `(?=x)` are the positive forms. They suit edges that `\b` does not describe.

```python
import re

re.findall(r"(?<![\w-])fig(?![\w-])", "fig fig-tree figs")  # ['fig']
```

### `re.sub` replaces every match

It returns the new string. In the replacement, `\1` stands for the first captured group. Add `re.IGNORECASE` to ignore case.

```python
import re

re.sub(r"\d+", "#", "3 figs, 12 pears")  # '# figs, # pears'
re.sub(r"(fig)s", r"\1", "FIGS", flags=re.IGNORECASE)  # 'FIG'
```

### A list comprehension builds a list in one expression

Read it as "this value, for each item, if this holds". The `if` part is optional.

```python
prices = [3, 8, 5]
cheap_doubled = [price * 2 for price in prices if price < 6]  # [6, 10]
```
