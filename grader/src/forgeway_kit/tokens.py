"""A deterministic token counter.

Real models use subword tokenisers (byte-pair encoding) whose counts vary by provider. This
counter splits text into words and individual punctuation marks, which tracks real counts
closely enough to teach budgeting while staying identical on every machine. `FakeModel`
reports usage with the same counter, so budgets computed with it are exact in the sandbox.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"\w+|[^\w\s]")


def tokenize(text: str) -> list[str]:
    """Split `text` into tokens: runs of word characters, and single punctuation marks."""
    return _TOKEN.findall(text)


def count_tokens(text: str) -> int:
    """Number of tokens in `text`."""
    return len(tokenize(text))
