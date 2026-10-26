# Serving MCP over stdio

The **Model Context Protocol** (MCP) lets an application plug tools, documents and prompts into a
model without custom glue for each one. Underneath it is nothing exotic: JSON-RPC 2.0 messages
sent back and forth. In this branch you build the protocol by hand, at the wire level, against
revision **2025-11-25**, the newest revision that opens with the `initialize` handshake. No SDK;
the point is to see what SDKs hide.

The simplest way to run an MCP server is as a child process. The client starts it and talks to it
over its **standard input and output**, with one rule of framing: each message is a single line of
JSON ending in a newline, and it must not contain a raw newline. Nothing else may appear on
stdout. Logs go to **stderr**.

```text
client -> server stdin : {"jsonrpc":"2.0","id":1,"method":"ping"}\n
server -> client stdout: {"jsonrpc":"2.0","id":1,"result":{}}\n
server -> stderr       : handling ping
```

Three habits cause most real-world stdio failures:

- A stray `print` for debugging puts a non-JSON line in the protocol stream and the client gives
  up on the connection.
- A pretty-printed reply (`indent=2`) spans several lines, so the client sees fragments.
- Output sits in a buffer and the client waits for ever for a reply that is already "sent".

## Your task

`server.py` already contains `handle(message)`, which answers one decoded request and returns
`None` for notifications. Implement `serve(stdin, stdout)`, the loop around it, and make the
server safe to run as `python server.py`.

- Read stdin one line at a time and stop when it ends. Skip blank lines.
- For each line, decode the JSON and write `handle`'s reply as one line to stdout, flushed
  straight away. Write nothing when `handle` returns `None`.
- A line that is not valid JSON gets an error reply with code `-32700` and a null `id`. The server
  then carries on with the next line. Valid JSON that is not an object (`[1, 2]`, `42`) is
  already answered by `handle` with -32600 and a null `id`; send that reply like any other.
- Log the method of each request to stderr, one line per request as it is handled. `handle` has a
  leftover `print` that is breaking the stream; move it where it belongs.
- Exit normally, with status 0, when stdin closes.
