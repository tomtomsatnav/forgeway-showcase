# You will need `McpError` from forgeway_kit.mcp. `check_instance` below is provided.


def check_instance(value, schema, path="$"):
    """Provided: the problems found validating `value` against a JSON Schema (empty when valid).

    It understands `type`, `enum`, `const`, `properties`, `required`, `additionalProperties`,
    `items` and string and number bounds, and ignores the rest.
    """
    types = {
        "string": lambda v: isinstance(v, str),
        "boolean": lambda v: isinstance(v, bool),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, int | float) and not isinstance(v, bool),
        "array": lambda v: isinstance(v, list),
        "object": lambda v: isinstance(v, dict),
        "null": lambda v: v is None,
    }
    expected = schema.get("type")
    if expected is not None:
        options = [expected] if isinstance(expected, str) else list(expected)
        if not any(types.get(t, lambda v: True)(value) for t in options):
            return [f"{path}: expected {' or '.join(options)}, got {type(value).__name__}"]
    problems = []
    if "const" in schema and value != schema["const"]:
        problems.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{path}: must be one of {schema['enum']!r}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            problems.append(f"{path}: shorter than {schema['minLength']} characters")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            problems.append(f"{path}: longer than {schema['maxLength']} characters")
    if isinstance(value, int | float) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            problems.append(f"{path}: below the minimum of {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            problems.append(f"{path}: above the maximum of {schema['maximum']}")
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            problems += check_instance(item, schema["items"], f"{path}[{index}]")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        problems += [
            f"{path}.{name}: is required"
            for name in schema.get("required", [])
            if name not in value
        ]
        for name, item in value.items():
            if name in properties:
                problems += check_instance(item, properties[name], f"{path}.{name}")
            elif schema.get("additionalProperties") is False:
                problems.append(f"{path}.{name}: is not an expected property")
    return problems


class Hub:
    def __init__(self, clients):
        self.failed = {}
        raise NotImplementedError("validate the server names and keep the clients")

    def tools(self):
        """Every tool of every server, named `<server>__<tool>`."""
        raise NotImplementedError("list each server, namespacing the tools")

    def call(self, name, arguments):
        """Run a namespaced tool and return {"is_error", "text", "data"}."""
        raise NotImplementedError("route the call, then validate any structured output")
