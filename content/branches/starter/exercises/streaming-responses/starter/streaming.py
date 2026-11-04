from collections.abc import Callable, Sequence

from forgeway_kit import Completion, Message, StreamingModelClient, Tool


class StreamInterrupted(Exception):
    """The stream broke after some of the reply had already been shown to the user."""

    def __init__(self, partial_text: str, error: Exception) -> None:
        super().__init__(f"the stream broke after {len(partial_text)} characters: {error}")
        self.partial_text = partial_text  # exactly the text passed to on_text
        self.error = error  # the error the stream raised


def stream_completion(
    client: StreamingModelClient,
    messages: Sequence[Message],
    on_text: Callable[[str], None],
    *,
    tools: Sequence[Tool] = (),
) -> Completion:
    """Stream a reply, showing its text through `on_text` as it arrives.

    Returns the whole reply as a `Completion`. Starts again once if the stream breaks before
    any text was shown; raises `StreamInterrupted` if it breaks after.
    """
    raise NotImplementedError("consume client.stream(...) and assemble the reply")
