"""docs/toolkit-reference.md is written by hand: it must name the whole kit, and its code runs."""

import re
from pathlib import Path

import forgeway_kit
import forgeway_kit.mcp

REFERENCE = (Path(__file__).parents[2] / "docs/toolkit-reference.md").read_text(encoding="utf-8")


def test_every_public_name_is_in_the_reference():
    live = ["AnthropicClient", "OpenAIClient", "Metered", "client_from_env"]
    names = [*forgeway_kit.__all__, *forgeway_kit.mcp.__all__, *live]
    assert [name for name in names if name not in REFERENCE] == []


def test_the_examples_run():
    namespace: dict[str, object] = {}
    for block in re.findall(r"```python\n(.*?)```", REFERENCE, re.DOTALL):
        exec(block, namespace)  # noqa: S102 - our own document
