"""In-app live runs: metering maths, spending caps, what the proxy accepts and the provider body."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from lattice.domain.entitlements import Plan
from lattice.domain.live import (
    Allowance,
    CallUsage,
    LiveCall,
    LiveLimits,
    ModelRate,
    ProviderError,
    RunMeter,
    SpendPolicy,
    cost_usd,
)
from lattice.infrastructure.live_anthropic import AnthropicProvider, parse, request_body
from lattice.settings import Settings

HAIKU = ModelRate(
    input=0.10, output=0.50, cache_read=0.01, cache_write=0.125,
    long_above=100_000, long_input=0.50, long_output=2.50,
)  # fmt: skip
POLICY = SpendPolicy(pro_monthly_cap_usd=10.0, daily_fraction=0.1, free_monthly_usd=0.0)


def call(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "messages": [{"role": "user", "content": "hi", "tool_calls": [], "tool_call_id": None}],
        "system": None,
        "max_tokens": 512,
        "temperature": 0.0,
        "tools": [],
        "model": "",
        "response_format": None,
        "tool_choice": "auto",
        "effort": None,
    }
    body.update(overrides)
    return body


# Metering ---------------------------------------------------------------------------------------


def test_a_call_is_priced_per_million_tokens() -> None:
    usage = CallUsage(input_tokens=50_000, output_tokens=10_000)
    assert cost_usd(usage, HAIKU) == pytest.approx((50_000 * 0.10 + 10_000 * 0.50) / 1e6)


def test_cache_reads_and_writes_are_priced_apart_from_fresh_input() -> None:
    usage = CallUsage(
        input_tokens=10_000, output_tokens=0, cache_read_tokens=6_000, cache_write_tokens=2_000
    )
    expected = (2_000 * 0.10 + 6_000 * 0.01 + 2_000 * 0.125) / 1_000_000
    assert cost_usd(usage, HAIKU) == pytest.approx(expected)


def test_prompts_past_100k_tokens_cost_five_times_as_much() -> None:
    short = cost_usd(CallUsage(100_000, 1_000), HAIKU)
    long = cost_usd(CallUsage(100_001, 1_000), HAIKU)
    assert short == pytest.approx((100_000 * 0.10 + 1_000 * 0.50) / 1e6)
    assert long == pytest.approx((100_001 * 0.50 + 1_000 * 2.50) / 1e6)


def test_a_typical_hint_sized_call_costs_under_a_tenth_of_a_cent() -> None:
    assert cost_usd(CallUsage(4_000, 800), HAIKU) < 0.001


# Caps -------------------------------------------------------------------------------------------


def test_pro_may_spend_half_its_price_a_month_and_a_tenth_of_that_a_day() -> None:
    assert POLICY.monthly_cap(Plan.PRO) == pytest.approx(10.0)
    assert POLICY.daily_cap(Plan.PRO) == pytest.approx(1.0)
    assert POLICY.monthly_cap(Plan.TEAM) == pytest.approx(10.0)


def test_the_free_plan_has_no_allowance_unless_one_is_granted() -> None:
    assert POLICY.monthly_cap(Plan.FREE) == 0
    granted = SpendPolicy(10.0, 0.1, free_monthly_usd=0.5)
    assert granted.monthly_cap(Plan.FREE) == pytest.approx(0.5)
    assert granted.daily_cap(Plan.FREE) == pytest.approx(0.05)


NOW = datetime(2026, 11, 3, 15, 30, tzinfo=UTC)


def test_the_daily_cap_resets_at_the_next_utc_midnight() -> None:
    spent = Allowance(10.0, 3.0, 1.0, 1.0, NOW)
    assert spent.exhausted == "day"
    assert spent.remaining_usd == 0
    assert spent.resets_at == datetime(2026, 11, 4, tzinfo=UTC)


def test_the_monthly_cap_resets_on_the_first_of_next_month() -> None:
    spent = Allowance(10.0, 10.0, 1.0, 0.2, NOW)
    assert spent.exhausted == "month"
    assert spent.resets_at == datetime(2026, 12, 1, tzinfo=UTC)
    december = Allowance(10.0, 10.0, 1.0, 0.0, datetime(2026, 12, 31, 23, tzinfo=UTC))
    assert december.resets_at == datetime(2027, 1, 1, tzinfo=UTC)


def test_the_remaining_allowance_is_the_tighter_of_month_and_day() -> None:
    assert Allowance(10.0, 9.5, 1.0, 0.1, NOW).remaining_usd == pytest.approx(0.5)
    assert Allowance(10.0, 1.0, 1.0, 0.7, NOW).remaining_usd == pytest.approx(0.3)
    assert Allowance(10.0, 1.0, 1.0, 0.7, NOW).exhausted is None


def test_a_run_stops_calling_at_its_call_and_token_limits() -> None:
    meter = RunMeter(LiveLimits(max_calls=2, max_tokens=100, max_output_tokens_per_call=10,
                                timeout_s=30))  # fmt: skip
    assert meter.refusal() is None
    meter.calls = 2
    assert "2 model calls" in (meter.refusal() or "")
    meter.calls, meter.tokens = 0, 100
    assert "100 tokens" in (meter.refusal() or "")


# What the proxy accepts -------------------------------------------------------------------------


def test_a_well_formed_toolkit_call_is_accepted() -> None:
    accepted = LiveCall.model_validate(
        call(
            tools=[{"name": "lookup", "description": "d", "input_schema": {"type": "object"}}],
            tool_choice={"name": "lookup"},
            effort="low",
            response_format={"type": "object"},
        )
    )
    assert accepted.tools[0].name == "lookup"


@pytest.mark.parametrize(
    "hostile",
    [
        call(url="https://evil.example"),  # an extra field: nothing unnamed reaches the provider
        call(api_key="sk-ant-anything"),
        call(messages=[]),
        call(messages=[{"role": "system", "content": "x"}]),
        call(messages=[{"role": "user", "content": "x", "betas": ["anything"]}]),
        call(messages=[{"role": "user", "content": 7}]),
        call(messages=[{"role": "tool", "content": "x"}]),  # no tool_call_id
        call(max_tokens=0),
        call(max_tokens="512"),
        call(tool_choice="required"),
        call(tool_choice={"name": "x", "type": "any"}),
        call(effort="max"),
        call(messages=[{"role": "user", "content": "x" * 200_001}]),
        call(tools=[{"name": "t", "description": "d", "input_schema": {}}] * 65),
        call(messages=[{"role": "user", "content": "x"}] * 201),
    ],
)
def test_anything_else_is_refused(hostile: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        LiveCall.model_validate(hostile)


# The provider body ------------------------------------------------------------------------------


def test_the_model_is_forced_and_max_tokens_clamped() -> None:
    body = request_body(
        LiveCall.model_validate(call(model="claude-fable-5-1", max_tokens=99_999)),
        model="claude-haiku-5-5",
        max_tokens=1024,
    )
    assert body["model"] == "claude-haiku-5-5"
    assert body["max_tokens"] == 1024
    small = request_body(LiveCall.model_validate(call(max_tokens=50)), model="m", max_tokens=1024)
    assert small["max_tokens"] == 50


def test_the_body_carries_only_named_fields() -> None:
    body = request_body(
        LiveCall.model_validate(
            call(
                system="be brief",
                temperature=0.7,
                messages=[
                    {"role": "user", "content": "weather?"},
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{"id": "t1", "name": "w", "arguments": {"c": "Leeds"}}],
                    },
                    {"role": "tool", "content": "rain", "tool_call_id": "t1"},
                ],
                tools=[{"name": "w", "description": "d", "input_schema": {"type": "object"}}],
                effort="low",
            )
        ),
        model="claude-haiku-5-5",
        max_tokens=256,
    )
    assert set(body) == {
        "model", "max_tokens", "messages", "system", "tools", "tool_choice", "output_config"
    }  # fmt: skip
    assert "temperature" not in json.dumps(body)
    assert body["messages"][1]["content"] == [
        {"type": "tool_use", "id": "t1", "name": "w", "input": {"c": "Leeds"}}
    ]
    assert body["messages"][2] == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "rain"}],
    }
    assert body["output_config"] == {"effort": "low"}


def test_a_response_becomes_the_toolkit_completion_with_cache_tokens_counted() -> None:
    reply = parse(
        {
            "model": "claude-haiku-5-5",
            "stop_reason": "tool_use",
            "content": [
                {"type": "thinking", "thinking": ""},
                {"type": "text", "text": "Checking."},
                {"type": "tool_use", "id": "t1", "name": "w", "input": {"c": "Leeds"}},
            ],
            "usage": {
                "input_tokens": 100,
                "cache_read_input_tokens": 900,
                "cache_creation_input_tokens": 50,
                "output_tokens": 20,
            },
        },
        123,
        fallback_model="claude-haiku-5-5",
    )
    assert reply.usage == CallUsage(1050, 20, 900, 50)
    assert reply.completion["text"] == "Checking."
    assert reply.completion["stop_reason"] == "tool_use"
    assert reply.completion["tool_calls"] == [
        {"id": "t1", "name": "w", "arguments": {"c": "Leeds"}}
    ]
    assert reply.completion["usage"]["input_tokens"] == 1050


# Settings ---------------------------------------------------------------------------------------


BILLING = {
    "stripe_secret_key": "sk_test",
    "stripe_webhook_secret": "whsec_test",
    "stripe_price_monthly": "price_m",
    "stripe_price_annual": "price_a",
}


def test_the_pro_cap_follows_what_the_learner_pays() -> None:
    policy = Settings(_env_file=None, **BILLING).live_config().policy  # type: ignore[call-arg, arg-type]
    assert policy.monthly_cap(Plan.PRO, "monthly") == pytest.approx(19 * 1.27 * 0.5)
    assert policy.monthly_cap(Plan.PRO, "annual") == pytest.approx(190 / 12 * 1.27 * 0.5)
    assert policy.daily_cap(Plan.PRO, "monthly") == pytest.approx(19 * 1.27 * 0.5 * 0.1)
    assert policy.monthly_cap(Plan.PRO) == 10.0  # granted by hand: no price behind it
    assert policy.monthly_cap(Plan.FREE, "monthly") == 0.0
    custom = Settings(  # type: ignore[call-arg]
        _env_file=None, **BILLING, gbp_to_usd=2.0, live_spend_cap_fraction=0.25,  # type: ignore[arg-type]
        billing_monthly_price_minor=1000,
    ).live_config().policy  # fmt: skip
    assert custom.monthly_cap(Plan.PRO, "monthly") == pytest.approx(5.0)


def test_without_billing_the_explicit_cap_applies_whatever_the_interval() -> None:
    settings = Settings(_env_file=None, live_pro_monthly_cap_usd=3.0)  # type: ignore[call-arg]
    assert settings.live_config().policy.monthly_cap(Plan.PRO, "monthly") == 3.0


def test_the_provider_call_times_out_with_what_is_left_of_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[float] = []

    def refuse(_request: object, *, timeout: float) -> None:
        seen.append(timeout)
        raise TimeoutError

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    provider = AnthropicProvider("key", "https://provider.test", timeout_s=60.0)
    request = LiveCall.model_validate(call())
    for left, expected in ((7.5, 7.5), (500.0, 60.0), (None, 60.0)):
        with pytest.raises(ProviderError):
            provider.complete(request, model="m", max_tokens=1, timeout_s=left)
        assert seen[-1] == expected


def test_live_runs_are_off_without_a_key_and_default_to_haiku() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.live_enabled is False
    config = settings.live_config()
    assert config.model == "claude-haiku-5-5"
    assert config.rate.input == pytest.approx(0.10)
    assert config.policy.monthly_cap(Plan.PRO) == pytest.approx(10.0)
    assert config.policy.daily_cap(Plan.PRO) == pytest.approx(1.0)


def test_the_live_model_must_be_on_the_rate_card() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, live_model="claude-unpriced")  # type: ignore[call-arg]


def test_the_key_never_shows_in_the_settings_repr() -> None:
    settings = Settings(_env_file=None, live_anthropic_api_key="sk-ant-secret")  # type: ignore[call-arg]
    assert settings.live_enabled
    assert "sk-ant-secret" not in repr(settings)
