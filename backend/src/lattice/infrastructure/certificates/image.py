"""Render a certificate as a 1200x627 PNG (the size LinkedIn and most previews expect).

Styled as the professional "engineering notebook": warm paper, ink and a deep green accent, in
Source Serif 4 and Instrument Sans, with the credential ID in JetBrains Mono so l, I and 1 differ
(all SIL OFL, vendored in `fonts/`). Long text shrinks, then wraps, then is cut with an ellipsis,
so nothing can overflow the card.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 627
FONTS_DIR = Path(__file__).parent / "fonts"
_FONTS = FONTS_DIR
_PAPER = (246, 244, 239)
_INK = (27, 28, 26)
_MUTED = (94, 96, 90)
_RULE = (132, 134, 126)
_GREEN = (29, 92, 75)
_MARGIN = 80
_TEXT_WIDTH = WIDTH - 2 * _MARGIN

Font = ImageFont.FreeTypeFont
FontFactory = Callable[[int], Font]


@dataclass(frozen=True)
class CardContent:
    """Everything the image shows. Hashable, so it doubles as the render cache key."""

    recipient_name: str
    branch_title: str
    exercise_count: int
    includes_capstone: bool
    issued_on: str  # already formatted, e.g. 25 October 2026
    credential_id: str


def _font(file: str, weight: int) -> FontFactory:
    def make(size: int) -> Font:
        font = ImageFont.truetype(str(_FONTS / file), size)
        values: list[float] = []
        for axis in font.get_variation_axes():
            low, high = float(axis["minimum"] or 0), float(axis["maximum"] or 0)
            default = float(axis["default"] or 0)
            values.append(
                max(low, min(high, float(weight))) if axis["name"] == b"Weight" else default
            )
        font.set_variation_by_axes(values)
        return font

    return make


def _wrap(text: str, font: Font, width: int) -> list[str]:
    """Greedy word wrap; a word wider than the line is broken by character."""
    lines: list[str] = []
    line = ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if font.getlength(candidate) <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
            line = ""
        while font.getlength(word) > width:
            cut = len(word)
            while cut > 1 and font.getlength(word[:cut]) > width:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        line = word
    if line:
        lines.append(line)
    return lines


def _ellipsise(line: str, font: Font, width: int) -> str:
    while line and font.getlength(f"{line}…") > width:
        line = line[:-1]
    return f"{line.rstrip()}…"


def _fit(
    text: str, make: FontFactory, width: int, max_lines: int, sizes: range
) -> tuple[list[str], Font]:
    """The largest size in `sizes` at which `text` fits in `max_lines`; else the smallest, cut."""
    for size in sizes:
        font = make(size)
        lines = _wrap(text, font, width)
        if len(lines) <= max_lines:
            return lines, font
    font = make(sizes[-1])
    lines = _wrap(text, font, width)[:max_lines]
    lines[-1] = _ellipsise(lines[-1], font, width)
    return lines, font


def _tracked(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: Font,
    fill: tuple[int, int, int],
    spacing: float,
    *,
    right: bool = False,
) -> None:
    """Draw small-caps style text with letter spacing, optionally right-aligned at x."""
    x, y = float(xy[0]), xy[1]
    total = sum(font.getlength(ch) + spacing for ch in text) - spacing
    if right:
        x = int(x - total)
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += font.getlength(ch) + spacing


@lru_cache(maxsize=256)
def render_png(content: CardContent) -> bytes:
    """The certificate image. Cached by content, so editing the name or any snapshot re-renders."""
    serif_semibold, serif = _font("SourceSerif4.ttf", 600), _font("SourceSerif4.ttf", 400)
    sans, sans_semibold = _font("InstrumentSans.ttf", 400), _font("InstrumentSans.ttf", 600)
    mono = _font("JetBrainsMono.ttf", 500)

    image = Image.new("RGB", (WIDTH, HEIGHT), _PAPER)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, HEIGHT - 14, WIDTH, HEIGHT), fill=_GREEN)

    draw.text((_MARGIN, 52), "Forgeway", font=sans_semibold(34), fill=_GREEN)
    _tracked(
        draw,
        (WIDTH - _MARGIN, 62),
        "CERTIFICATE OF COMPLETION",
        sans_semibold(18),
        _MUTED,
        2.4,
        right=True,
    )
    draw.line((_MARGIN, 112, WIDTH - _MARGIN, 112), fill=_RULE, width=1)

    draw.text((_MARGIN, 148), "This certifies that", font=sans(26), fill=_MUTED)

    lines, font = _fit(content.recipient_name, serif_semibold, _TEXT_WIDTH, 2, range(72, 35, -2))
    y = 196
    for line in lines:
        draw.text((_MARGIN, y), line, font=font, fill=_INK)
        y += int(font.size * 1.1)

    y = max(y + 12, 320)
    claim = f"has completed the {content.branch_title} track on Forgeway"
    lines, font = _fit(claim, serif, _TEXT_WIDTH, 2, range(36, 25, -2))
    for line in lines:
        draw.text((_MARGIN, y), line, font=font, fill=_INK)
        y += int(font.size * 1.25)

    noun = "exercise" if content.exercise_count == 1 else "exercises"
    including = ", including its capstone project" if content.includes_capstone else ""
    detail = (
        f"{content.exercise_count} {noun}{including}, each graded automatically by sandboxed "
        "behavioural checks."
    )
    lines, font = _fit(detail, sans, _TEXT_WIDTH, 1, range(26, 15, -1))
    y += 6
    for line in lines:
        draw.text((_MARGIN, y), line, font=font, fill=_MUTED)
        y += int(font.size * 1.4)

    draw.line((_MARGIN, 506, WIDTH - _MARGIN, 506), fill=_RULE, width=1)
    label = sans_semibold(15)
    _tracked(draw, (_MARGIN, 526), "ISSUED", label, _MUTED, 2.0)
    draw.text((_MARGIN, 550), content.issued_on, font=sans(26), fill=_INK)
    mid = 520
    _tracked(draw, (mid, 526), "CREDENTIAL ID", label, _MUTED, 2.0)
    lines, font = _fit(content.credential_id, mono, WIDTH - _MARGIN - mid, 1, range(24, 15, -1))
    draw.text((mid, 552), lines[0], font=font, fill=_INK)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
