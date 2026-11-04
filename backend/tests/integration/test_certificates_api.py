"""HTTP contract for certificates: owner API, public JSON, verification page and image."""

from __future__ import annotations

import io
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import update

from lattice.api.app import create_app
from lattice.application.content_sync import sync_content
from lattice.infrastructure.db.engine import transaction
from lattice.infrastructure.db.models import Certificate
from lattice.settings import Settings
from tests.integration.test_api import ORIGIN, go_pro, sign_up
from tests.integration.test_learning_flow import CORRECT, run_worker_once
from tests.integration.test_progression_flow import catalogue  # noqa: F401

BASE = "https://forgeway.example"
HOSTILE = '"><script>alert(1)</script>'


@pytest.fixture
def client(engine, factory, catalogue, tmp_path) -> Iterator[TestClient]:  # noqa: F811
    with transaction(factory) as session:
        sync_content(session, catalogue.graph)
    settings = Settings(
        content_dir=tmp_path,
        database_url=str(engine.url),
        allowed_origins="",
        log_level="WARNING",
        public_base_url=BASE + "/",
    )
    with TestClient(create_app(settings, engine=engine), headers={"origin": ORIGIN}) as client:
        yield client


def csrf_of(me: dict) -> dict[str, str]:
    return {"x-csrf-token": me["csrf_token"]}


def complete_starter(client: TestClient, factory, catalogue, me: dict) -> None:  # noqa: F811
    for exercise_id in ("starter.one", "starter.two"):
        queued = client.post(
            f"/api/exercises/{exercise_id}/attempts", json={"files": CORRECT}, headers=csrf_of(me)
        )
        assert queued.status_code == 202, queued.text
        run_worker_once(factory, catalogue)


@pytest.fixture
def owned(client, factory, catalogue) -> tuple[dict, dict]:  # noqa: F811
    """A signed-in Pro learner with a completed starter branch: (me, their certificate)."""
    me = sign_up(client)
    go_pro(factory)
    complete_starter(client, factory, catalogue, me)
    (certificate,) = client.get("/api/certificates").json()["certificates"]
    return me, certificate


