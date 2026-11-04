### A slice takes part of a list or string

`items[start:stop]` includes `start` and stops before `stop`. Either end can be left out, a negative index counts from the end, and a slice past the end is simply shorter rather than an error.

```python
letters = "abcdef"
letters[1:3]  # 'bc'
letters[:2]  # 'ab'
letters[-2:]  # 'ef'
letters[4:100]  # 'ef'
```

### `raise ValueError(...)` refuses bad input

It stops the function and hands the problem to the caller. `ValueError` is the usual type for an argument of the right type but a wrong value.

```python
def halve(number: int) -> int:
    if number % 2:
        raise ValueError(f"{number} is odd")
    return number // 2
```
