### `Callable[[str], int]` is the type of a function

The list holds the argument types and the last item is the return type. Functions are ordinary values in Python, so you can take one as an argument and call it. Import it from `collections.abc`.

```python
from collections.abc import Callable


def apply_twice(step: Callable[[int], int], start: int) -> int:
    return step(step(start))


apply_twice(lambda n: n + 3, 1)  # 7
```

### A function can be a default argument

Naming a function as a default gives you the real behaviour in normal use, while a caller or a test can pass a stand-in. Note the missing brackets: you pass the function, you do not call it.

```python
import time
from collections.abc import Callable


def nap(seconds: float, sleep: Callable[[float], None] = time.sleep) -> None:
    sleep(seconds)
```

### `except` can take a tuple of types

Any of them is caught, and you can keep the tuple in a constant if you need it more than once.

```python
def read_number(text: str) -> float:
    try:
        return 1 / float(text)
    except (ValueError, ZeroDivisionError):
        return 0.0
```

### `isinstance(value, kind)` checks a type while the code runs

Annotations are not enforced, so this is how you test data that came from outside, or tell apart several kinds of object. The second argument can be a tuple or a union.

```python
def describe(value: object) -> str:
    if isinstance(value, str):
        return "text"
    if isinstance(value, (int, float)):
        return "a number"
    return "something else"
```

### A bare `*` in a signature makes the rest keyword-only

Callers must name those arguments, which keeps a call readable and stops two numbers being swapped by accident.

```python
def bake(item: str, *, minutes: int = 20, fan: bool = False) -> str:
    return f"{item}: {minutes} min"


bake("loaf", minutes=35)  # bake("loaf", 35) raises TypeError
```
