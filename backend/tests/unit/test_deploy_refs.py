"""`deploy/vps/deploy.sh` deploys only what origin publishes: a release tag matching origin's, a
branch on origin, or a commit on one of origin's branches.

Each test builds a throwaway origin and a clone of it, then sources the script (which defines its
functions without deploying) and calls `resolve`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

DEPLOY = Path(__file__).parents[3] / "deploy" / "vps" / "deploy.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None, reason="needs git and bash"
)

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "FORGEWAY_OPS_CONFIG": os.devnull,
}


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, env=ENV, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    """A clone of an origin with `main`, a release tag `v2026.11.0` and a branch `feature`."""
    origin, work = tmp_path / "origin", tmp_path / "work"
    git(tmp_path, "init", "-q", "-b", "main", str(origin))
    (origin / "a.txt").write_text("a")
    git(origin, "add", "a.txt")
    git(origin, "commit", "-q", "-m", "first")
    git(origin, "tag", "-a", "v2026.11.0", "-m", "Release 2026.11.0")
    git(origin, "switch", "-q", "-c", "feature")
    (origin / "b.txt").write_text("b")
    git(origin, "add", "b.txt")
    git(origin, "commit", "-q", "-m", "feature work")
    git(origin, "switch", "-q", "main")
    git(tmp_path, "clone", "-q", str(origin), str(work))
    return work


def resolve(clone: Path, ref: str) -> subprocess.CompletedProcess[str]:
    script = f'source "{DEPLOY}"; resolve "$1"'
    return subprocess.run(
        ["bash", "-c", script, "resolve", ref],
        cwd=clone,
        env=ENV,
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_release_tag_on_origin_resolves_to_its_commit(clone: Path) -> None:
    done = resolve(clone, "v2026.11.0")
    assert done.returncode == 0, done.stderr
    assert done.stdout == git(clone, "rev-parse", "v2026.11.0^{commit}")


def test_a_branch_on_origin_resolves(clone: Path) -> None:
    done = resolve(clone, "feature")
    assert done.returncode == 0, done.stderr
    assert done.stdout == git(clone, "rev-parse", "origin/feature")


def test_a_commit_on_an_origin_branch_resolves(clone: Path) -> None:
    sha = git(clone, "rev-parse", "origin/feature")
    done = resolve(clone, sha[:12])
    assert done.returncode == 0, done.stderr
    assert done.stdout == sha


def test_a_release_tag_only_made_here_is_refused(clone: Path) -> None:
    git(clone, "tag", "v2026.11.1")
    done = resolve(clone, "v2026.11.1")
    assert done.returncode != 0
    assert "not on origin" in done.stderr


def test_a_release_tag_moved_here_is_refused(clone: Path) -> None:
    (clone / "c.txt").write_text("c")
    git(clone, "add", "c.txt")
    git(clone, "commit", "-q", "-m", "local only")
    git(clone, "tag", "-f", "v2026.11.0")
    done = resolve(clone, "v2026.11.0")
    assert done.returncode != 0
    assert "is not origin's" in done.stderr


def test_a_tag_that_is_not_a_release_tag_is_refused(clone: Path) -> None:
    git(clone, "tag", "nightly")
    done = resolve(clone, "nightly")
    assert done.returncode != 0
    assert "not a release tag" in done.stderr


def test_a_local_branch_and_a_local_commit_are_refused(clone: Path) -> None:
    git(clone, "switch", "-q", "-c", "mine")
    (clone / "d.txt").write_text("d")
    git(clone, "add", "d.txt")
    git(clone, "commit", "-q", "-m", "mine")
    sha = git(clone, "rev-parse", "HEAD")
    branch = resolve(clone, "mine")
    assert branch.returncode != 0 and "unknown ref" in branch.stderr
    commit = resolve(clone, sha)
    assert commit.returncode != 0 and "none of origin's branches" in commit.stderr


@pytest.mark.parametrize("ref", ["v2026.13.0", "v26.11.0", "2026.11.0", "no-such-thing"])
def test_malformed_and_unknown_refs_are_refused(clone: Path, ref: str) -> None:
    done = resolve(clone, ref)
    assert done.returncode != 0
    assert "unknown" in done.stderr
