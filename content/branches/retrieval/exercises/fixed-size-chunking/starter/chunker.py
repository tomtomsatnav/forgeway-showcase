def chunk(text: str, size: int, overlap: int = 0) -> list[str]:
    """Split `text` into chunks of at most `size` characters.

    Consecutive chunks share `overlap` characters. The last chunk ends exactly at the end of
    `text`, and no chunk is wholly contained in the one before it.

    Raises ValueError if size < 1, overlap < 0 or overlap >= size.
    """
    raise NotImplementedError("slice the text, stepping forward by size - overlap")
