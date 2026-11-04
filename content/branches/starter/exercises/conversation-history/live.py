"""Hold a three-turn conversation with a live model through your Chat.

python live.py   (set FORGEWAY_LIVE first; see LIVE-MODE.md)
"""

from chat import Chat

from forgeway_kit import default_client

SYSTEM = "You are a concise cooking assistant. Answer in two sentences or fewer."
chat = Chat(default_client(), system=SYSTEM)
for text in [
    "I have eggs, spinach and feta. What could I make?",
    "How long should it bake?",
    "And what was the first ingredient I mentioned?",  # needs the history
]:
    print(f"you: {text}\nbot: {chat.send(text)}\n")
print(f"{len(chat.history)} messages in the history")
