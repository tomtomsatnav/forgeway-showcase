"""Trim a long conversation with your fit_to_budget(), then send what is left to a live model.

python live.py   (set FORGEWAY_LIVE first; see LIVE-MODE.md)
"""

from budget import fit_to_budget

from forgeway_kit import Message, count_tokens, default_client

SYSTEM = "You are a helpful travel assistant. Answer briefly."
history = []
for day in range(1, 9):
    history += [
        Message("user", f"Day {day} of my Japan trip: suggest one thing to do in Kyoto."),
        Message("assistant", f"On day {day}, visit a temple early, before the crowds."),
    ]
history.append(Message("user", "Which train is quickest from Kyoto to Tokyo?"))

kept = fit_to_budget(SYSTEM, history, budget=120)
print(
    f"kept {len(kept)} of {len(history)} messages, "
    f"{count_tokens(SYSTEM) + sum(count_tokens(m.content) for m in kept)} tokens of 120\n"
)
print(default_client().complete(kept, system=SYSTEM).text)
