class InvalidParams(Exception):
    """Raised by a method handler when its params are unusable (reply with -32602)."""


def dispatch(message, methods):
    """Answer one decoded JSON-RPC message with a response dict, or None if none is due.

    `methods` maps a method name to a function taking the params dict and returning a result dict.
    """
    raise NotImplementedError("validate the message, then route it to the right handler")
