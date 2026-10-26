"""Strict YAML parsing for content files.

PyYAML's safe loader keeps the last of two equal mapping keys, so a second `bosses:` block
silently replaces the first. Content is hand-written and long, so a duplicate key is always a
mistake: this loader refuses it and names the line of the first definition.
"""

from __future__ import annotations

from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode, Node


class UniqueKeySafeLoader(yaml.SafeLoader):
    """A `SafeLoader` that raises on a duplicate key in any mapping."""

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Any, Any]:
        seen: dict[Any, Node] = {}
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                first = seen[key].start_mark.line + 1
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key {key!r} (first defined on line {first})",
                    key_node.start_mark,
                )
            seen[key] = key_node
        return super().construct_mapping(node, deep=deep)


def load_yaml(text: str) -> Any:
    """Parse one YAML document, rejecting duplicate mapping keys."""
    return yaml.load(text, Loader=UniqueKeySafeLoader)  # noqa: S506 - a SafeLoader subclass
