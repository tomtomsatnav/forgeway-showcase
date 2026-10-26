# Resources and prompts

Tools are only one of the three things an MCP server can offer. The other two are for the
*application* and the *user* rather than the model:

- **Resources** are data the server can hand over: a file, a database row, a page of
  documentation. Each has a `uri`. `resources/list` shows what exists, `resources/read` fetches the
  content.
- **Prompts** are reusable message templates with named arguments, the kind a UI offers as slash
  commands. `prompts/list` shows them, `prompts/get` fills one in and returns ready-to-send
  messages.

```text
resources/list   -> {"resources": [{"uri": "file:///notes.txt", "name": "notes", "mimeType": "text/plain"}]}
resources/read   {"uri": "file:///notes.txt"}
                 -> {"contents": [{"uri": "file:///notes.txt", "mimeType": "text/plain", "text": "..."}]}

prompts/get      {"name": "summarise", "arguments": {"topic": "tides"}}
                 -> {"description": "...", "messages": [{"role": "user",
                      "content": {"type": "text", "text": "Summarise tides in 50 words."}}]}
```

Three details matter. **Listings are cheap**: they never include content, because a client lists
often and reads rarely. A **missing resource** is a protocol error with its own code, -32002, and
the `data` names the uri that was not found. And **templates are an injection surface**: argument
values come from users, so they must be substituted exactly once. A value that happens to contain
`{other}` is just text, not another placeholder.

## Your task

Implement the `Library` class in `primitives.py`. `Library(resources, prompts)` is built from plain
dicts and its `handle(request)` method takes a decoded request and returns the full JSON-RPC
response.

- A resource dict has `uri`, `name`, `text`, and optionally `mime_type` (default `text/plain`) and
  `description`. `resources/list` returns `{"resources": [...]}` with `uri`, `name`, `mimeType`
  and, only when it has one, `description`. It must not include `text`.
- `resources/read` takes `params.uri` and returns `{"contents": [{"uri", "mimeType", "text"}]}`.
  A missing or non-string `uri` is -32602. An unknown one is -32002 with `data: {"uri": <uri>}`.
- A prompt dict has `name`, `description`, `template` and `arguments` (a list of dicts with `name`,
  `description` and `required`). `prompts/list` returns `{"prompts": [...]}` with `name`,
  `description` and, only if it has any, `arguments` (each with `name`, `description`, `required`).
  Never include the template.
- `prompts/get` takes `params.name` and optional `params.arguments`. It returns `description` and
  one `user` message of type `text`. Replace each `{argument}` placeholder in the template, in a
  single pass, with the matching value; an optional argument that was not given becomes the empty
  string, and a `{placeholder}` that is not a declared argument stays as written.
- It is -32602 when the prompt is unknown, when `arguments` is not an object of strings, or when a
  required argument is missing (the message names it).
- Any other method is -32601.
