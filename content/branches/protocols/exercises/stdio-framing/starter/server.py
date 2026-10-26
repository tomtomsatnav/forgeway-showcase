import sys


def handle(message):
    """Answer one decoded JSON-RPC message. Returns the reply dict, or None for a notification."""
    if not isinstance(message, dict):
        return error(None, -32600, "a message must be a JSON object")
    method = message.get("method")
    print(f"handling {method}")  # leftover debugging
    if "id" not in message:
        return None  # notifications never get a reply
    request_id = message["id"]
    params = message.get("params") or {}
    if method == "initialize":
        result = {
            "protocolVersion": "2025-11-25",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "echo-server", "version": "1.0.0"},
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        schema = {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }
        result = {
            "tools": [{"name": "echo", "description": "Repeat the text.", "inputSchema": schema}]
        }
    elif method == "tools/call" and params.get("name") == "echo":
        text = str(params.get("arguments", {}).get("text", ""))
        result = {"content": [{"type": "text", "text": text}], "isError": False}
    else:
        return error(request_id, -32601, f"method not found: {method}")
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def serve(stdin, stdout):
    """Read newline-delimited JSON-RPC from `stdin`, write replies to `stdout`."""
    raise NotImplementedError("a read-handle-write loop with one flushed line per reply")


if __name__ == "__main__":
    serve(sys.stdin, sys.stdout)
