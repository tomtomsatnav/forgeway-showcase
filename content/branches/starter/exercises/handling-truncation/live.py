"""Get a long answer in 60-token pieces from a live model with your complete_fully().

python live.py   (set FORGEWAY_LIVE first; see LIVE-MODE.md)
"""

from continuation import complete_fully

from forgeway_kit import default_client

question = "Explain, in about 200 words, how a hash map handles collisions."
# A small max_tokens forces the reply to be cut off, so your continuation logic does the work.
print(complete_fully(default_client(), question, max_tokens=60, max_continuations=6))
