import json
from collections.abc import Mapping
from typing import Any

from forgeway_kit import Completion, Message, StreamingModelClient, Tool


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


def _refuse_if_refused(completion: Completion) -> None:
    if completion.stop_reason == "refusal":
        raise Refused(completion.text)


def _parse(reply: str, schema: Mapping[str, Any]) -> dict:
    data = json.loads(reply)  # JSONDecodeError is a ValueError
    check(data, schema)
    return data


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
    ask = Message(role="user", content=f"Extract the {name} from this text:\n\n{text}")
    if "response_format" in supports:
        completion = client.complete([ask], response_format=schema)
        _refuse_if_refused(completion)
        return _parse(completion.text, schema)  # validate anyway: defence in depth
    if "tool_choice" in supports:
        tool = Tool(name=name, description=f"Record the {name}.", input_schema=schema)
        completion = client.complete([ask], tools=[tool], tool_choice={"name": name})
        _refuse_if_refused(completion)
        if not completion.tool_calls:
            raise ValueError(f"the model did not call {name}")
        arguments = dict(completion.tool_calls[0].arguments)
        check(arguments, schema)
        return arguments

    # Neither: the parse-and-repair loop from "Structured output".
    messages = [
        Message(
            role="user",
            content=(
                f"{ask.content}\n\nReply with only a JSON object that fits this JSON Schema:\n"
                f"{json.dumps(schema)}"
            ),
        )
    ]
    completion = client.complete(messages)
    _refuse_if_refused(completion)
    try:
        return _parse(completion.text, schema)
    except ValueError as error:
        messages += [
            Message(role="assistant", content=completion.text),
            Message(
                role="user",
                content=f"That reply was invalid: {error}. Reply again with only the JSON object.",
            ),
        ]
    completion = client.complete(messages)
    _refuse_if_refused(completion)
    return _parse(completion.text, schema)
