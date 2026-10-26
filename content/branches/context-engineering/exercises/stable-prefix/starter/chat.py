# You will need `Message` from forgeway_kit.
from collections.abc import Sequence

from forgeway_kit import ModelClient, Tool


class CachedChat:
    """A multi-turn chat whose requests share the longest possible byte-identical prefix."""

    def __init__(
        self,
        client: ModelClient,
        instructions: str,
        reference: list[str],
        tools: Sequence[Tool] = (),
    ) -> None:
        raise NotImplementedError("build everything that never changes once, here")

    def send(self, text: str, *, now: str, notes: Sequence[str] = ()) -> str:
        """One turn: the volatile `[now: ...]` and note lines go in the new user message."""
        raise NotImplementedError("append to the history, never rewrite it")
