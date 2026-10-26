"""Write the forgeway_kit API description the exercise editor uses for completion and hovers.

    uv run python scripts/kit_api.py            # rewrite the JSON
    uv run python scripts/kit_api.py --check    # fail if the JSON is out of date

The data is introspected from the real package (its `__all__`), so the editor never documents
a signature the sandbox does not have. grader/tests/test_kit_api.py runs the check in CI.
"""

from __future__ import annotations

import argparse
import dataclasses
import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any

import forgeway_kit

OUTPUT = (
    Path(__file__).resolve().parent.parent / "frontend/src/components/editor/forgeway-kit-api.json"
)

# Object reprs carry memory addresses (`<function <lambda> at 0x...>`); they would make the
# output differ on every run, so a default like that, or a dataclass `<factory>`, shows as `...`.
_OPAQUE = re.compile(r"<\w+ \S+ at 0x[0-9a-f]+>|^<factory>$")


def _annotation(value: Any) -> str:
    # The kit uses `from __future__ import annotations`, so most annotations are already text.
    return value if isinstance(value, str) else inspect.formatannotation(value)


def _parameter(param: inspect.Parameter) -> str:
    text = param.name
    if param.kind is inspect.Parameter.VAR_POSITIONAL:
        text = "*" + text
    elif param.kind is inspect.Parameter.VAR_KEYWORD:
        text = "**" + text
    if param.annotation is not inspect.Parameter.empty:
        text += f": {_annotation(param.annotation)}"
    if param.default is not inspect.Parameter.empty:
        default = _OPAQUE.sub("...", repr(param.default))
        text += (
            f" = {default}" if param.annotation is not inspect.Parameter.empty else f"={default}"
        )
    return text


def _signature(obj: Any, *, drop_self: bool = False, returns: bool = True) -> str:
    """`(a: int, *, b: str = 'x') -> int`, with the bare `*` and `/` markers Python prints."""
    sig = inspect.signature(obj)
    params = list(sig.parameters.values())
    if drop_self and params and params[0].name in ("self", "cls"):
        params = params[1:]
    parts: list[str] = []
    keyword_marker_needed = True
    for index, param in enumerate(params):
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            keyword_marker_needed = False
        if param.kind is inspect.Parameter.KEYWORD_ONLY and keyword_marker_needed:
            parts.append("*")
            keyword_marker_needed = False
        parts.append(_parameter(param))
        following = params[index + 1] if index + 1 < len(params) else None
        if param.kind is inspect.Parameter.POSITIONAL_ONLY and (
            following is None or following.kind is not inspect.Parameter.POSITIONAL_ONLY
        ):
            parts.append("/")
    text = f"({', '.join(parts)})"
    if returns and sig.return_annotation is not inspect.Signature.empty:
        text += f" -> {_annotation(sig.return_annotation)}"
    return text


def _summary(obj: Any, name: str) -> str:
    """The first paragraph of the docstring, re-flowed onto one line."""
    doc = inspect.getdoc(obj) or ""
    # A dataclass without a docstring gets its signature as one; that says nothing new.
    if doc.startswith(f"{name}("):
        return ""
    return " ".join(doc.split("\n\n", 1)[0].split())


def _class_signature(cls: type) -> str:
    """`class Usage(input_tokens: int, output_tokens: int)`; the bases where that says more.

    A Protocol cannot be instantiated, and an exception without its own `__init__` has no
    signature to show, so those name their bases instead.
    """
    bases = ", ".join(base.__name__ for base in cls.__bases__ if base is not object)
    by_bases = f"class {cls.__name__}({bases})" if bases else f"class {cls.__name__}"
    if getattr(cls, "_is_protocol", False):
        return f"class {cls.__name__}(Protocol)"
    try:
        return f"class {cls.__name__}{_signature(cls, returns=False)}"
    except ValueError:
        return by_bases


def _members(cls: type) -> list[dict[str, str]]:
    members: list[dict[str, str]] = []
    fields = dataclasses.fields(cls) if dataclasses.is_dataclass(cls) else ()
    for item in fields:
        members.append(
            {
                "name": item.name,
                "kind": "field",
                "signature": f"{item.name}: {_annotation(item.type)}",
                "doc": "",
            }
        )
    field_names = {item.name for item in fields}
    for name, value in vars(cls).items():
        # A field's default (FakeModel.responder's lambda) is not a method.
        if name.startswith("_") or name in field_names:
            continue
        if isinstance(value, property):
            annotation = inspect.signature(value.fget).return_annotation if value.fget else None
            shown = "" if annotation in (None, inspect.Signature.empty) else annotation
            members.append(
                {
                    "name": name,
                    "kind": "property",
                    "signature": f"{name}: {_annotation(shown)}" if shown else name,
                    "doc": _summary(value, name),
                }
            )
        elif inspect.isfunction(value):
            members.append(
                {
                    "name": name,
                    "kind": "method",
                    "signature": name + _signature(value, drop_self=True),
                    "doc": _summary(value, name),
                }
            )
    return members


def describe() -> dict[str, Any]:
    symbols: list[dict[str, Any]] = []
    for name in sorted(forgeway_kit.__all__):
        obj = getattr(forgeway_kit, name)
        if inspect.isclass(obj):
            symbols.append(
                {
                    "name": name,
                    "kind": "class",
                    "signature": _class_signature(obj),
                    "doc": _summary(obj, name),
                    "members": _members(obj),
                }
            )
        else:
            symbols.append(
                {
                    "name": name,
                    "kind": "function",
                    "signature": f"def {name}{_signature(obj)}",
                    "doc": _summary(obj, name),
                    "members": [],
                }
            )
    return {"module": "forgeway_kit", "symbols": symbols}


def render() -> str:
    return json.dumps(describe(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the file is out of date")
    args = parser.parse_args()
    text = render()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text() != text:
            print(f"{OUTPUT} is out of date: run uv run python scripts/kit_api.py", file=sys.stderr)
            return 1
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
