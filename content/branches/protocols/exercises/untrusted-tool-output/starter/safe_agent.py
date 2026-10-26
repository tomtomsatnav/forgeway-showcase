# You will need `Message` and `Tool` from forgeway_kit, and `McpError` from forgeway_kit.mcp.


def run_agent(model, mcp, question, max_steps=6):
    """Answer `question` with the model, offering and running the tools of the MCP server `mcp`
    while treating everything the server says as untrusted."""
    raise NotImplementedError("clean what you offer, fence what comes back")
