"""The part both servers share: framing, the lifecycle, tools, resources and pagination.

Both servers run as `python -S <file> <argument>`, so use the standard library only.
"""

import json
import sys

PROTOCOL_VERSION = "2025-11-25"
PAGE_SIZE = 4  # resources/list returns pages of this many
CONFIRM_KEY = "notes/confirm"  # where a caller puts a confirmation token, inside params._meta


class RpcError(Exception):
    """Raise this to answer a request with a JSON-RPC error."""

    def __init__(self, code, message, data=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def error(request_id, code, message, data=None):
    body = {"code": code, "message": message}
    if data is not None:
        body["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": body}


class McpServer:
    """A suggested shape: give it the server's name, its tools and its resources, and let
    `serve` do the rest. Change it as you like; the tests only talk to the servers over stdio."""

    def __init__(self, name):
        self.name = name

    def handle(self, message):
        """The reply to one decoded message, or None when nothing is to be sent."""
        raise NotImplementedError

    def serve(self, stdin, stdout):
        """Read newline-delimited JSON-RPC from `stdin` until it closes; write replies to
        `stdout`, one line each, flushed at once. Logs go to stderr."""
        for line in stdin:
            print(f"{self.name}: got {len(line)} characters", file=sys.stderr, flush=True)
        _ = json  # you will need it
