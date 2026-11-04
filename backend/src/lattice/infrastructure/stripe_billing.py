"""`BillingGateway` over the official Stripe SDK (docs/plans/billing.md).

Everything Stripe-shaped stays here: request parameters, response fields and the API version's
quirks (in the `clover` API a subscription's period end is on its items, and an invoice names its
subscription under `parent.subscription_details`). The rest of the app sees plain snapshots.

Responses are read as mappings (`StripeObject` is a dict), so tests can hand back plain dicts
from a mocked client. Nothing here is called with billing off.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

import stripe

from lattice.domain.billing import (
    BillingEvent,
    CheckoutRequest,
    CheckoutSnapshot,
    Interval,
    InvalidSignatureError,
    InvoiceSnapshot,
    PriceSnapshot,
    SubscriptionSnapshot,
)

_INTERVALS: dict[str, Interval] = {"month": "monthly", "year": "annual"}


class StripeGateway:
    def __init__(self, client: Any, webhook_secret: str) -> None:
        """`client` is a `stripe.StripeClient` (a mock in tests)."""
        self._v1 = client.v1
        self._webhook_secret = webhook_secret

    @classmethod
    def from_keys(cls, secret_key: str, webhook_secret: str) -> StripeGateway:
        return cls(stripe.StripeClient(secret_key, max_network_retries=2), webhook_secret)

    def verify_event(self, payload: bytes, signature: str) -> BillingEvent:
        """Check the `Stripe-Signature` header against the raw body, then read the event."""
        try:
            text = payload.decode("utf-8")
            # The tolerance refuses replays; without it the SDK checks no timestamp at all.
            stripe.WebhookSignature.verify_header(  # type: ignore[no-untyped-call]
                text, signature, self._webhook_secret, stripe.Webhook.DEFAULT_TOLERANCE
            )
            event = json.loads(text)
        except (stripe.SignatureVerificationError, UnicodeDecodeError, ValueError) as err:
            raise InvalidSignatureError(str(err)) from err
        obj: Mapping[str, Any] = event.get("data", {}).get("object", {})
        kind = str(obj.get("object", ""))
        subscription = (
            obj.get("id")
            if kind == "subscription"
            else obj.get("subscription")
            if kind == "checkout.session"
            else _invoice_subscription(obj)
            if kind == "invoice"
            else None
        )
        return BillingEvent(
            id=str(event["id"]),
            type=str(event["type"]),
            object_id=_id(obj.get("id")),
            customer_id=_id(obj.get("customer")),
            subscription_id=_id(subscription),
        )

    def create_customer(self, user_id: str, email: str, name: str) -> str:
        customer = self._v1.customers.create(
            params={"email": email, "name": name, "metadata": {"user_id": user_id}},
            # Two tabs racing to Checkout make one customer, not two.
            options={"idempotency_key": f"forgeway-customer-{user_id}"},
        )
        return str(customer["id"])

    def create_checkout(self, request: CheckoutRequest) -> tuple[str, str]:
        session = self._v1.checkout.sessions.create(params=checkout_params(request))
        return str(session["id"]), str(session["url"])

    def create_portal(self, customer_id: str, return_url: str) -> str:
        portal = self._v1.billing_portal.sessions.create(
            params={"customer": customer_id, "return_url": return_url}
        )
        return str(portal["url"])

    def checkout_session(self, session_id: str) -> CheckoutSnapshot:
        session = self._v1.checkout.sessions.retrieve(session_id)
        details = session.get("customer_details") or {}
        address = details.get("address") or {}
        return CheckoutSnapshot(
            id=str(session["id"]),
            customer_id=_id(session.get("customer")),
            subscription_id=_id(session.get("subscription")),
            client_reference_id=session.get("client_reference_id"),
            country=address.get("country"),
        )

    def subscription(self, subscription_id: str) -> SubscriptionSnapshot:
        return _subscription(self._v1.subscriptions.retrieve(subscription_id))

    def invoice(self, invoice_id: str) -> InvoiceSnapshot:
        return _invoice(self._v1.invoices.retrieve(invoice_id))

    def paid_invoices(self, subscription_id: str, since: datetime) -> list[InvoiceSnapshot]:
        # shortcut: one page of 100, far more than a 14-day window can hold.
        page = self._v1.invoices.list(
            params={
                "subscription": subscription_id,
                "status": "paid",
                "created": {"gte": int(since.timestamp())},
                "limit": 100,
            }
        )
        return [_invoice(invoice) for invoice in page.get("data") or []]

    def price(self, price_id: str) -> PriceSnapshot:
        price = self._v1.prices.retrieve(price_id)
        recurring = price.get("recurring") or {}
        return PriceSnapshot(
            id=str(price["id"]),
            unit_amount=price.get("unit_amount"),
            currency=str(price.get("currency", "")),
            tax_behavior=price.get("tax_behavior"),
            interval=recurring.get("interval"),
            active=bool(price.get("active")),
        )

    def pause(self, subscription_id: str, resumes_at: datetime) -> SubscriptionSnapshot:
        # `void`: invoices that fall due while paused are voided, so nothing is charged.
        return _subscription(
            self._v1.subscriptions.update(
                subscription_id,
                params={
                    "pause_collection": {
                        "behavior": "void",
                        "resumes_at": int(resumes_at.timestamp()),
                    }
                },
            )
        )

    def resume(self, subscription_id: str) -> SubscriptionSnapshot:
        # An empty value unsets the field: collection resumes at once.
        params = cast(Any, {"pause_collection": ""})
        return _subscription(self._v1.subscriptions.update(subscription_id, params=params))

    def cancel_now(self, subscription_id: str) -> SubscriptionSnapshot:
        return _subscription(self._v1.subscriptions.cancel(subscription_id))

    def refund_invoice(self, invoice_id: str, amount: int) -> None:
        # A credit note with a refund keeps the invoice, the refund and the VAT record together.
        self._v1.credit_notes.create(
            params={
                "invoice": invoice_id,
                "amount": amount,
                "refund_amount": amount,
                "memo": "Withdrawal from the contract",
            },
            # A retried withdrawal refunds each invoice once.
            options={"idempotency_key": f"withdraw-{invoice_id}"},
        )


def checkout_params(request: CheckoutRequest) -> dict[str, Any]:
    """The Checkout Session for a subscription: hosted, tax-inclusive prices with Stripe Tax, the
    learner's own customer, and either a trial or promotion codes, never both."""
    subscription_data: dict[str, Any] = {"metadata": {"user_id": request.user_id}}
    if request.trial_days > 0:
        subscription_data["trial_period_days"] = request.trial_days
    return {
        "mode": "subscription",
        "customer": request.customer_id,
        "client_reference_id": request.user_id,
        "line_items": [{"price": request.price_id, "quantity": 1}],
        "subscription_data": subscription_data,
        "payment_method_collection": "always",  # card required, trial or not
        "customer_update": {"address": "auto", "name": "auto"},
        "automatic_tax": {"enabled": True},
        "tax_id_collection": {"enabled": True},
        # A promotion code is for campaigns and win-back; never with a trial in one session.
        "allow_promotion_codes": request.trial_days == 0,
        "custom_text": {"submit": {"message": request.submit_message}},
        "success_url": request.success_url,
        "cancel_url": request.cancel_url,
        "locale": "en-GB",
    }


