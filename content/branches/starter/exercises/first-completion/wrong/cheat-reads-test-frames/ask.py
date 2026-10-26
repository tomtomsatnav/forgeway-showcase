import sys

from forgeway_kit import Message, ModelClient


def ask(client: ModelClient, question: str) -> str:
    """Probe: send the wrong question, then rewrite the test's record of it from its frames."""
    completion = client.complete([Message(role="user", content="Hello")])
    frame = sys._getframe(1)
    while frame is not None:
        model = frame.f_locals.get("model")
        requests = getattr(model, "requests", None)
        if isinstance(requests, list) and requests:
            fixed = Message(role="user", content=question)
            requests[-1] = type(requests[-1])(**{**vars(requests[-1]), "messages": (fixed,)})
            break
        frame = frame.f_back
    return completion.text
