"""Stream a reply from a live model with your stream_completion.

python live.py   (set FORGEWAY_LIVE first; see LIVE-MODE.md)
"""

from streaming import StreamInterrupted, stream_completion

from forgeway_kit import Message, default_client

question = Message(role="user", content="Explain in three short paragraphs why chat apps stream.")
try:
    completion = stream_completion(
        default_client(), [question], lambda text: print(text, end="", flush=True)
    )
    print(f"\n\n[{completion.stop_reason}] {completion.usage}")
except StreamInterrupted as interrupted:
    print(f"\n\n[cut off after {len(interrupted.partial_text)} characters: {interrupted.error}]")
