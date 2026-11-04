# JSON and regular expressions

Models and tools talk in text. To work with it, you turn JSON into Python values and back, and
you pick out or check small patterns with regular expressions.

```python
import json
import re

json.loads('{"a": [1, 2]}')  # {'a': [1, 2]}
json.loads("not json")  # raises json.JSONDecodeError, a ValueError
json.dumps({"b": 1, "a": 2}, sort_keys=True)  # '{"a": 2, "b": 1}'

re.findall(r"\d+", "3 pears, 12 figs")  # ['3', '12']
re.sub(r"\d", "#", "room 42")  # 'room ##'
re.sub(r"(\w+)@", lambda m: m.group(1).upper() + "@", "ann@host")  # 'ANN@host'
re.fullmatch(r"[a-z]+", "tea")  # a match: the whole string fits
re.fullmatch(r"[a-z]+", "tea!")  # None
```

Write patterns as raw strings (`r"..."`), so a backslash reaches `re` as it is. `\b` matches at
the edge of a word, and `re.fullmatch` is the safe way to check a whole string.

## Your task

Implement these in `parsing.py`:

- `parse_object(text)` returns the dict that `text` holds as JSON. If `text` is not valid JSON, or
  it holds anything other than an object (a list, a number and so on), return `None`.
- `canonical(value)` returns `value` as JSON text with the keys sorted and no spaces at all, such
  as `{"a":1,"b":[1,2]}`, so that two equal values always give the same text.
- `document_ids(text)` returns every document id in `text`, in order, repeats included. An id is
  `DOC-` followed by one or more digits, and it stands as a word of its own: `DOC-12` counts, but
  there is none in `XDOC-12` or `DOC-12a`.
- `is_tool_name(name)` returns `True` if the whole of `name` is a lower-case letter followed by up
  to 31 lower-case letters, digits or underscores, otherwise `False`. A trailing newline makes a
  name invalid.
- `redact_keys(text)` replaces each key in `text` with `key-` followed by one `#` per digit of the
  key. A key is `key-` followed by one or more digits, standing as a word of its own, so
  `key-204` becomes `key-###`.
