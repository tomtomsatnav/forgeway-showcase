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
