"""Ask a live model a question with your ask().

python live.py   (set FORGEWAY_LIVE first; see LIVE-MODE.md)
"""

from ask import ask

from forgeway_kit import default_client

question = "In two sentences, what is a context window in a large language model?"
print(f"Q: {question}\n")
print(f"A: {ask(default_client(), question)}")
