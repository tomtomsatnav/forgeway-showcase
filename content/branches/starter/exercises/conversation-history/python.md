### `@property` reads like an attribute but runs a method

Callers write `room.area`, with no brackets, and the value is worked out when they ask.

```python
class Room:
    def __init__(self, width: int, depth: int) -> None:
        self.width, self.depth = width, depth

    @property
    def area(self) -> int:
        return self.width * self.depth
```

### `[*items, extra]` builds a new list

The star spreads one list into another, so the original stays as it was. It is a tidy way to add to a list you do not own.

```python
base = ["fig", "pear"]
longer = [*base, "plum"]  # ['fig', 'pear', 'plum']
base  # still ['fig', 'pear']
```
