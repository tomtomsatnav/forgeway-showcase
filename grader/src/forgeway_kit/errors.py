"""Errors a model client can raise, mirroring the categories real provider SDKs use."""


class ModelError(Exception):
    """Base class for model API errors."""


class RateLimitError(ModelError):
    """The provider asked us to slow down. Safe to retry after a delay."""

    def __init__(self, message: str = "rate limited", retry_after_s: float = 1.0) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class ServerError(ModelError):
    """A transient provider-side failure. Usually safe to retry."""


class InvalidRequestError(ModelError):
    """The request itself is wrong (for example, too many tokens). Retrying will not help."""
