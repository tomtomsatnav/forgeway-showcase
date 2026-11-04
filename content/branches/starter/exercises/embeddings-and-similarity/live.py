"""Pick the most relevant notes with your top_k(), then let a live model answer from them.

python live.py   (set FORGEWAY_LIVE first; see LIVE-MODE.md)
"""

from search import top_k

from forgeway_kit import HashingEmbedder, Message, default_client

NOTES = [
    "Refunds are issued to the original payment method within 5 working days.",
    "Opened items can be returned within 14 days if they are unused and in their box.",
    "Our London store opens at 9am on weekdays and 10am at weekends.",
    "Gift cards cannot be exchanged for cash.",
    "Standard delivery takes 3 to 5 working days; express delivery is next day.",
]
question = "Can I return headphones I have opened?"
notes = top_k(HashingEmbedder(), question, NOTES, k=2)
print("retrieved:\n" + "\n".join(f"- {note}" for note in notes) + "\n")
prompt = "Answer from these notes only.\n\n" + "\n".join(notes) + f"\n\nQuestion: {question}"
print(default_client().complete([Message("user", prompt)]).text)
