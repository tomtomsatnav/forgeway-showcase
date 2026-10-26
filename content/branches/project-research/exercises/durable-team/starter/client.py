"""An MCP client for one server started as a child process."""

import json
import queue
import subprocess
import threading

from forgeway_kit.mcp import PROTOCOL_VERSION, McpError  # noqa: F401 - you will need them


class StdioTransport:
    """Provided: talks to a child process over its stdin and stdout, one JSON message per line.

    `send(message)` writes a message. `receive()` returns the next message as a dict, or `None`
    once the child has closed its stdout, and raises `TimeoutError` if nothing arrives within
    `timeout` seconds. Lines that are not JSON objects are skipped. `close()` stops the child.
    """

    def __init__(self, argv, timeout=5.0):
        self.timeout = timeout
        self.process = subprocess.Popen(  # noqa: S603
            list(argv),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self.lines = queue.Queue()
        threading.Thread(target=self.pump, daemon=True).start()

    def pump(self):
        for line in self.process.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def send(self, message):
        try:
            self.process.stdin.write(json.dumps(message) + "\n")
            self.process.stdin.flush()
        except (OSError, ValueError):
            raise ConnectionError("the child process is no longer reading its input") from None

    def receive(self):
        while True:
            try:
                line = self.lines.get(timeout=self.timeout)
            except queue.Empty:
                raise TimeoutError(f"nothing arrived for {self.timeout} seconds") from None
            if line is None:
                self.lines.put(None)
                return None
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if isinstance(message, dict):
                return message

    def close(self):
        try:
            self.process.stdin.close()
            self.process.wait(timeout=self.timeout)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            self.process.kill()
            self.process.wait()


class McpClient:
    """One connection to the server that `argv` starts, ready to use once constructed.

    Bring your client from the MCP gateway: the handshake, matching replies to requests by id,
    answering a server's `ping`, and `McpError` for an error response. Workers run in threads
    and share one client per server, so send one request at a time.
    """

    def __init__(self, argv):
        self.transport = StdioTransport(argv)

    def request(self, method, params=None):
        raise NotImplementedError

    def list_tools(self, max_pages=50):
        """Every tool the server lists, following `nextCursor`."""
        raise NotImplementedError

    def call_tool(self, name, arguments, meta=None):
        """The `tools/call` result dict; `_meta` is added to the params when `meta` is given."""
        raise NotImplementedError

    def close(self):
        self.transport.close()
