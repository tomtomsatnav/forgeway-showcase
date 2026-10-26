from copilot import Copilot  # noqa: F401

# You will need `json`, `Counter`, `redact` from guardrails, and `Message` from forgeway_kit.

# The judge's prompt, filled in with str.format for each ordering of a pair.
JUDGE_TEMPLATE = (
    "{rubric}\n\nQuestion: {question}\n\nResponse 1: {first}\n\nResponse 2: {second}\n\n"
    "Which response is better under the rubric? Reply with 1 or 2."
)


def judge_pair(judge, rubric: str, question: str, a: str, b: str) -> str:
    """'A', 'B' or 'tie', from two judge requests with the answers in both orders."""
    raise NotImplementedError


def run_eval(copilot, judge, cases: list[dict], rubric: str, *, now: str) -> dict:
    """Run every case through the copilot, judge what was shown, check each trajectory."""
    raise NotImplementedError


def run_red_team(copilot, attacks: list[dict], canary: str, *, now: str) -> dict:
    """Send every attack through the copilot and report what leaked, per category."""
    raise NotImplementedError
