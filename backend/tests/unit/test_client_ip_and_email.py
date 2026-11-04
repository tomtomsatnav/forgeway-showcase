"""The real client IP behind trusted proxies, and the email senders."""

from __future__ import annotations

import json
from typing import Any

import pytest

from lattice.api.client_ip import parse_networks, resolve
from lattice.domain.email import EmailMessage
from lattice.infrastructure import email as email_module
from lattice.infrastructure.email import ConsoleEmailSender, ResendEmailSender, build_sender

CADDY = parse_networks("172.16.0.0/12, ::1")


def test_an_untrusted_peer_is_the_client_whatever_it_claims() -> None:
    headers = {"cf-connecting-ip": "203.0.113.9", "x-forwarded-for": "203.0.113.9"}
    assert resolve("198.51.100.4", headers, CADDY) == "198.51.100.4"
    assert resolve("198.51.100.4", headers, ()) == "198.51.100.4"


def test_a_trusted_proxy_passes_on_cf_connecting_ip_first() -> None:
    headers = {"cf-connecting-ip": "203.0.113.9", "x-forwarded-for": "198.51.100.1, 172.18.0.2"}
    assert resolve("172.18.0.2", headers, CADDY) == "203.0.113.9"


def test_without_cf_connecting_ip_the_first_forwarded_hop_is_used() -> None:
    headers = {"x-forwarded-for": " 2001:db8::7 , 172.18.0.2"}
    assert resolve("::1", headers, CADDY) == "2001:db8::7"


def test_garbage_headers_fall_back_to_the_peer() -> None:
    headers = {"cf-connecting-ip": "not an ip", "x-forwarded-for": "nor this"}
    assert resolve("172.18.0.2", headers, CADDY) == "172.18.0.2"
    assert resolve(None, {}, CADDY) == "unknown"
    assert resolve("testclient", {}, CADDY) == "testclient"


def test_bad_trusted_proxy_settings_are_rejected() -> None:
    with pytest.raises(ValueError):
        parse_networks("10.0.0.0/33")
    assert parse_networks(" ") == ()


MESSAGE = EmailMessage(to="ada@example.com", subject="Hi", text="Hello", html="<p>Hello</p>")


def test_the_console_sender_keeps_the_latest_message_per_address() -> None:
    sender = ConsoleEmailSender()
    sender.send(MESSAGE)
    newer = EmailMessage(to="ada@example.com", subject="Again", text="t", html="h")
    sender.send(newer)
    assert sender.latest("ada@example.com") == newer
    assert sender.latest("grace@example.com") is None


class FakeResponse:
    status = 200

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None


def test_resend_gets_the_message_with_the_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def urlopen(request: Any, timeout: float) -> FakeResponse:
        seen.update(
            url=request.full_url,
            auth=request.get_header("Authorization"),
            body=json.loads(request.data),
        )
        return FakeResponse()

    monkeypatch.setattr(email_module.urllib.request, "urlopen", urlopen)
    ResendEmailSender("re_test", "Forgeway <hello@forgeway.dev>").send(MESSAGE)
    assert seen["url"] == "https://api.resend.com/emails"
    assert seen["auth"] == "Bearer re_test"
    assert seen["body"] == {
        "from": "Forgeway <hello@forgeway.dev>",
        "to": ["ada@example.com"],
        "subject": "Hi",
        "text": "Hello",
        "html": "<p>Hello</p>",
    }


def test_the_provider_setting_picks_the_sender() -> None:
    assert isinstance(build_sender("console", None, "x"), ConsoleEmailSender)
    assert isinstance(build_sender("resend", "re_x", "x"), ResendEmailSender)
    with pytest.raises(ValueError):
        build_sender("resend", None, "x")
