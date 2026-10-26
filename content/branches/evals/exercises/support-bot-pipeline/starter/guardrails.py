import re

# You will need `json`, `Message` and `ModelError` from forgeway_kit.

# The four patterns from the redaction exercise, in the order they must be applied.
PATTERNS = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"), "[EMAIL]"),
    (re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"), "[CARD]"),
    (re.compile(r"\b[A-Z]{2}\d{6}[A-D]\b"), "[NINO]"),
    (re.compile(r"(?<!\w)\+?\d(?:[ -]?\d){9,12}(?!\w)"), "[PHONE]"),
]

# What a customer sees when a request is blocked or a reply is refused.
REFUSAL = "I can't help with that request."

# The bot's system prompt. Pass it, unchanged, on every bot request.
SYSTEM_PROMPT = (
    "You are a support assistant for Acme. Use the tools to look up orders. "
    'Reply with only a JSON object: {"answer": <string>, "escalate": <true or false>}.'
)


def redact(text):
    """Replace personal data with placeholders."""
    raise NotImplementedError("apply PATTERNS in order")


def classify(shield, text):
    """'SAFE', 'JAILBREAK', 'INJECTION', 'UNKNOWN' or 'ERROR' for `text`."""
    raise NotImplementedError("one request to the shield; read the verdict; fail closed")


def guarded_reply(bot, shield, question, tools, registry, banned=(), max_attempts=2, max_steps=6):
    """Answer `question` with the bot, behind every guardrail."""
    raise NotImplementedError("redact, classify, run the tool loop, then check the reply")
