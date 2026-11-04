"""Errors raised by use cases. The API maps each to an HTTP problem response."""


class ApplicationError(Exception):
    """Base class. `code` is a stable, machine-readable identifier."""

    code = "error"

    def __init__(self, detail: str, extensions: dict[str, object] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        # Structured fields added to the problem, so a client can phrase the message itself.
        self.extensions = extensions or {}


class NotFoundError(ApplicationError):
    code = "not-found"


class ConflictError(ApplicationError):
    code = "conflict"


class AttemptInFlightError(ConflictError):
    """The learner already has an attempt queued or running."""

    code = "attempt-in-flight"


class ForbiddenError(ApplicationError):
    code = "forbidden"


class InvalidInputError(ApplicationError):
    code = "invalid-input"


class RateLimitedError(ApplicationError):
    code = "rate-limited"


class AttemptCapError(RateLimitedError):
    """The learner has used their graded attempts for the rolling day (extension `limit`)."""

    code = "attempt-daily-cap"


class GradingBudgetError(RateLimitedError):
    """The learner has used their grading time for the rolling day (extension
    `budget_minutes`)."""

    code = "grading-budget"


class UnauthenticatedError(ApplicationError):
    code = "unauthenticated"


class EmailUnverifiedError(ForbiddenError):
    """The action needs a verified email address."""

    code = "email-unverified"


class PlanRequiredError(ForbiddenError):
    """The action is part of Pro, and the learner's plan does not include it."""

    code = "plan-required"


class ChallengeFailedError(ForbiddenError):
    """The human check (Cloudflare Turnstile) did not pass."""

    code = "challenge-failed"


class ServiceBusyError(ApplicationError):
    """The platform as a whole is at capacity; the request may succeed later."""

    code = "busy"


class LiveRunInFlightError(ConflictError):
    """The learner already has a live run queued or running."""

    code = "live-run-in-flight"


class LiveCapError(RateLimitedError):
    """The learner has spent their live-run allowance for the month or the day (extensions
    `scope`, "month", "day", "trial" or "time", and `resets_at`, an ISO 8601 time)."""

    code = "live-cap"


class LiveUnavailableError(ServiceBusyError):
    """Live runs are switched off on this server (no platform key is configured)."""

    code = "live-unavailable"


class BillingUnavailableError(ServiceBusyError):
    """Billing is switched off on this server (no Stripe keys), or its prices failed the check."""

    code = "billing-unavailable"


class ConsentRequiredError(InvalidInputError):
    """Checkout needs the regulation-37 consent, in the current wording, first."""

    code = "consent-required"
