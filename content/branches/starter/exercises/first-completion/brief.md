# Your first completion

Every model API, whichever provider you use, has the same core shape: you send a list of
messages and get a completion back.

In this platform you talk to models through `forgeway_kit`, a small provider-neutral client:

```python
from forgeway_kit import Message

completion = client.complete([Message(role="user", content="What is a token?")])
print(completion.text)
```

## Your task

Implement `ask(client, question)` in `ask.py`. It should send `question` to the model as a
single user message and return the reply text.

The grader uses a deterministic fake model, so you can't be lucky or unlucky: the checks look
at exactly what your code sent and what it returned.
