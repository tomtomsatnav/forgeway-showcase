"""The editor's forgeway_kit API data (completion and hovers) must match the real package."""

import importlib.util
import json
from pathlib import Path

import forgeway_kit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "kit_api.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("kit_api", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_editor_kit_api_json_is_up_to_date():
    kit_api = _load_script()
    assert kit_api.OUTPUT.read_text() == kit_api.render(), (
        "frontend/src/components/editor/forgeway-kit-api.json is out of date: "
        "run uv run python scripts/kit_api.py"
    )


def test_editor_kit_api_covers_the_public_api_without_memory_addresses():
    kit_api = _load_script()
    data = json.loads(kit_api.render())
    assert [s["name"] for s in data["symbols"]] == sorted(forgeway_kit.__all__)
    assert " at 0x" not in kit_api.render()
    count_tokens = next(s for s in data["symbols"] if s["name"] == "count_tokens")
    assert count_tokens["signature"] == "def count_tokens(text: str) -> int"
    assert count_tokens["doc"] == "Number of tokens in `text`."
