"""Local live mode: the exercise download and the forgeway-kit wheel, through the API."""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from lattice.api.app import create_app
from lattice.application.content_sync import sync_content
from lattice.application.local_live import is_shippable
from lattice.infrastructure.content_loader import ContentCatalogue, load_catalogue
from lattice.infrastructure.db.engine import transaction
from lattice.infrastructure.db.models import Draft, User
from lattice.settings import Settings
from tests.content_factory import write_branch, write_exercise
from tests.integration.test_api import ORIGIN, go_pro, sign_up

LIVE = "from forgeway_kit import default_client\nprint(default_client())\n"
STARTER = "def add(a, b):\n    raise NotImplementedError\n"
WHEEL = "forgeway_kit-2.0.0-py3-none-any.whl"
GUIDE = "# Live mode: run your code against a real model\n\nThe guide.\n"


@pytest.fixture
def catalogue(tmp_path: Path) -> ContentCatalogue:
    """Starter: one (with live.py and notes.md). Retrieval: a (free), b (Pro past the allowance
    of one)."""
    content = tmp_path / "content"
    write_branch(content, "starter", order=0)
    write_branch(content, "retrieval", order=1, requires=["starter"])
    one = write_exercise(content, "starter", "one")
    (one / "live.py").write_text(LIVE)
    (one / "notes.md").write_text("the solution adds\n")
    write_exercise(content, "retrieval", "a")
    write_exercise(content, "retrieval", "b", prerequisites=["retrieval.a"])
    return load_catalogue(content)


@pytest.fixture
def kit_dir(tmp_path: Path) -> Path:
    kit = tmp_path / "kit"
    kit.mkdir()
    (kit / WHEEL).write_bytes(b"PK wheel bytes")
    (tmp_path / "secret.txt").write_text("not for download")
    return kit


@pytest.fixture
def guide(tmp_path: Path) -> Path:
    path = tmp_path / "live-mode.md"
    path.write_text(GUIDE)
    return path


@pytest.fixture
def client(engine, factory, catalogue, kit_dir, guide, tmp_path) -> Iterator[TestClient]:
    with transaction(factory) as session:
        sync_content(session, catalogue.graph)
    settings = Settings(
        content_dir=tmp_path / "content",
        kit_dir=kit_dir,
        live_mode_guide=guide,
        public_base_url="https://forgeway.example",
        database_url=engine.url.render_as_string(hide_password=False),
        allowed_origins="",
        log_level="WARNING",
        free_exercises_per_branch=1,
    )
    with TestClient(create_app(settings, engine=engine), headers={"origin": ORIGIN}) as client:
        yield client


def unzip(response) -> dict[str, str]:
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        return {name: archive.read(name).decode() for name in archive.namelist()}


def test_a_free_learner_cannot_download_pro_content(client, factory):
    sign_up(client)
    denied = client.get("/api/exercises/retrieval.b/download")
    assert denied.status_code == 403
    assert denied.json()["code"] == "plan-required"
    go_pro(factory)
    assert unzip(client.get("/api/exercises/retrieval.b/download"))


def test_downloading_is_rate_limited_per_account(client, monkeypatch):
    monkeypatch.setattr("lattice.api.routes.learning.DOWNLOADS_PER_HOUR", 1)
    sign_up(client)
    assert client.get("/api/exercises/starter.one/download").status_code == 200
    assert client.get("/api/exercises/starter.one/download").status_code == 429


def test_downloading_needs_a_session_and_a_real_exercise(client):
    assert client.get("/api/exercises/starter.one/download").status_code == 401
    sign_up(client)
    assert client.get("/api/exercises/starter.nope/download").status_code == 404


def test_the_zip_holds_exactly_the_brief_starter_live_script_readme_and_guide(client):
    sign_up(client)
    response = client.get("/api/exercises/starter.one/download")
    files = unzip(response)
    assert sorted(files) == [
        "starter.one/LIVE-MODE.md",
        "starter.one/README.md",
        "starter.one/brief.md",
        "starter.one/live.py",
        "starter.one/solution_mod.py",
    ]
    assert files["starter.one/brief.md"] == "# one\n"
    assert files["starter.one/solution_mod.py"] == STARTER
    assert files["starter.one/live.py"] == LIVE
    assert files["starter.one/LIVE-MODE.md"] == GUIDE
    readme = files["starter.one/README.md"]
    assert "https://forgeway.example/live-mode" in readme
    assert "github.com" not in readme  # the repository is private
    assert f'pip install "https://forgeway.example/kit/{WHEEL}"' in readme
    for name in ("FORGEWAY_LIVE", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "FORGEWAY_MODEL"):
        assert name in readme
    assert "FORGEWAY_BASE_URL" in readme
    assert "python live.py" in readme
    assert "never leaves your machine" in readme
    assert "Grades still come from Forgeway" in readme
    assert 'filename="starter.one.zip"' in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"


