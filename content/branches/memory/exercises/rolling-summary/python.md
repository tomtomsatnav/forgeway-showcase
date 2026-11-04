### `[*items, extra]` builds a new list

The star spreads one list into another, so the original stays as it was. It is a tidy way to add to a list you do not own.

```python
base = ["fig", "pear"]
longer = [*base, "plum"]  # ['fig', 'pear', 'plum']
base  # still ['fig', 'pear']
```

### A generator expression feeds a function one value at a time

It is a comprehension in round brackets, with no list built on the way. When it is the only argument, the function's own brackets are enough.

```python
total_letters = sum(len(word) for word in ["fig", "pear"])  # 7
", ".join(word.upper() for word in ["fig", "pear"])  # 'FIG, PEAR'
```
