# Listing tools with input schemas

A model can only use a tool it knows about. An MCP server advertises its tools in response to
`tools/list`, and the quality of that listing decides how well the model uses them. Each tool has
a `name`, a `description` the model reads to decide when to call it, and an **`inputSchema`**: a
JSON Schema object describing the arguments.

```text
client -> server  {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
server -> client  {"jsonrpc": "2.0", "id": 2, "result": {"tools": [{
                    "name": "get_weather",
                    "description": "Current weather for a city.",
                    "inputSchema": {"type": "object",
                                    "properties": {"city": {"type": "string"},
                                                   "days": {"type": "integer", "default": 1}},
                                    "required": ["city"]}}]}}
```

Writing schemas by hand drifts away from the code. The usual fix is to derive them from the
function itself: its name, docstring and type annotations. The schema is plain JSON Schema, not
Python: `int` becomes `"integer"`, `str` becomes `"string"`, `list[str]` becomes an array whose
`items` are strings. Tool names are 1 to 128 characters of **ASCII** letters (`A-Z`, `a-z`), digits
(`0-9`), `_`, `-` and `.`, and they must be unique in a listing. (This is the specification's
guidance on tool names in revision 2025-11-25, under Tools; `naïve` and `名前` are not valid, and
Python's `str.isalnum()` and the regex class `\w` both accept them.)

## Your task

In `tools.py`, implement `describe_tool(fn)` and `list_tools(functions)`.

- `describe_tool(fn)` returns `{"name", "description", "inputSchema"}`. The name is `fn.__name__`;
  the description is the first line of the docstring, or `""` if there is none.
- `inputSchema` is `{"type": "object", "properties": {...}, "required": [...]}` with one property
  per parameter, in signature order. Map `str`, `int`, `float`, `bool`, `dict` (object), `list`
  (array), `list[T]` (array whose `items` is the schema for `T`) and `Literal["a", "b"]`
  (`{"type": "string", "enum": ["a", "b"]}`). An unannotated parameter is `{}` (anything).
- `required` lists the parameters that have no default. Leave the key out when there are none.
  A parameter whose default is a string, number or boolean records it as `"default"`.
- `list_tools(functions)` returns `{"tools": [...]}` in the order given. It raises `ValueError` for
  a duplicate name or a name outside the allowed characters, a trailing newline included.
- The result must be plain JSON: `json.dumps` has to accept it.
