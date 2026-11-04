# Dataclasses and typing

Much of the code you will write and read here passes small records around: a token count, a
search hit, a tool call. A dataclass writes the boring parts of such a class for you, from
annotated fields:

```python
from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class Point:
    x: int
    y: int = 0  # a default


origin = Point(0)
moved = replace(origin, y=5)  # a new Point; `origin` is unchanged
origin.x = 1  # raises FrozenInstanceError, because it is frozen


@dataclass
class Route:
    stops: list[Point] = field(default_factory=list)  # a new list for each Route
```

Annotations such as `list[Point]` and `str | None` state what a value should be. Python does not
enforce them when the code runs, but they tell your reader and your type checker what you meant.
`str | None` is how you say "a string, or nothing".

A `@property` is a method read like an attribute: `route.length`, not `route.length()`.

## Your task

Implement these in `records.py`:

- `Usage`, a frozen dataclass with the fields `input_tokens: int` and `output_tokens: int`, where
  `output_tokens` defaults to 0, and a `total` property giving the two added together.
- `add_output(usage, extra)` returns a new `Usage` with `extra` more output tokens. It must leave
  `usage` as it was.
- `Conversation`, a dataclass (not frozen) with the fields `title: str` and `messages: list[str]`,
  where `messages` defaults to a new empty list for each conversation. Give it a method
  `add(text)` that appends to `messages`.
- `find(conversations, title)` returns the first conversation with that title, or `None` if
  there is none.
