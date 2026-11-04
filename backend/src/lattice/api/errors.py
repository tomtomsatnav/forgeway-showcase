"""Map application errors and validation failures to RFC 9457 problem responses."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from lattice.application.errors import (
    ApplicationError,
    ConflictError,
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
    RateLimitedError,
    ServiceBusyError,
    UnauthenticatedError,
)

_STATUS: dict[type[ApplicationError], tuple[int, str]] = {
    NotFoundError: (404, "Not found"),
    ConflictError: (409, "Conflict"),
    ForbiddenError: (403, "Forbidden"),
    InvalidInputError: (422, "Invalid input"),
    RateLimitedError: (429, "Too many requests"),
    UnauthenticatedError: (401, "Unauthenticated"),
    ServiceBusyError: (503, "Service busy"),
}
RETRY_AFTER_S = 60  # sent with 503s: grading capacity frees up within a minute or so

PROBLEM_JSON = "application/problem+json"


def problem(
    status: int, title: str, detail: str, code: str, extensions: dict[str, object] | None = None
) -> JSONResponse:
    body = {"type": "about:blank", "title": title, "status": status, "detail": detail, "code": code}
    body.update(extensions or {})
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)


def install(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def _application_error(_: Request, exc: ApplicationError) -> JSONResponse:
        # The nearest mapped class, so subclasses (e.g. EmailUnverifiedError) keep their status.
        status, title = next(
            (_STATUS[cls] for cls in type(exc).__mro__ if cls in _STATUS), (400, "Bad request")
        )
        response = problem(status, title, exc.detail, exc.code, exc.extensions)
        if status == 503:
            response.headers["Retry-After"] = str(RETRY_AFTER_S)
        return response

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {"loc": (), "msg": "invalid request"}
        where = ".".join(str(p) for p in first["loc"] if p != "body")
        detail = f"{where}: {first['msg']}" if where else str(first["msg"])
        return problem(422, "Invalid input", detail, "invalid-input")