def test_without_live_py_the_readme_says_how_to_call_your_own_code(client):
    sign_up(client)
    files = unzip(client.get("/api/exercises/retrieval.a/download"))
    assert "retrieval.a/live.py" not in files
    assert "default_client()" in files["retrieval.a/README.md"]


def test_the_draft_overrides_the_starter(client):
    me = sign_up(client)
    saved = client.put(
        "/api/exercises/starter.one/draft",
        json={"files": {"solution_mod.py": "def add(a, b):\n    return a + b  # mine\n"}},
        headers={"x-csrf-token": me["csrf_token"]},
    )
    assert saved.status_code == 204
    files = unzip(client.get("/api/exercises/starter.one/download"))
    assert files["starter.one/solution_mod.py"] == "def add(a, b):\n    return a + b  # mine\n"


def test_no_hidden_file_can_leak_even_from_a_tampered_draft(client, factory):
    sign_up(client)
    with transaction(factory) as session:
        user = session.scalars(select(User)).one()
        session.add(
            Draft(
                user_id=user.id,
                exercise_id="starter.one",
                files={
                    "solution_mod.py": "mine\n",
                    "../solution/solution_mod.py": "x",
                    "tests/test_add.py": "x",
                    "/etc/passwd": "x",
                    "notes.md": "x",
                },
            )
        )
    files = unzip(client.get("/api/exercises/starter.one/download"))
    assert sorted(files) == [
        "starter.one/LIVE-MODE.md",
        "starter.one/README.md",
        "starter.one/brief.md",
        "starter.one/live.py",
        "starter.one/solution_mod.py",
    ]
    assert files["starter.one/solution_mod.py"] == "mine\n"
    everything = "".join(files.values())
    assert "return a + b" not in everything  # the reference solution
    assert "def test_adds" not in everything  # the hidden tests
    assert "the solution adds" not in everything  # the notes


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".",
        "../x.py",
        "a/../../x.py",
        "/etc/passwd",
        "..\\x.py",
        "tests/test_add.py",
        "solution/solution_mod.py",
        "wrong/case/solution_mod.py",
        "notes.md",
        "exercise.yaml",
    ],
)
def test_unsafe_or_hidden_names_never_ship(name):
    assert not is_shippable(name)


@pytest.mark.parametrize("name", ["solution_mod.py", "pkg/agent.py", "live.py", "README.md"])
def test_ordinary_names_ship(name):
    assert is_shippable(name)


def test_the_kit_wheel_is_served_by_name_with_a_latest_redirect(client):
    latest = client.get("/kit/latest", follow_redirects=False)
    assert latest.status_code == 307
    assert latest.headers["location"] == f"/kit/{WHEEL}"
    wheel = client.get(f"/kit/{WHEEL}")
    assert wheel.status_code == 200
    assert wheel.content == b"PK wheel bytes"
    for other in ("secret.txt", "..%2Fsecret.txt", "forgeway_kit-9.9.9-py3-none-any.whl"):
        assert client.get(f"/kit/{other}").status_code == 404
    assert client.get("/api/config").json()["kit_wheel_url"] == (
        f"https://forgeway.example/kit/{WHEEL}"
    )


def test_without_a_built_wheel_the_kit_is_absent(client, kit_dir):
    (kit_dir / WHEEL).unlink()
    assert client.get("/kit/latest").status_code == 404
    assert client.get("/api/config").json()["kit_wheel_url"] is None
    sign_up(client)
    readme = unzip(client.get("/api/exercises/starter.one/download"))["starter.one/README.md"]
    assert "pip install ./grader/kit" in readme


def test_the_toolkit_reference_is_public_markdown(client):
    # The real docs/ file through the default setting: pytest runs from the repo root.
    served = client.get("/kit/toolkit-reference.md")
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("text/markdown")
    assert "ToolCall(id, name, arguments)" in served.text


def test_the_guide_is_public_markdown_and_optional(client, guide):
    served = client.get("/kit/live-mode.md")
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("text/markdown")
    assert served.text == GUIDE
    guide.unlink()
    assert client.get("/kit/live-mode.md").status_code == 404
    sign_up(client)
    files = unzip(client.get("/api/exercises/starter.one/download"))
    assert "starter.one/LIVE-MODE.md" not in files
