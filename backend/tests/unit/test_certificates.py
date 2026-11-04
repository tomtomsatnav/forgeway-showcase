"""Certificate rules, the verification page's escaping and the image's layout limits."""

from __future__ import annotations

import io
import re
from datetime import date

import pytest
from PIL import Image

from lattice.api.certificate_page import PageContent, render_certificate_page, render_not_found_page
from lattice.domain.certificates import (
    InvalidRecipientNameError,
    certification_name,
    clean_recipient_name,
    format_issue_date,
    new_public_id,
    snapshot_name,
)
from lattice.infrastructure.certificates.image import HEIGHT, WIDTH, CardContent, render_png

URL_SAFE = re.compile(r"^[A-Za-z0-9_-]+$")


def test_public_ids_are_url_safe_unique_and_at_least_128_bits():
    ids = {new_public_id() for _ in range(500)}
    assert len(ids) == 500
    assert all(URL_SAFE.match(i) and len(i) >= 22 for i in ids)  # 22 base64 characters = 132 bits


def test_names_are_trimmed():
    assert clean_recipient_name("  Ada Lovelace \t") == "Ada Lovelace"
    assert clean_recipient_name("x" * 60) == "x" * 60
    assert clean_recipient_name("Zoë Müller 李") == "Zoë Müller 李"


@pytest.mark.parametrize(
    "raw", ["", " \n ", "x" * 61, "a\nb", "a\tb", "a\x00b", "a\x7fb", "a\u2028b"]
)
def test_names_that_are_empty_long_or_contain_control_characters_are_refused(raw):
    with pytest.raises(InvalidRecipientNameError):
        clean_recipient_name(raw)


def test_a_display_name_always_yields_a_valid_snapshot():
    assert snapshot_name("  Ada\nLovelace ") == "AdaLovelace"
    assert snapshot_name("\n\t") == "Forgeway learner"
    assert clean_recipient_name(snapshot_name("y" * 200)) == "y" * 60


def test_dates_use_the_uk_long_form_whatever_the_locale():
    assert format_issue_date(date(2026, 10, 25)) == "25 October 2026"
    assert format_issue_date(date(2027, 3, 1)) == "1 March 2027"


def test_the_certification_name_carries_the_issuer():
    assert certification_name("Retrieval") == "Forgeway — Retrieval"


def content(
    name: str = "Ada", branch: str = "Retrieval", count: int = 9, capstone: bool = False
) -> PageContent:
    return PageContent(
        recipient_name=name,
        branch_title=branch,
        exercise_count=count,
        includes_capstone=capstone,
        issued_on="25 October 2026",
        issued_iso="2026-10-25",
        credential_id="abc_DEF-123",
        url="https://forgeway.example/c/abc_DEF-123",
        image_url="https://forgeway.example/c/abc_DEF-123.png",
        site_url="https://forgeway.example/",
    )


def test_every_interpolated_value_is_escaped_in_text_and_attributes():
    hostile = '"><script>alert(1)</script>'
    page = render_certificate_page(
        PageContent(
            recipient_name=hostile,
            branch_title="<b onload=x>' & \"",
            exercise_count=3,
            includes_capstone=True,
            issued_on="<i>",
            issued_iso='"><x>',
            credential_id="<id>",
            url='https://x.example/c/"><y>',
            image_url="https://x.example/'><z>",
            site_url='https://x.example/"><w>',
        )
    )
    for raw in ("<script>", "<b onload", "<i>", "<x>", "<id>", "<y>", "<z>", "<w>", hostile):
        assert raw not in page
    assert "&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert page.count("<script") == 0


def test_the_page_pluralises_and_stays_self_contained():
    page = render_certificate_page(content(count=1))
    assert "1 exercise, each graded" in page
    assert '<link rel="stylesheet"' not in page and "src=" not in page


def test_the_page_loads_its_brand_fonts_from_its_own_origin_and_sets_the_id_in_mono():
    page = render_certificate_page(content())
    for name in ("SourceSerif4.ttf", "InstrumentSans.ttf", "JetBrainsMono.ttf"):
        assert f'url("/c/fonts/{name}")' in page
    assert '<dd class="credential">abc_DEF-123</dd>' in page
    assert '"JetBrains Mono", ui-monospace' in page
    assert "googleapis" not in page and "gstatic" not in page


def test_the_page_claims_a_capstone_only_when_the_certificate_includes_one():
    with_capstone = render_certificate_page(content(capstone=True))
    assert "9 exercises, including its capstone project, each graded" in with_capstone
    assert (
        with_capstone.count("including its capstone project") == 4
    )  # detail and three descriptions
    # An older certificate (false) renders as before, with no claim about a capstone.
    assert "capstone" not in render_certificate_page(content(capstone=False))


def test_the_image_differs_only_when_a_capstone_is_claimed():
    plain = CardContent("Ada", "Retrieval", 9, False, "25 October 2026", "abc_DEF-123")
    with_capstone = CardContent("Ada", "Retrieval", 9, True, "25 October 2026", "abc_DEF-123")
    assert render_png(plain) != render_png(with_capstone)
    assert Image.open(io.BytesIO(render_png(with_capstone))).size == (WIDTH, HEIGHT)


def test_the_not_found_page_is_html_with_no_certificate_data():
    page = render_not_found_page("https://forgeway.example/")
    assert "Certificate not found" in page and "og:" not in page


def test_the_image_is_1200_by_627_and_cached_by_content():
    card = CardContent("Ada", "Retrieval", 9, False, "25 October 2026", "abc_DEF-123")
    first = render_png(card)
    assert Image.open(io.BytesIO(first)).size == (WIDTH, HEIGHT) == (1200, 627)
    assert render_png(card) is first
    assert (
        render_png(CardContent("Grace", "Retrieval", 9, False, "25 October 2026", "abc_DEF-123"))
        != first
    )


@pytest.mark.parametrize(
    "name",
    ["W" * 60, "Wolfeschlegelsteinhausenbergerdorff " * 2, "李" * 60, "a b " * 15, "Ada"],
)
def test_long_names_and_titles_never_overflow_the_card(name):
    card = CardContent(name[:60], "Orchestration " * 6, 12, True, "25 October 2026", "x" * 22)
    image = Image.open(io.BytesIO(render_png(card))).convert("RGB")
    paper = image.getpixel((5, 5))
    # Nothing is drawn in the side margins or between the text block and the footer rule.
    for x in (*range(0, 70), *range(WIDTH - 70, WIDTH)):
        for y in range(0, HEIGHT - 14):
            assert image.getpixel((x, y)) == paper, (x, y)
    for x in range(WIDTH):
        for y in range(500, 505):
            assert image.getpixel((x, y)) == paper, (x, y)
