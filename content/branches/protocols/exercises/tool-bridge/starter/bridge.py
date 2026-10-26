# You will need `Message` and `Tool` from forgeway_kit.

PROTOCOL_VERSION = "2025-11-25"


class McpError(Exception):
    """The server answered a request with a JSON-RPC error."""

    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class McpClient:
    def __init__(self, transport):
        self.transport = transport
        self.next_id = 1

    def initialize(self):
        raise NotImplementedError("initialize, check the revision, send initialized")

    def request(self, method, params=None):
        raise NotImplementedError("send a request and read until its response arrives")

    def list_tools(self):
        raise NotImplementedError("follow nextCursor through every page")

    def call_tool(self, name, arguments):
        raise NotImplementedError("send tools/call and return the result")


def run_agent(model, mcp, question, max_steps=6):
    """Let `model` use the tools of the MCP server behind `mcp` to answer `question`."""
    raise NotImplementedError("offer the tools, run the calls through MCP, report errors back")