def _subscription(sub: Mapping[str, Any]) -> SubscriptionSnapshot:
    items = (sub.get("items") or {}).get("data") or [{}]
    item = items[0]
    price = item.get("price") or {}
    recurring = price.get("recurring") or {}
    pause = sub.get("pause_collection")
    metadata = sub.get("metadata") or {}
    return SubscriptionSnapshot(
        id=str(sub["id"]),
        customer_id=str(_id(sub.get("customer"))),
        status=str(sub.get("status")),
        price_id=price.get("id"),
        interval=_INTERVALS.get(str(recurring.get("interval"))),
        started_at=_time(sub.get("start_date")) or datetime.now(UTC),
        trial_end=_time(sub.get("trial_end")),
        current_period_end=_time(item.get("current_period_end") or sub.get("current_period_end")),
        cancel_at_period_end=bool(sub.get("cancel_at_period_end")),
        cancel_at=_time(sub.get("cancel_at")),
        paused=bool(pause),
        resumes_at=_time(pause.get("resumes_at")) if pause else None,
        latest_invoice_id=_id(sub.get("latest_invoice")),
        user_id=metadata.get("user_id"),
    )


def _invoice(invoice: Mapping[str, Any]) -> InvoiceSnapshot:
    return InvoiceSnapshot(
        id=str(invoice["id"]),
        subscription_id=_id(_invoice_subscription(invoice)),
        status=invoice.get("status"),
        amount_paid=int(invoice.get("amount_paid") or 0),
        hosted_invoice_url=invoice.get("hosted_invoice_url"),
    )


def _invoice_subscription(invoice: Mapping[str, Any]) -> Any:
    parent = invoice.get("parent") or {}
    details = parent.get("subscription_details") or {}
    return details.get("subscription") or invoice.get("subscription")


def _id(value: Any) -> str | None:
    """An id, whether the field holds the id or an expanded object."""
    if value is None or value == "":
        return None
    if isinstance(value, Mapping):
        return str(value.get("id"))
    return str(value)


def _time(value: Any) -> datetime | None:
    return None if value is None else datetime.fromtimestamp(int(value), UTC)
