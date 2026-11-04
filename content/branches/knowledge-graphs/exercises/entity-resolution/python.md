### `unicodedata` takes accents apart

The `NFKD` form splits a letter from its accent, and `combining()` tells you which characters are the accents.

```python
import unicodedata

parts = unicodedata.normalize("NFKD", "é")
[unicodedata.combining(ch) > 0 for ch in parts]  # [False, True]
```

### `str.casefold` is the right way to ignore case

It is a stronger `lower()` meant for comparing text: German `ß` folds to `ss`, for example.

```python
"Straße".casefold() == "STRASSE".casefold()  # True
```

### `dict.setdefault(key, default)` creates an entry the first time

It returns what is stored under the key, adding the default if there was nothing. That lets you build groups without checking first.

```python
groups: dict[str, list[str]] = {}
for word in ["fig", "fir", "pear"]:
    groups.setdefault(word[0], []).append(word)
# {'f': ['fig', 'fir'], 'p': ['pear']}
```

### A dict comprehension builds a dict the same way

It is a list comprehension with `key: value` at the front and braces around it.

```python
lengths = {word: len(word) for word in ["fig", "pear"]}  # {'fig': 3, 'pear': 4}
```

### A generator expression feeds a function one value at a time

It is a comprehension in round brackets, with no list built on the way. When it is the only argument, the function's own brackets are enough.

```python
total_letters = sum(len(word) for word in ["fig", "pear"])  # 7
", ".join(word.upper() for word in ["fig", "pear"])  # 'FIG, PEAR'
```
