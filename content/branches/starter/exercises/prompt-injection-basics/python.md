### `str.replace` returns a new string

Strings never change in place, so you keep the result. It replaces every occurrence, and matches exact text only, case included.

```python
text = "red, red wine"
text.replace("red", "blue")  # 'blue, blue wine'
text  # still 'red, red wine'
```

### An f-string puts values into text

Anything inside braces is evaluated and turned into text. Add `!r` to show a value as Python would write it, quotes included.

```python
name = "fig"
f"{name} costs {1 + 2}"  # 'fig costs 3'
f"{name!r}"  # "'fig'"
```
