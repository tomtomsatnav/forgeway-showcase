"""The wire format between the in-sandbox harness and the worker.

The harness prints exactly one line ``LATTICE-REPORT <nonce> <json>`` on its real stdout.
The nonce is chosen by the worker per attempt, so a report printed by anything else is
detectable.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Literal

REPORT_PREFIX = "LATTICE-REPORT"
MAX_MESSAGE_CHARS = 2000

Outcome = Literal["passed", "failed"]


@dataclass(frozen=True)
class CheckOutcome:
    id: str
    outcome: Outcome
    message: str = ""
    output: str = ""


@dataclass(frozen=True)
class HarnessReport:
    checks: list[CheckOutcome] = field(default_factory=list)
    exit_status: int = 0

    def to_line(self, nonce: str) -> str:
        return f"{REPORT_PREFIX} {nonce} {json.dumps(asdict(self), separators=(',', ':'))}"

    @classmethod
    def from_json(cls, payload: str) -> HarnessReport:
        data = json.loads(payload)
        return cls(
            checks=[CheckOutcome(**c) for c in data["checks"]],
            exit_status=int(data["exit_status"]),
        )


def clip(text: str, limit: int = MAX_MESSAGE_CHARS) -> str:
    """Trim long text, keeping the start, and say that it was trimmed."""
    return text if len(text) <= limit else text[: limit - 20].rstrip() + "\n… (trimmed)"
