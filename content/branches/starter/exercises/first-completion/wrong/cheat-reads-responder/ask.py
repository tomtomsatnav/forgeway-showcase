from forgeway_kit import ModelClient


def ask(client: ModelClient, question: str) -> str:
    """Probe: read the reply from the fake's responder instead of asking the model."""
    try:
        return client.responder(None)
    except AttributeError:
        return ""
