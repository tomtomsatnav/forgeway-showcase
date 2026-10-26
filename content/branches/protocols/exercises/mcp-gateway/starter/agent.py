# You will need `Message` and `Tool` from forgeway_kit, and `McpError` from forgeway_kit.mcp.


def run_agent(model, mcp, question, confirm, max_steps=6):
    """Answer `question` with the model, offering and running the tools of the gateway `mcp`
    while treating everything it relays as untrusted and asking `confirm` before anything
    destructive runs."""
    raise NotImplementedError(
        "clean what you offer, fence what comes back, ask before destructive calls"
    )
