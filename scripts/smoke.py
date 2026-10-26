"""End-to-end smoke test against a running stack: register, verify, fail, pass, earn XP, unlock.

Verifying the new account follows the emailed link through the test-only outbox, so the grading
steps need a stack started with LATTICE_E2E=1 and console email (docker-compose.e2e.yml).
Without it, the smoke test stops after registering.

Usage: uv run python scripts/smoke.py [base_url]
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
EXERCISE = "starter.first-completion"
SOLUTION = (
    Path(__file__).parents[1]
    / "content/branches/starter/exercises/first-completion/solution/ask.py"
)


def check(condition: bool, detail: object) -> None:
    if not condition:
        raise SystemExit(f"✗ smoke test failed: {detail}")


def wait_for(client: httpx.Client, attempt_id: str) -> dict:
    for _ in range(60):
        attempt = client.get(f"/api/attempts/{attempt_id}").json()
        if attempt["status"] not in {"queued", "running"}:
            return attempt
        time.sleep(0.5)
    raise SystemExit("attempt was not graded within 30 s")


def main() -> None:
    with httpx.Client(base_url=BASE, headers={"origin": BASE}, timeout=10) as client:
        me = (
            client.post(
                "/api/auth/register",
                json={
                    "email": f"smoke-{uuid.uuid4().hex[:8]}@example.com",
                    "password": "correct horse battery",
                    "display_name": "Smoke",
                },
            )
            .raise_for_status()
            .json()
        )
        client.headers["x-csrf-token"] = me["csrf_token"]
        outbox = client.get("/api/test/outbox/latest", params={"email": me["email"]})
        # A problem response means the outbox exists but the email (sent just after the response)
        # is not in it yet; a bare 404 means there is no outbox.
        for _ in range(10):
            if outbox.status_code != 404 or "code" not in outbox.json():
                break
            time.sleep(0.2)
            outbox = client.get("/api/test/outbox/latest", params={"email": me["email"]})
        if outbox.status_code == 404:
            print("✓ registered; no test outbox (LATTICE_E2E unset), so grading is not checked")
            return
        token = outbox.raise_for_status().json()["token"]
        client.post("/api/auth/verify-email", json={"token": token}).raise_for_status()
        print("✓ registered and verified")

        wrong = (
            client.post(
                f"/api/exercises/{EXERCISE}/attempts",
                json={"files": {"ask.py": "def ask(client, question):\n    return 'hi'\n"}},
            )
            .raise_for_status()
            .json()
        )
        failed = wait_for(client, wrong["id"])
        check(failed["status"] == "failed", failed)
        print("✓ wrong answer failed:", failed["checks"][0]["message"][:80])

        right = (
            client.post(
                f"/api/exercises/{EXERCISE}/attempts",
                json={"files": {"ask.py": SOLUTION.read_text()}},
            )
            .raise_for_status()
            .json()
        )
        passed = wait_for(client, right["id"])
        check(passed["status"] == "passed", passed)
        print(f"✓ correct answer passed in {passed['duration_ms']} ms:", passed["progression"])

        level = client.get("/api/map").json()["level"]
        check(level["total_xp"] == passed["progression"]["xp_awarded"] > 0, level)
        print("✓ XP recorded:", level)


if __name__ == "__main__":
    main()
