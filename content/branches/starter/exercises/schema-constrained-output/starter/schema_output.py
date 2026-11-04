from collections.abc import Mapping
from typing import Any

from forgeway_kit import StreamingModelClient


class Refused(Exception):
    """The model declined to answer (stop_reason "refusal")."""

    def __init__(self, text: str) -> None:
        super().__init__(text or "the model refused")
        self.text = text  # the model's explanation, exactly as it replied


def check(value: Any, schema: Mapping[str, Any], path: str = "$") -> None:
    """Raise ValueError naming the first place `value` breaks `schema`; return None if it fits.

    A small JSON Schema subset, enough for this exercise: `type` (object, array, string,
    integer, number, boolean, null), `properties`, `required`, `additionalProperties: false`,
    `items` and `enum`. Use a full validator, such as the `jsonschema` package, in real code.
    """
    kind = schema.get("type")
    if kind is not None and not _is(value, kind):
        raise ValueError(f"{path} must be of type {kind}, not {type(value).__name__}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} must be one of {schema['enum']}, not {value!r}")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                raise ValueError(f'{path} is missing the required field "{key}"')
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise ValueError(f"{path} has fields the schema does not allow: {extra}")
        for key, item in value.items():
            if key in properties:
                check(item, properties[key], f"{path}.{key}")
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            check(item, schema["items"], f"{path}[{index}]")


def _is(value: Any, kind: str) -> bool:
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    types = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}
    return isinstance(value, types[kind])


def extract(
    client: StreamingModelClient,
    text: str,
    schema: Mapping[str, Any],
    name: str,
    *,
    supports: set[str],
) -> dict:
    """Extract an object that fits `schema` from `text`, by the strongest route `supports` allows.

    Raises `Refused` if the model refuses and `ValueError` if no valid object comes back.
    """
    raise NotImplementedError("native schema first, then a forced tool, then parse-and-repair")