def publish(client, me, certificate, **body) -> dict:
    response = client.patch(
        f"/api/certificates/{certificate['id']}",
        json={"is_public": True, **body},
        headers=csrf_of(me),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_the_attempt_that_completes_a_branch_reports_the_certificate(client, factory, catalogue):  # noqa: F811
    me = sign_up(client)
    complete_starter(client, factory, catalogue, me)
    (certificate,) = client.get("/api/certificates").json()["certificates"]
    attempts = client.get("/api/exercises/starter.two").json()["recent_attempts"]
    detail = client.get(f"/api/attempts/{attempts[0]['id']}").json()
    assert detail["progression"]["certificates_issued"] == [
        {
            "id": certificate["id"],
            "branch_id": "starter",
            "branch_title": "Starter",
            "includes_capstone": False,
        }
    ]


def test_the_owner_lists_certificates_with_urls_and_linkedin_fields(owned):
    _, certificate = owned
    assert certificate["recipient_name"] == "Ada"
    assert certificate["branch_title"] == "Starter"
    assert certificate["exercise_count"] == 2
    assert certificate["is_public"] is False and certificate["published_at"] is None
    assert certificate["public_url"] == f"{BASE}/c/{certificate['id']}"
    assert certificate["image_url"] == f"{BASE}/c/{certificate['id']}.png"
    issued = certificate["issued_at"]
    assert certificate["linkedin"] == {
        "name": "Forgeway — Starter",
        "organisation": "Forgeway",
        "issue_year": int(issued[:4]),
        "issue_month": int(issued[5:7]),
        "credential_id": certificate["id"],
        "credential_url": certificate["public_url"],
    }


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/api/certificates"), ("patch", "/api/certificates/anything")],
)
def test_the_owner_endpoints_need_a_signed_in_learner(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_changes_need_a_csrf_token_and_a_same_origin_request(client, owned):
    me, certificate = owned
    url = f"/api/certificates/{certificate['id']}"
    assert client.patch(url, json={"is_public": True}).status_code == 403
    cross = client.patch(
        url, json={"is_public": True}, headers={**csrf_of(me), "origin": "https://evil.example"}
    )
    assert cross.status_code == 403


def test_another_learner_gets_404_never_403(client, owned):
    _, certificate = owned
    client.post("/api/auth/logout", headers={"x-csrf-token": owned[0]["csrf_token"]})
    other = sign_up(client, "grace@example.com")
    go_pro(client.app.state.lattice.sessions, "grace@example.com")  # type: ignore[attr-defined]
    assert client.get("/api/certificates").json() == {"certificates": []}
    response = client.patch(
        f"/api/certificates/{certificate['id']}", json={"is_public": True}, headers=csrf_of(other)
    )
    assert response.status_code == 404
    missing = client.patch(
        "/api/certificates/does-not-exist", json={"is_public": True}, headers=csrf_of(other)
    )
    assert (missing.status_code, missing.json()["detail"]) == (404, response.json()["detail"])


def test_publish_and_unpublish_control_the_public_endpoints(client, owned):
    me, certificate = owned
    cid = certificate["id"]
    for path in (f"/api/public/certificates/{cid}", f"/c/{cid}", f"/c/{cid}.png"):
        assert client.get(path).status_code == 404  # private by default

    published = publish(client, me, certificate)
    assert published["is_public"] is True and published["published_at"] is not None
    public = client.get(f"/api/public/certificates/{cid}")
    assert public.status_code == 200
    assert public.headers["cache-control"] == "public, max-age=300"
    assert public.headers["x-content-type-options"] == "nosniff"
    body = public.json()
    assert body["recipient_name"] == "Ada" and body["exercise_count"] == 2
    assert body["url"] == f"{BASE}/c/{cid}" and body["image_url"] == f"{BASE}/c/{cid}.png"
    assert not {"email", "user_id", "display_name"} & body.keys()
    assert "ada@example.com" not in public.text

    unpublished = client.patch(
        f"/api/certificates/{cid}", json={"is_public": False}, headers=csrf_of(me)
    ).json()
    assert unpublished["is_public"] is False and unpublished["published_at"] is None
    assert client.get(f"/api/public/certificates/{cid}").status_code == 404


def test_the_public_endpoints_need_no_sign_in(client, owned):
    me, certificate = owned
    publish(client, me, certificate)
    with TestClient(client.app, headers={"origin": ORIGIN}) as anonymous:
        for suffix in ("", ".png"):
            assert anonymous.get(f"/c/{certificate['id']}{suffix}").status_code == 200
        assert anonymous.get(f"/api/public/certificates/{certificate['id']}").status_code == 200


@pytest.mark.parametrize(
    "name", ["", "   ", "x" * 61, "Ada\nLovelace", "Ada\x00", "Ada\u2028Lovelace"]
)
def test_a_recipient_name_must_be_one_to_sixty_characters_without_control_characters(
    client, owned, name
):
    me, certificate = owned
    response = client.patch(
        f"/api/certificates/{certificate['id']}", json={"recipient_name": name}, headers=csrf_of(me)
    )
    assert response.status_code == 422
    assert client.get("/api/certificates").json()["certificates"][0]["recipient_name"] == "Ada"


def test_the_recipient_name_is_trimmed_and_shown_publicly(client, owned):
    me, certificate = owned
    updated = publish(client, me, certificate, recipient_name="  Ada King-Noel, Countess  ")
    assert updated["recipient_name"] == "Ada King-Noel, Countess"
    page = client.get(f"/c/{certificate['id']}")
    assert "Ada King-Noel, Countess" in page.text


def test_the_page_has_metadata_open_graph_tags_and_absolute_urls(client, owned):
    me, certificate = owned
    publish(client, me, certificate)
    cid = certificate["id"]
    response = client.get(f"/c/{cid}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "public, max-age=300"
    assert response.headers["x-content-type-options"] == "nosniff"
    html = response.text
    for expected in (
        "<title>Ada: Starter certificate | Forgeway</title>",
        '<meta name="description" content="Ada has completed the Starter track on Forgeway: '
        "2 exercises, each graded automatically by sandboxed behavioural checks.",
        '<meta property="og:type" content="website">',
        '<meta property="og:title" content="Ada: Starter certificate | Forgeway">',
        '<meta property="og:description" content="Ada has completed',
        f'<meta property="og:url" content="{BASE}/c/{cid}">',
        f'<meta property="og:image" content="{BASE}/c/{cid}.png">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="627">',
        '<meta property="og:image:alt" content="',
        '<meta name="twitter:card" content="summary_large_image">',
        "has completed the Starter track on Forgeway",
        "2 exercises, each graded automatically by sandboxed behavioural checks.",
        f'<dd class="credential">{cid}</dd>',
        f'<a class="brand" href="{BASE}/">',
        "prefers-color-scheme: dark",
    ):
        assert expected in html, expected
    assert "<script" not in html


def test_a_hostile_name_is_escaped_everywhere_in_the_page(client, owned):
    me, certificate = owned
    publish(client, me, certificate, recipient_name=HOSTILE)
    html = client.get(f"/c/{certificate['id']}").text
    assert "<script>" not in html
    assert HOSTILE not in html
    assert "&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in html
    for tag in ("og:title", "og:description", "og:image:alt"):
        line = next(ln for ln in html.splitlines() if f'property="{tag}"' in ln)
        assert line.count('"') == 4, line  # property="x" content="y": the value cannot break out
    description = next(ln for ln in html.splitlines() if 'name="description"' in ln)
    assert description.count('"') == 4, description


def test_a_missing_or_private_page_is_a_html_404(client, owned):
    _, certificate = owned
    for cid in (certificate["id"], "nope"):
        response = client.get(f"/c/{cid}")
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("text/html")
        assert "Certificate not found" in response.text
        assert response.headers["x-content-type-options"] == "nosniff"
        assert client.get(f"/c/{cid}.png").status_code == 404


def test_the_image_is_a_1200_by_627_png(client, owned):
    me, certificate = owned
    publish(client, me, certificate, recipient_name="Ada " + "Wolfeschlegelstein" * 3)
    response = client.get(f"/c/{certificate['id']}.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "public, max-age=300"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert Image.open(io.BytesIO(response.content)).size == (1200, 627)


def test_the_page_fonts_are_served_from_the_same_origin_and_nothing_else_is(client):
    font = client.get("/c/fonts/SourceSerif4.ttf")
    assert font.status_code == 200
    assert font.headers["content-type"] == "font/ttf"
    assert font.content[:4] == b"\x00\x01\x00\x00"  # a TrueType file
    assert client.get("/c/fonts/JetBrainsMono.ttf").status_code == 200
    assert client.get("/c/fonts/OFL-SourceSerif4.txt").status_code == 404
    assert client.get("/c/fonts/..%2Fimage.py").status_code == 404


def test_the_page_policy_allows_its_own_fonts(client, owned):
    me, certificate = owned
    publish(client, me, certificate)
    policy = client.get(f"/c/{certificate['id']}").headers["content-security-policy"]
    assert "font-src 'self'" in policy and "default-src 'none'" in policy


def test_an_older_certificate_exposes_false_and_renders_without_the_capstone_claim(client, owned):
    """Issued before capstones existed (the column defaults to false), so it must not claim one."""
    me, certificate = owned
    assert certificate["includes_capstone"] is False
    published = publish(client, me, certificate)
    assert published["includes_capstone"] is False
    cid = certificate["id"]
    assert client.get(f"/api/public/certificates/{cid}").json()["includes_capstone"] is False
    html = client.get(f"/c/{cid}").text
    assert "capstone" not in html
    assert "2 exercises, each graded automatically" in html


def test_a_certificate_that_includes_a_capstone_says_so_everywhere(client, factory, owned):
    me, certificate = owned
    publish(client, me, certificate)
    cid = certificate["id"]
    plain = client.get(f"/c/{cid}.png").content
    with transaction(factory) as session:
        session.execute(
            update(Certificate).where(Certificate.id == cid).values(includes_capstone=True)
        )
    assert client.get("/api/certificates").json()["certificates"][0]["includes_capstone"] is True
    assert client.get(f"/api/public/certificates/{cid}").json()["includes_capstone"] is True
    html = client.get(f"/c/{cid}").text
    assert "2 exercises, including its capstone project, each graded automatically" in html
    assert client.get(f"/c/{cid}.png").content != plain
