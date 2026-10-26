"""Server-side verification of Cloudflare Turnstile tokens.

See https://developers.cloudflare.com/turnstile/get-started/server-side-validation/. Cloudflare's
documented test secrets behave predictably (`1x0000000000000000000000000000000AA` always passes,
`2x0000000000000000000000000000000AA` always fails), which the tests rely on through a fake
transport.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
MAX_TOKEN_LENGTH = 2048  # Cloudflare's documented maximum

# Takes the form fields, returns the parsed JSON answer.
Transport = Callable[[dict[str, str]], dict[str, Any]]


def _post(fields: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(
        SITEVERIFY_URL, data=urllib.parse.urlencode(fields).encode(), method="POST"
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        answer: dict[str, Any] = json.loads(response.read())
        return answer


class TurnstileVerifier:
    def __init__(self, secret: str, transport: Transport = _post) -> None:
        self._secret = secret
        self._transport = transport

    def verify(self, token: str | None, remote_ip: str | None) -> bool:
        """Whether Cloudflare accepts `token`. Fails closed when Cloudflare cannot be reached."""
        if not token or len(token) > MAX_TOKEN_LENGTH:
            return False
        fields = {"secret": self._secret, "response": token}
        if remote_ip:
            fields["remoteip"] = remote_ip
        try:
            answer = self._transport(fields)
        except Exception:
            logger.exception("turnstile siteverify failed")
            return False
        return answer.get("success") is True
