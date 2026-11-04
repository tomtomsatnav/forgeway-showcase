"""The server-rendered verification page for a public certificate.

Self-contained: inline CSS, no scripts and no third-party requests; the brand fonts come from the
same origin (`/c/fonts/`, vendored with the share image). Every interpolated value goes through
`esc`, attributes included, because the recipient's name is user-controlled.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

IMAGE_WIDTH, IMAGE_HEIGHT = 1200, 627


def esc(value: object) -> str:
    """HTML-escape for text and for double- or single-quoted attributes."""
    return escape(str(value), quote=True)


@dataclass(frozen=True)
class PageContent:
    recipient_name: str
    branch_title: str
    exercise_count: int
    includes_capstone: bool
    issued_on: str  # formatted for people, e.g. 25 October 2026
    issued_iso: str  # YYYY-MM-DD, for the <time> element
    credential_id: str
    url: str  # absolute
    image_url: str  # absolute
    site_url: str  # absolute


# The fonts the page may load from /c/fonts/, by file name: the ones the share image uses.
PAGE_FONTS = ("SourceSerif4.ttf", "InstrumentSans.ttf", "JetBrainsMono.ttf")

_STYLE = """\
@font-face { font-family: "Source Serif 4"; src: url("/c/fonts/SourceSerif4.ttf")
  format("truetype"); font-weight: 200 900; font-display: swap; }
@font-face { font-family: "Instrument Sans"; src: url("/c/fonts/InstrumentSans.ttf")
  format("truetype"); font-weight: 400 700; font-display: swap; }
@font-face { font-family: "JetBrains Mono"; src: url("/c/fonts/JetBrainsMono.ttf")
  format("truetype"); font-weight: 100 800; font-display: swap; }
:root {
  --paper: #F6F4EF; --raised: #FFFFFF; --ink: #1B1C1A; --muted: #5E605A;
  --rule: #84867E; --accent: #1D5C4B;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #131513; --raised: #1C1F1C; --ink: #E9E6DE; --muted: #A3A59C;
    --rule: #70736B; --accent: #6FC2A6;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font: 16px/1.6 "Instrument Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
}
main { max-width: 46rem; margin: 0 auto; padding: 2rem 1rem 3rem; }
.brand { color: var(--accent); font-weight: 600; font-size: 1.25rem; text-decoration: none; }
.card {
  margin-top: 1.5rem; padding: 1.5rem; background: var(--raised);
  border: 1px solid var(--rule); border-top: 6px solid var(--accent); border-radius: 4px;
}
.label {
  margin: 0; color: var(--muted); font-size: 0.75rem; letter-spacing: 0.06em;
  text-transform: uppercase; font-weight: 600;
}
h1 {
  margin: 0.25rem 0 0.75rem; font: 600 clamp(1.75rem, 6vw, 2.75rem)/1.15
    "Source Serif 4", Georgia, "Times New Roman", serif;
  overflow-wrap: anywhere;
}
.claim { margin: 0 0 0.5rem; font: 1.25rem/1.4 "Source Serif 4", Georgia, serif; }
.claim, .detail { overflow-wrap: anywhere; }
.detail { margin: 0; color: var(--muted); }
dl { display: grid; grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr)); gap: 1rem;
  margin: 1.5rem 0 0; padding-top: 1rem; border-top: 1px solid var(--rule); }
dt { color: var(--muted); font-size: 0.75rem; letter-spacing: 0.06em; text-transform: uppercase;
  font-weight: 600; }
dd { margin: 0; overflow-wrap: anywhere; }
.credential { font: 500 0.9375rem/1.6 "JetBrains Mono", ui-monospace, "SFMono-Regular", Menlo,
  Consolas, monospace; font-variant-numeric: tabular-nums slashed-zero; }
.about { margin-top: 1.5rem; color: var(--muted); }
a { color: var(--accent); }
a:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
"""


def render_certificate_page(c: PageContent) -> str:
    noun = "exercise" if c.exercise_count == 1 else "exercises"
    including = ", including its capstone project" if c.includes_capstone else ""
    title = f"{c.recipient_name}: {c.branch_title} certificate | Forgeway"
    description = (
        f"{c.recipient_name} has completed the {c.branch_title} track on Forgeway: "
        f"{c.exercise_count} {noun}{including}, each graded automatically by sandboxed "
        "behavioural checks."
    )
    image_alt = f"Forgeway certificate: {c.recipient_name} completed the {c.branch_title} track"
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(c.url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Forgeway">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(c.url)}">
<meta property="og:image" content="{esc(c.image_url)}">
<meta property="og:image:width" content="{IMAGE_WIDTH}">
<meta property="og:image:height" content="{IMAGE_HEIGHT}">
<meta property="og:image:alt" content="{esc(image_alt)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
<meta name="twitter:image" content="{esc(c.image_url)}">
<meta name="twitter:image:alt" content="{esc(image_alt)}">
<style>
{_STYLE}</style>
</head>
<body>
<main>
<a class="brand" href="{esc(c.site_url)}">Forgeway</a>
<article class="card">
<p class="label">Certificate of completion</p>
<h1>{esc(c.recipient_name)}</h1>
<p class="claim">has completed the {esc(c.branch_title)} track on Forgeway</p>
<p class="detail">{esc(c.exercise_count)} {noun}{including}, each graded automatically by \
sandboxed behavioural checks.</p>
<dl>
<div><dt>Issued</dt><dd><time datetime="{esc(c.issued_iso)}">{esc(c.issued_on)}</time></dd></div>
<div><dt>Credential ID</dt><dd class="credential">{esc(c.credential_id)}</dd></div>
</dl>
</article>
<p class="about">This page verifies a credential issued by \
<a href="{esc(c.site_url)}">Forgeway</a>, a platform for learning AI engineering through \
hands-on exercises.</p>
</main>
</body>
</html>
"""


def render_not_found_page(site_url: str) -> str:
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Certificate not found | Forgeway</title>
<style>
{_STYLE}</style>
</head>
<body>
<main>
<a class="brand" href="{esc(site_url)}">Forgeway</a>
<article class="card">
<h1>Certificate not found</h1>
<p class="detail">There is no public certificate at this address. It may be private, or the link
may be mistyped.</p>
</article>
</main>
</body>
</html>
"""
