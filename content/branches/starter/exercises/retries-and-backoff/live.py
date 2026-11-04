"""Call a live model through your complete_with_retries(), which rides out rate limits.

python live.py   (set FORGEWAY_LIVE first; see LIVE-MODE.md)
"""

import time

from retry import complete_with_retries

from forgeway_kit import Message, default_client


def sleep(seconds: float) -> None:
    print(f"(retrying in {seconds:.1f}s)")
    time.sleep(seconds)


client = default_client()
for city in ["Lagos", "Oslo", "Lima", "Hanoi", "Perth"]:
    messages = [Message("user", f"One sentence: what is {city} best known for?")]
    print(complete_with_retries(client, messages, max_attempts=4, sleep=sleep).text)
