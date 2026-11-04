from typing import Any


def parse_object(text: str) -> dict[str, Any] | None:
    """The dict `text` holds as JSON, or None if it holds anything else."""
    raise NotImplementedError


def canonical(value: Any) -> str:
    """`value` as JSON with sorted keys and no spaces."""
    raise NotImplementedError


def document_ids(text: str) -> list[str]:
    """Every `DOC-<digits>` standing as a word of its own, in order, repeats included."""
    raise NotImplementedError


def is_tool_name(name: str) -> bool:
    """A lower-case letter, then up to 31 lower-case letters, digits or underscores."""
    raise NotImplementedError


def redact_keys(text: str) -> str:
    """Replace each `key-<digits>` with `key-` and one `#` per digit."""
    raise NotImplementedError
