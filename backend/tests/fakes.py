"""Test doubles."""

from __future__ import annotations

import json

from lattice.domain.grading import SandboxRequest, SandboxResult


class ScriptedRunner:
    """Passes every check when the submission contains `marker`; fails them all otherwise."""

    def __init__(self, marker: str = "return a + b") -> None:
        self.marker = marker
        self.requests: list[SandboxRequest] = []

    def run(self, request: SandboxRequest) -> SandboxResult:
        self.requests.append(request)
        ok = any(self.marker in text for text in request.submission.values())
        checks = [
            {"id": cid, "outcome": "passed" if ok else "failed", "message": "" if ok else "nope"}
            for cid in request.checks
        ]
        payload = json.dumps({"checks": checks, "exit_status": 0 if ok else 1})
        return SandboxResult(0, f"LATTICE-REPORT {request.nonce} {payload}\n", "", False, False, 5)
