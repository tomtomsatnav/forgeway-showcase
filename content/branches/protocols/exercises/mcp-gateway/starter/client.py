# You will need `McpError` and `PROTOCOL_VERSION` from forgeway_kit.mcp.
import json
import queue
import subprocess
import threading


class StdioTransport:
    """Provided: talks to a child process over its stdin and stdout, one JSON message per line.

    `send(message)` writes a message. `receive()` returns the next message as a dict, or `None`
    once the child has closed its stdout, and raises `TimeoutError` if nothing arrives within
    `timeout` seconds. Lines that are not JSON objects are skipped. `close()` stops the child.
    """

    def __init__(self, argv, timeout=2.0):
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
        self.process.kill()
        self.process.wait()


class McpClient:
    """An MCP client over a transport with `send(message_dict)` and `receive()`."""

    def __init__(self, transport):
        self.transport = transport
        self.next_id = 1

    def initialize(self):
        raise NotImplementedError("initialize, check the revision, send initialized")

    def request(self, method, params=None):
        raise NotImplementedError("send a request and read until its response arrives")

    def list_all(self, method, key, max_pages=50):
        raise NotImplementedError("follow nextCursor to the end, guarding against loops")

    def list_all_tools(self):
        return self.list_all("tools/list", "tools")

    def call_tool(self, name, arguments, meta=None):
        raise NotImplementedError("send tools/call, adding `_meta` when `meta` is given")

    def close(self):
        raise NotImplementedError("close the transport")
