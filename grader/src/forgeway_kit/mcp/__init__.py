"""The MCP names exercise code is written against.

Learners implement the protocol themselves, at the wire level, so this module is deliberately
small: the protocol revision the branch teaches, the standard JSON-RPC error codes, and the
exception a client raises for an error response. Messages travel as plain ``dict``s.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any

#: The protocol revision this branch teaches. It is the newest revision that opens with the
#: ``initialize`` handshake (the SDK's ``LATEST_HANDSHAKE_VERSION``). The revision after it,
#: 2026-07-28, replaces the handshake with a stateless per-request envelope.
PROTOCOL_VERSION = "2025-11-25"

JSONRPC_VERSION = "2.0"


class ErrorCode(IntEnum):
    """The standard JSON-RPC error codes, plus the one MCP adds for missing resources."""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    RESOURCE_NOT_FOUND = -32002


class McpError(Exception):
    """A server answered a request with a JSON-RPC error."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.data = data


__all__ = ["JSONRPC_VERSION", "PROTOCOL_VERSION", "ErrorCode", "McpError"]
