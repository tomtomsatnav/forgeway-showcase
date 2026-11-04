"""Answer under a system prompt and few-shot examples with your answer().

python live.py   (set FORGEWAY_LIVE first; see LIVE-MODE.md)
"""

from prompts import answer

from forgeway_kit import default_client

SYSTEM = (
    "You turn customer feedback into a sentiment label: positive, negative or mixed. "
    "Reply with the label only."
)
EXAMPLES = [
    ("The delivery was fast and the jacket fits perfectly.", "positive"),
    ("It broke after two days and support never replied.", "negative"),
]
client = default_client()
for feedback in [
    "Lovely colour, but the zip feels cheap.",
    "Exactly what I ordered, thank you!",
    "Third time the app has logged me out mid-checkout.",
]:
    print(f"{answer(client, SYSTEM, feedback, EXAMPLES):>10}  {feedback}")
