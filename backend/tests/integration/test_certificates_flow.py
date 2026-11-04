"""Certificate issuing against a real database: on completion, once, lazily and as a snapshot."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import delete, select, update

from lattice.application import accounts, certificates, grading
from lattice.application.content_sync import sync_content
from lattice.application.errors import NotFoundError
from lattice.infrastructure.content_loader import load_catalogue
from lattice.infrastructure.db.engine import transaction
from lattice.infrastructure.db.models import Certificate, User
from tests.content_factory import write_branch, write_exercise
from tests.fakes import ScriptedRunner
from tests.integration.test_learning_flow import CORRECT, attempt_row, submit
from tests.integration.test_progression_flow import (  # noqa: F401
    catalogue,
    learner,
    pass_everything,
    pass_exercise,
)


def issued(factory, user_id) -> list[Certificate]:
    with factory() as session:
        return list(
            session.scalars(select(Certificate).where(Certificate.user_id == user_id)).all()
        )


def test_a_certificate_is_issued_when_the_last_exercise_passes_and_not_before(
    factory,
    catalogue,  # noqa: F811
    learner,  # noqa: F811
):
    first = pass_exercise(factory, catalogue, learner, "starter.one")
    assert issued(factory, learner) == []
    assert attempt_row(factory, first).report["progression"]["certificates_issued"] == []

    last = pass_exercise(factory, catalogue, learner, "starter.two")
    (certificate,) = issued(factory, learner)
    assert certificate.branch_id == "starter"
    assert certificate.attempt_id == last
    assert (certificate.recipient_name, certificate.branch_title) == ("Ada", "Starter")
    assert certificate.exercise_count == 2
    assert not certificate.is_public and certificate.published_at is None
    assert len(certificate.id) >= 22  # 128 bits, URL-safe
    assert attempt_row(factory, last).report["progression"]["certificates_issued"] == [
        {
            "id": certificate.id,
            "branch_id": "starter",
            "branch_title": "Starter",
            "includes_capstone": False,
        }
    ]

    pass_exercise(factory, catalogue, learner, "retrieval.chunking")
    assert sorted(c.branch_id for c in issued(factory, learner)) == ["retrieval", "starter"]


def test_a_failed_attempt_issues_nothing(factory, catalogue, learner):  # noqa: F811
    pass_exercise(factory, catalogue, learner, "starter.one")
    wrong = {"solution_mod.py": "def add(a, b):\n    return a - b\n"}
    attempt_id = submit(factory, catalogue, learner, "starter.two", wrong)
    with transaction(factory) as session:
        claimed = grading.claim_next(session, "w")
    report = grading.grade(claimed, catalogue, ScriptedRunner())
    with transaction(factory) as session:
        grading.record_grade(session, catalogue, attempt_id, report, free_per_branch=3)
    assert issued(factory, learner) == []


def test_processing_a_report_again_or_repassing_never_duplicates_a_certificate(
    factory,
    catalogue,  # noqa: F811
    learner,  # noqa: F811
):
    pass_exercise(factory, catalogue, learner, "starter.one")
    attempt_id = submit(factory, catalogue, learner, "starter.two", CORRECT)
    with transaction(factory) as session:
        claimed = grading.claim_next(session, "w")
    report = grading.grade(claimed, catalogue, ScriptedRunner())
    for _ in range(2):  # a worker retry delivers the same report twice
        with transaction(factory) as session:
            grading.record_grade(session, catalogue, attempt_id, report, free_per_branch=3)
    (certificate,) = issued(factory, learner)

    again = pass_exercise(factory, catalogue, learner, "starter.two")  # a repeat pass
    assert [c.id for c in issued(factory, learner)] == [certificate.id]
    assert attempt_row(factory, again).report["progression"]["certificates_issued"] == []


def test_listing_issues_missing_certificates_for_completed_branches_once(
    factory,
    catalogue,  # noqa: F811
    learner,  # noqa: F811
):
    pass_everything(factory, catalogue, learner)
    with transaction(factory) as session:  # as if the learner finished before certificates existed
        session.execute(delete(Certificate))

    for _ in range(2):
        with transaction(factory) as session:
            listed = certificates.list_certificates(session, catalogue, learner)
    assert sorted(c.branch_id for c in listed) == ["retrieval", "starter"]
    assert all(c.attempt_id is None for c in listed)
    assert len(issued(factory, learner)) == 2
    assert [c.issued_at for c in listed] == sorted((c.issued_at for c in listed), reverse=True)


def test_listing_does_not_issue_for_incomplete_branches(factory, catalogue, learner):  # noqa: F811
    pass_exercise(factory, catalogue, learner, "starter.one")
    with transaction(factory) as session:
        assert certificates.list_certificates(session, catalogue, learner) == []


def test_a_certificate_is_a_snapshot_that_content_and_account_changes_do_not_touch(
    factory,
    catalogue,  # noqa: F811
    learner,  # noqa: F811
    tmp_path: Path,
):
    pass_exercise(factory, catalogue, learner, "starter.one")
    pass_exercise(factory, catalogue, learner, "starter.two")
    (before,) = issued(factory, learner)

    write_branch(tmp_path, "starter", order=0, title="Renamed")
    write_exercise(tmp_path, "starter", "three", prerequisites=["starter.two"])
    grown = load_catalogue(tmp_path)
    with transaction(factory) as session:
        session.execute(update(User).where(User.id == learner).values(display_name="Someone else"))
        listed = certificates.list_certificates(session, grown, learner)

    (after,) = listed  # the branch is no longer complete, yet the certificate stands
    assert (after.id, after.recipient_name, after.branch_title, after.exercise_count) == (
        before.id,
        "Ada",
        "Starter",
        2,
    )


def test_the_recipient_name_snapshot_is_always_valid(factory, catalogue, learner):  # noqa: F811
    with transaction(factory) as session:
        session.execute(
            update(User)
            .where(User.id == learner)
            .values(display_name="  Ada\nLovelace " + "x" * 40)
        )
    pass_exercise(factory, catalogue, learner, "starter.one")
    pass_exercise(factory, catalogue, learner, "starter.two")
    (certificate,) = issued(factory, learner)
    assert certificate.recipient_name == "AdaLovelace " + "x" * 40


def test_only_the_owner_can_edit_and_only_public_ones_are_visible(
    factory,
    catalogue,  # noqa: F811
    learner,  # noqa: F811
):
    pass_exercise(factory, catalogue, learner, "starter.one")
    pass_exercise(factory, catalogue, learner, "starter.two")
    (certificate,) = issued(factory, learner)
    with transaction(factory) as session:
        with pytest.raises(NotFoundError):
            certificates.update_certificate(session, uuid.uuid4(), certificate.id, is_public=True)
        with pytest.raises(NotFoundError):
            certificates.public_certificate(session, certificate.id)
        updated = certificates.update_certificate(
            session, learner, certificate.id, is_public=True, recipient_name="  Ada L.  "
        )
        assert updated.is_public and updated.published_at is not None
        assert updated.recipient_name == "Ada L."
        assert certificates.public_certificate(session, certificate.id).id == certificate.id
        again = certificates.update_certificate(session, learner, certificate.id, is_public=False)
        assert not again.is_public and again.published_at is None


@pytest.fixture
def capstone_catalogue(tmp_path: Path):
    """Starter has no capstone. Retrieval does: chunking, then the capstone project."""
    write_branch(tmp_path, "starter", order=0)
    write_branch(tmp_path, "retrieval", order=1, requires=["starter"])
    write_exercise(tmp_path, "starter", "one", xp=50)
    write_exercise(tmp_path, "retrieval", "chunking", xp=100)
    write_exercise(
        tmp_path,
        "retrieval",
        "project",
        tier="capstone",
        xp=300,
        prerequisites=["retrieval.chunking"],
    )
    return load_catalogue(tmp_path)


def test_a_certificate_records_whether_its_branch_has_a_capstone(factory, capstone_catalogue):
    with transaction(factory) as session:
        sync_content(session, capstone_catalogue.graph)
        user = accounts.register(
            session, email="ada@example.com", password="correct horse battery", display_name="Ada"
        )
        user.plan = "pro"  # capstones are Pro
        learner_id = user.id
    for exercise_id in ("starter.one", "retrieval.chunking"):
        pass_exercise(factory, capstone_catalogue, learner_id, exercise_id)
    # The capstone is still open, so the retrieval branch is incomplete and has no certificate.
    assert [c.branch_id for c in issued(factory, learner_id)] == ["starter"]

    pass_exercise(factory, capstone_catalogue, learner_id, "retrieval.project")
    by_branch = {c.branch_id: c for c in issued(factory, learner_id)}
    assert by_branch["starter"].includes_capstone is False
    assert by_branch["retrieval"].includes_capstone is True
    assert by_branch["retrieval"].exercise_count == 2
