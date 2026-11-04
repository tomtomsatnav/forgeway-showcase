def describe_tool(fn):
    """The MCP tool definition for `fn`: name, description and inputSchema."""
    raise NotImplementedError("read the name, docstring, signature and type hints of fn")


def list_tools(functions):
    """The result of a `tools/list` request for these functions."""
    raise NotImplementedError("describe every function, rejecting duplicate or invalid names")
