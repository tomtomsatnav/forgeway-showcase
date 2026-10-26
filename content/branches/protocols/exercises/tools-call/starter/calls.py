class ToolError(Exception):
    """Raised by a tool handler with a message written for the model."""


def handle_call(request, tools):
    """Answer one `tools/call` request with a complete JSON-RPC response dict."""
    raise NotImplementedError("separate protocol errors from tool execution errors")
