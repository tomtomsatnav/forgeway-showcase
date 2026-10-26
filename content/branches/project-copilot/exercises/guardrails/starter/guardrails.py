import re

# You will need `json`, and `Message`, `ModelClient` and `ModelError` from forgeway_kit.

# The four patterns from the redaction exercise, in the order they must be applied.
PATTERNS = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"), "[EMAIL]"),
    (re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"), "[CARD]"),
    (re.compile(r"\b[A-Z]{2}\d{6}[A-D]\b"), "[NINO]"),
    (re.compile(r"(?<!\w)\+?\d(?:[ -]?\d){9,12}(?!\w)"), "[PHONE]"),
]

# What a customer sees when the copilot cannot give a checked answer.
REFUSAL = "Sorry, I can't answer that here. I've passed your question to a colleague."

# Appended to the system prompt: the shape every final reply must have.
REPLY_FORMAT = (
    'Reply with only a JSON object: {"answer": <string>, "escalate": <true or false>}. '
    "Cite sources inside the answer, like [1]."
)


def redact(text: str) -> str:
    """Replace personal data with placeholders."""
    raise NotImplementedError("apply PATTERNS in order")


def screen(shield, text: str) -> str:
    """'SAFE', 'INJECTION', 'UNKNOWN' or 'ERROR' for a piece of retrieved text."""
    raise NotImplementedError("one request to the shield; read its verdict; fail closed")
