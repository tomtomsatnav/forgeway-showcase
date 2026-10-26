from datetime import timedelta

import pytest

from lattice.application import accounts
from lattice.application.errors import ConflictError, InvalidInputError, UnauthenticatedError
from lattice.infrastructure.db.engine import transaction

PASSWORD = "correct horse battery"


def register(factory, email="grace@example.com"):
    with transaction(factory) as session:
        return accounts.register(session, email=email, password=PASSWORD, display_name="Grace")


def test_login_is_case_insensitive_on_email(factory):
    user = register(factory)
    with transaction(factory) as session:
        assert (
            accounts.authenticate(session, email=" GRACE@example.com ", password=PASSWORD).id
            == user.id
        )


def test_wrong_password_and_unknown_email_fail_identically(factory):
    register(factory)
    messages = []
    for email, password in [("grace@example.com", "nope-nope-nope"), ("who@example.com", PASSWORD)]:
        with transaction(factory) as session, pytest.raises(UnauthenticatedError) as info:
            accounts.authenticate(session, email=email, password=password)
        messages.append(info.value.detail)
    assert messages[0] == messages[1]


def test_duplicate_email_is_rejected(factory):
    register(factory)
    with pytest.raises(ConflictError):
        register(factory, email="Grace@Example.com")


def test_short_passwords_are_rejected(factory):
    with transaction(factory) as session, pytest.raises(InvalidInputError):
        accounts.register(session, email="a@b.com", password="short", display_name="A")


def test_sessions_resolve_until_expiry_or_revocation(factory):
    user = register(factory)
    with transaction(factory) as session:
        live = accounts.issue_session(session, user.id, ttl=timedelta(hours=1))
        expired = accounts.issue_session(session, user.id, ttl=timedelta(seconds=-1))
    with transaction(factory) as session:
        resolved = accounts.resolve_session(session, live.token)
        assert resolved is not None and resolved[0].id == user.id
        assert accounts.resolve_session(session, expired.token) is None
        assert accounts.resolve_session(session, "forged") is None
        accounts.revoke_session(session, live.token)
    with transaction(factory) as session:
        assert accounts.resolve_session(session, live.token) is None
