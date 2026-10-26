"""Release notes: front matter, ids that must exist, unique versions and ISO dates."""

from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lattice.cli import app
from lattice.domain.content import ContentError
from lattice.domain.content.releases import ReleaseNote, has_unread, newest_first, version_key
from lattice.infrastructure.content_loader import load_catalogue
from tests.content_factory import write_branch, write_exercise

REAL_CONTENT = Path(__file__).parents[3] / "content"


def content(tmp_path: Path) -> Path:
    write_branch(tmp_path, "starter")
    write_exercise(tmp_path, "starter", "one")
    write_exercise(tmp_path, "starter", "two")
    (tmp_path / "releases").mkdir()
    return tmp_path


def note(root: Path, name: str, front: str, body: str = "Body text.\n") -> None:
    (root / "releases" / f"{name}.md").write_text(f"---\n{front}---\n{body}")


GOOD = (
    "version: 2026.10.0\ndate: 2026-10-26\ntitle: First\nsummary: The first release.\n"
    "added: [starter.one]\nfixed: [starter.two]\n"
)


def test_a_release_note_loads_with_its_body_and_ids(tmp_path: Path):
    root = content(tmp_path)
    note(root, "2026.10.0", GOOD, "## Heading\n\nSome words.\n")
    (release,) = load_catalogue(root).releases
    assert release.version == "2026.10.0"
    assert release.date == date(2026, 10, 26)
    assert release.added == ("starter.one",)
    assert release.fixed == ("starter.two",)
    assert release.body == "## Heading\n\nSome words.\n"


def test_releases_are_optional(tmp_path: Path):
    write_branch(tmp_path, "starter")
    write_exercise(tmp_path, "starter", "one")
    assert load_catalogue(tmp_path).releases == ()


def test_releases_come_newest_first_by_version_not_by_file_order(tmp_path: Path):
    root = content(tmp_path)
    for version in ("2026.9.0", "2026.11.0", "2026.10.2"):
        note(root, version, GOOD.replace("2026.10.0", version))
    versions = [r.version for r in load_catalogue(root).releases]
    assert versions == ["2026.11.0", "2026.10.2", "2026.9.0"]


@pytest.mark.parametrize(
    ("front", "expected"),
    [
        (GOOD.replace("starter.two", "starter.missing"), "unknown exercise 'starter.missing'"),
        (GOOD.replace("2026-10-26", "26/10/2026"), "date"),
        (GOOD.replace("2026-10-26", "2026-13-01"), "month must be in 1..12"),
        (GOOD.replace("version: 2026.10.0", "version: v1"), "version"),
        (GOOD.replace("title: First\n", ""), "title"),
        (GOOD + "colour: red\n", "colour"),
        (GOOD.replace("[starter.one]", "[starter.one, starter.one]"), "more than once"),
    ],
)
def test_an_invalid_release_note_is_reported(tmp_path: Path, front: str, expected: str):
    root = content(tmp_path)
    note(root, "2026.10.0", front)
    with pytest.raises(ContentError) as err:
        load_catalogue(root)
    assert expected in str(err.value)


def test_the_file_name_must_be_the_version(tmp_path: Path):
    root = content(tmp_path)
    note(root, "2026.10.1", GOOD)
    with pytest.raises(ContentError, match="file name must be the version"):
        load_catalogue(root)


def test_versions_must_be_unique(tmp_path: Path):
    root = content(tmp_path)
    note(root, "2026.10.0", GOOD)
    note(root, "copy", GOOD)
    with pytest.raises(ContentError, match="defined more than once"):
        load_catalogue(root)


def test_front_matter_is_required(tmp_path: Path):
    root = content(tmp_path)
    (root / "releases" / "2026.10.0.md").write_text("# No front matter\n")
    with pytest.raises(ContentError, match="front matter"):
        load_catalogue(root)


def test_content_validate_reports_a_bad_release(tmp_path: Path):
    root = content(tmp_path)
    note(root, "2026.10.0", GOOD.replace("starter.two", "starter.gone"))
    result = CliRunner().invoke(app, ["content", "validate", "--content-dir", str(root)])
    assert result.exit_code == 1
    assert "starter.gone" in result.output


def test_unread_is_any_release_newer_than_the_last_seen():
    notes = [
        ReleaseNote(version=v, date=date(2026, 10, 1), title="t", summary="s")
        for v in ("2026.9.0", "2026.10.0")
    ]
    assert has_unread(notes, None)
    assert has_unread(notes, "2026.9.0")
    assert not has_unread(notes, "2026.10.0")
    assert not has_unread([], None)
    assert [n.version for n in newest_first(notes)] == ["2026.10.0", "2026.9.0"]
    assert version_key("2026.10.0") > version_key("2026.9.12")


def test_the_shipped_release_notes_are_valid():
    releases = load_catalogue(REAL_CONTENT).releases
    assert "2026.10.0" in [r.version for r in releases]


def test_the_first_release_note_states_the_shipped_counts_and_no_waitlist():
    catalogue = load_catalogue(REAL_CONTENT)
    (first,) = [n for n in catalogue.releases if n.version == "2026.10.0"]
    capstones = sum(e.tier.value == "capstone" for e in catalogue.graph.exercises.values())
    words = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
    assert f"{words[capstones]} capstones" in first.title
    assert f"{len(catalogue.sources)} exercises" in first.body
    text = f"{first.title} {first.summary} {first.body}".lower()
    assert "waitlist" not in text and "not open yet" not in text
