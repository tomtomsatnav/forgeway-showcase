### A bare `*` in a signature makes the rest keyword-only

Callers must name those arguments, which keeps a call readable and stops two numbers being swapped by accident.

```python
def bake(item: str, *, minutes: int = 20, fan: bool = False) -> str:
    return f"{item}: {minutes} min"


bake("loaf", minutes=35)  # bake("loaf", 35) raises TypeError
```

### `separator.join(parts)` glues strings together

The method belongs to the separator, which surprises most newcomers, and every part must already be a string.

```python
", ".join(["fig", "pear"])  # 'fig, pear'
"".join(["a", "b"])  # 'ab'
```
