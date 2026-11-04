"""Compliance guards that need no database: production refuses development-only settings,
billing refuses to start without the trader's address, and the 2027 renewal cooling-off."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from lattice.api.routes.billing import build_billing
from lattice.application import billing as billing_app
from lattice.domain.billing import renewal_cooling_off_deadline
from lattice.infrastructure.db.models import Subscription
from lattice.settings import Settings

PROD: dict[str, Any] = {
    "environment": "production",
    "email_provider": "resend",
    "resend_api_key": "re_x",
    "secure_cookies": True,
}
BILLING: dict[str, Any] = {
    "stripe_secret_key": "sk_test_x",
    "stripe_webhook_secret": "whsec_x",
    "stripe_price_monthly": "price_m",
    "stripe_price_annual": "price_a",
}


def settings(**values: Any) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


def test_production_refuses_the_console_email_provider() -> None:
    with pytest.raises(ValidationError, match="console"):
        settings(**PROD | {"email_provider": "console"})
    assert settings(email_provider="console").environment == "development"  # fine locally


def test_production_refuses_insecure_cookies() -> None:
    with pytest.raises(ValidationError, match="SECURE_COOKIES"):
        settings(**PROD | {"secure_cookies": False})
    assert settings(**PROD).secure_cookies is True


@pytest.mark.parametrize("address", [None, "", "  "])
def test_billing_stays_off_without_the_trader_address(
    address: str | None, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        assert build_billing(settings(**BILLING, trader_address=address)) is None
    assert any("LATTICE_TRADER_ADDRESS" in r.getMessage() for r in caplog.records)


def test_billing_starts_once_the_trader_address_is_set() -> None:
    assert build_billing(settings(**BILLING, trader_address="1 Example St, London")) is not None


# --- The renewal cooling-off (DMCC Act 2024, from 1 January 2027) ----------------------------

DAY = timedelta(days=1)
JAN = datetime(2027, 1, 10, tzinfo=UTC)


def deadline(now: datetime, **kw: Any) -> datetime | None:
    values: dict[str, Any] = {
        "started_at": JAN - DAY * 7,
        "trial_end": JAN,
        "interval": "monthly",
        "current_period_end": JAN + DAY * 30,
    } | kw
    return renewal_cooling_off_deadline(now=now, **values)


def test_cooling_off_runs_14_days_from_the_trial_converting() -> None:
    assert deadline(JAN + DAY) == JAN + DAY * 14
    assert deadline(JAN + DAY * 14) is None
    assert deadline(JAN - DAY) is None  # still in the trial


def test_there_is_no_renewal_cooling_off_before_2027() -> None:
    dec = datetime(2026, 12, 1, tzinfo=UTC)
    assert deadline(dec + DAY, started_at=dec - DAY * 7, trial_end=dec) is None


def test_an_annual_renewal_opens_a_cooling_off_but_a_monthly_one_does_not() -> None:
    renewed = datetime(2028, 3, 1, tzinfo=UTC)
    annual = {"started_at": renewed - DAY * 366, "trial_end": None, "interval": "annual"}
    assert deadline(renewed + DAY * 3, current_period_end=datetime(2029, 3, 1, tzinfo=UTC),
                    **annual) == renewed + DAY * 14  # fmt: skip
    monthly = annual | {"interval": "monthly"}
    assert deadline(renewed + DAY * 3, current_period_end=renewed + DAY * 30, **monthly) is None


def test_the_first_paid_year_without_a_trial_is_covered_by_the_waiver_not_cooling_off() -> None:
    start = datetime(2027, 2, 1, tzinfo=UTC)
    first_year = {"started_at": start, "trial_end": None, "interval": "annual"}
    assert deadline(start + DAY, current_period_end=datetime(2028, 2, 1, tzinfo=UTC),
                    **first_year) is None  # fmt: skip


def test_the_withdraw_control_opens_for_a_uk_customer_after_the_trial_converts() -> None:
    row = Subscription(
        status="active", country="GB", started_at=JAN - DAY * 7, trial_end=JAN,
        interval="annual", current_period_end=datetime(2028, 1, 10, tzinfo=UTC),
    )  # fmt: skip
    assert billing_app._withdrawal_until(row, JAN + DAY) == JAN + DAY * 14
    row.status = "trialing"
    assert billing_app._withdrawal_until(row, JAN - DAY) is None
