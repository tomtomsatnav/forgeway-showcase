class InvalidCursor(ValueError):
    """The cursor was not issued by this server for this list (reply with -32602)."""


def page(items, cursor, page_size):
    """One page of `items` after `cursor`, and the cursor for the next page (or None)."""
    raise NotImplementedError("encode a position as an opaque cursor")


def fetch_all(send, method, key, max_pages=50):
    """Follow `nextCursor` through every page of `method` and return all of `result[key]`."""
    raise NotImplementedError("loop over the pages, guarding against a server that never ends")
