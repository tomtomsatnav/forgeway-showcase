# The initialise handshake

Before an MCP client and server exchange anything useful, they agree on three things: which
**protocol revision** to speak, what each side is **capable** of, and who they are. This happens in
a fixed opening exchange:

```text
client -> server  initialize           {"protocolVersion": "2025-11-25",
                                        "capabilities": {...}, "clientInfo": {"name": ..., "version": ...}}
server -> client  result               {"protocolVersion": "2025-11-25",
                                        "capabilities": {"tools": {}}, "serverInfo": {...}}
client -> server  notifications/initialized          (a notification: no reply)
```

**Version negotiation** is the subtle part. The client sends the newest revision it supports. If the
server supports that revision it answers with the same string. If not, it answers with a revision
it *does* support, its preferred one, and the client decides whether it can use it or must
disconnect. The server never errors just because it has not heard of the version.

**Capabilities** are how a server advertises what it offers (`tools`, `resources`, `prompts`). A
client only calls methods the server declared, so a server must not claim more than it implements.

Until the handshake is done the server is in no state to serve work. The only message allowed
earlier is `ping`.

## Your task

Implement the `Server` class in `handshake.py`. `Server(supported_versions, capabilities, name,
version)` has a `handle(message)` method taking a decoded JSON-RPC message and returning the
response dict (or `None`). `supported_versions` lists revisions, preferred first.

- `initialize` needs `protocolVersion` (a string), `capabilities` (an object) and `clientInfo`
  (an object) in its params. Otherwise reply with error -32602 and leave the server untouched.
- A valid `initialize` replies with `protocolVersion` (the client's if supported, else
  `supported_versions[0]`), your `capabilities`, and `serverInfo` holding `name` and `version`.
  Remember the client's `clientInfo` and `capabilities` as `self.client_info` and
  `self.client_capabilities`.
- A second `initialize` is error -32600 (already initialised), unless its params are invalid:
  check the params first, so a second `initialize` with bad params is -32602, as above.
- Before `initialize`, every request except `ping` is error -32600 (not initialised). `ping`
  always returns `{}`.
- `notifications/initialized` sets `self.ready` to `True`, but only after a successful
  `initialize`; sent earlier it is ignored. It is a notification: return `None`.
- After initialising, any other method is error -32601.
