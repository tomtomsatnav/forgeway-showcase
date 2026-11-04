import json
import re
from typing import Any


def parse_object(text: str) -> dict[str, Any] | None:
    """The dict `text` holds as JSON, or None if it holds anything else."""
    try:
        value = json.loads(text)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def canonical(value: Any) -> str:
    """`value` as JSON with sorted keys and no spaces."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def document_ids(text: str) -> list[str]:
    """Every `DOC-<digits>` standing as a word of its own, in order, repeats included."""
    return re.findall(r"\bDOC-\d+\b", text)


def is_tool_name(name: str) -> bool:
    """A lower-case letter, then up to 31 lower-case letters, digits or underscores."""
    return re.fullmatch(r"[a-z][a-z0-9_]{0,31}", name) is not None


def redact_keys(text: str) -> str:
    """Replace each `key-<digits>` with `key-` and one `#` per digit."""
    return re.sub(r"\bkey-(\d+)\b", lambda match: "key-" + "#" * len(match.group(1)), text)
