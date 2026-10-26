# You will need `re` and `Message` from forgeway_kit.


def redact(text):
    """Replace emails, cards, NI numbers and phone numbers with their placeholders."""
    raise NotImplementedError("apply the four patterns from the brief, in order")


def ask(client, history, text, system=None):
    """Send `history` plus `text` to `client`, redacted, and return the reply text."""
    raise NotImplementedError("build the messages from redacted content and send only those")
