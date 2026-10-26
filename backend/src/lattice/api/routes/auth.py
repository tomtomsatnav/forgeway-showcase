"""Registration, sign-in, sign-out, the current learner, email verification and password reset.

Per-IP limits key on the real client address (`ClientIp`), counted in Postgres.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Response, status

from lattice.api.deps import (
    SESSION_COOKIE,
    ClientIp,
    CurrentLearner,
    Db,
    MutatingLearner,
    State,
)
from lattice.api.schemas import (
    PROBLEM_RESPONSES,
    EmailChangeRequest,
    LoginRequest,
    Me,
    PasswordResetCheck,
    PasswordResetConfirm,
    PasswordResetRequest,
    Profile,
    ProfileUpdate,
    RegisterRequest,
    VerifyEmailRequest,
)
from lattice.application import accounts
from lattice.application.errors import ChallengeFailedError, ConflictError
from lattice.domain.email import EmailMessage, EmailSender
from lattice.infrastructure.db.models import LearnerProfile, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"], responses=PROBLEM_RESPONSES)
HOUR = timedelta(hours=1)
LOGIN_PER_ACCOUNT = 10  # sign-in attempts per IP and email address, every five minutes
LOGIN_WINDOW = timedelta(minutes=5)
_TOO_MANY_EMAILS = "We have sent several emails already. Check your inbox, or try again later."


def _send(sender: EmailSender, message: EmailMessage) -> None:
    """Runs after the response, so a slow or failing provider never holds up the request (and
    the reset endpoint answers in the same time whether or not the address has an account)."""
    try:
        sender.send(message)
    except Exception:
        logger.exception("email could not be sent", extra={"subject": message.subject})


def _me(db: Db, user: User, csrf_token: str) -> Me:
    profile = db.get(LearnerProfile, user.id)
    assert profile is not None  # noqa: S101 - created with the user
    return Me(
        id=user.id,
        email=user.email,
        email_verified=user.email_verified_at is not None,
        pending_email=user.pending_email,
        display_name=user.display_name,
        plan=user.plan,
        profile=Profile(mode=profile.mode, colour_scheme=profile.colour_scheme),
        csrf_token=csrf_token,
    )


def _start_session(response: Response, db: Db, state: State, user: User) -> Me:
    issued = accounts.issue_session(
        db, user.id, ttl=timedelta(hours=state.settings.session_ttl_hours)
    )
    response.set_cookie(
        SESSION_COOKIE,
        issued.token,
        expires=issued.expires_at,
        httponly=True,
        secure=state.settings.secure_cookies,
        samesite="lax",
        path="/",
    )
    return _me(db, user, issued.csrf_token)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    response: Response,
    background: BackgroundTasks,
    db: Db,
    state: State,
    ip: ClientIp,
) -> Me:
    """Create an account, email a verification link and sign in.

    The new account is unverified: it can explore, but not submit attempts or publish
    certificates, until the link is followed. With Turnstile on, `turnstile_token` must pass.
    """
    if state.turnstile is not None and not state.turnstile.verify(body.turnstile_token, ip):
        raise ChallengeFailedError("We could not confirm you are human. Try the check again.")
    state.limiter.check(
        f"register:ip:{ip}",
        limit=state.settings.register_per_ip_per_hour,
        window=HOUR,
        message="Too many accounts have been created from your network. Try again later.",
    )
    user = accounts.register(
        db,
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        time_zone=body.time_zone or "UTC",
        mode=body.mode or "professional",
        colour_scheme=body.colour_scheme or "system",
    )
    message = accounts.verification_email(db, user, state.settings.public_base_url)
    background.add_task(_send, state.email, message)
    return _start_session(response, db, state, user)


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Db, state: State, ip: ClientIp) -> Me:
    """Sign in with email and password."""
    message = "Too many sign-in attempts. Try again in a few minutes."
    state.limiter.check(
        f"login:ip:{ip}", limit=state.settings.login_per_ip_per_hour, window=HOUR, message=message
    )
    email = accounts.normalise_email(body.email)
    state.limiter.check(
        f"login:ip-email:{ip}:{email}",
        limit=LOGIN_PER_ACCOUNT,
        window=LOGIN_WINDOW,
        message=message,
    )
    state.limiter.check(
        f"login:email:{email}",
        limit=state.settings.login_per_email_per_hour,
        window=HOUR,
        message=message,
    )
    user = accounts.authenticate(db, email=body.email, password=body.password)
    return _start_session(response, db, state, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(learner: MutatingLearner, response: Response, db: Db) -> None:
    accounts.revoke_session(db, learner.token)
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me")
def me(learner: CurrentLearner, db: Db) -> Me:
    return _me(db, learner.user, learner.session.csrf_token)


@router.patch("/profile")
def update_profile(body: ProfileUpdate, learner: MutatingLearner, db: Db) -> Me:
    """Change presentation preferences. These never affect grading or progress."""
    profile = db.get(LearnerProfile, learner.user.id)
    assert profile is not None  # noqa: S101
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(profile, key, value)
    return _me(db, learner.user, learner.session.csrf_token)


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
def verify_email(body: VerifyEmailRequest, db: Db) -> None:
    """Follow a verification link. Works signed in or not; each link works once, for 24 hours."""
    accounts.verify_email(db, body.token)


@router.post("/verify-email/resend", status_code=status.HTTP_202_ACCEPTED)
def resend_verification(
    learner: MutatingLearner, background: BackgroundTasks, db: Db, state: State
) -> Me:
    """Send a fresh verification link (to the pending new address, if there is one). Earlier
    links stop working."""
    user = learner.user
    if user.pending_email is None and user.email_verified_at is not None:
        raise ConflictError("Your email address is already verified.")
    state.limiter.check(
        f"verify-email:user:{user.id}",
        limit=state.settings.verification_emails_per_hour,
        window=HOUR,
        message=_TOO_MANY_EMAILS,
    )
    message = accounts.verification_email(
        db, user, state.settings.public_base_url, to=user.pending_email
    )
    background.add_task(_send, state.email, message)
    return _me(db, user, learner.session.csrf_token)


@router.put("/email", status_code=status.HTTP_202_ACCEPTED)
def change_email(
    body: EmailChangeRequest,
    learner: MutatingLearner,
    background: BackgroundTasks,
    db: Db,
    state: State,
) -> Me:
    """Ask to change the account's address. It changes once the link sent to the new address is
    followed; until then the current one keeps working. Needs the current password."""
    state.limiter.check(
        f"verify-email:user:{learner.user.id}",
        limit=state.settings.verification_emails_per_hour,
        window=HOUR,
        message=_TOO_MANY_EMAILS,
    )
    message = accounts.request_email_change(
        db,
        learner.user,
        new_email=body.email,
        password=body.password,
        base_url=state.settings.public_base_url,
    )
    background.add_task(_send, state.email, message)
    return _me(db, learner.user, learner.session.csrf_token)


@router.post("/password-reset", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(
    body: PasswordResetRequest, background: BackgroundTasks, db: Db, state: State, ip: ClientIp
) -> None:
    """Email a reset link if the address has an account. The answer is the same either way."""
    settings = state.settings
    message = "Too many reset requests. Try again later."
    state.limiter.check(
        f"reset:ip:{ip}", limit=settings.password_reset_per_ip_per_hour, window=HOUR,
        message=message,
    )  # fmt: skip
    state.limiter.check(
        f"reset:email:{accounts.normalise_email(body.email)}",
        limit=settings.password_reset_per_email_per_hour,
        window=HOUR,
        message=message,
    )
    email = accounts.password_reset_email(db, body.email, settings.public_base_url)
    if email is not None:
        background.add_task(_send, state.email, email)


@router.post("/password-reset/check", status_code=status.HTTP_204_NO_CONTENT)
def check_password_reset(body: PasswordResetCheck, db: Db) -> None:
    """204 if a reset link still works, 422 if not, so the page can say so before a new password
    is typed. The token is not consumed."""
    accounts.check_reset_token(db, body.token)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(body: PasswordResetConfirm, response: Response, db: Db) -> None:
    """Set a new password from a reset link (single use, 15 minutes). Every session the account
    has ends, this browser's included: sign in again with the new password."""
    accounts.reset_password(db, body.token, body.password)
    response.delete_cookie(SESSION_COOKIE, path="/")
