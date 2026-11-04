import json
import random

from parsing import canonical, document_ids, is_tool_name, parse_object, redact_keys


def plain(value):
    """A learner's value as plain built-ins, so it cannot lie about equality."""
    return json.loads(json.dumps(value))


def test_parse_object():
    rng = random.Random(1)  # noqa: S311
    for _ in range(3):
        value = {f"k{rng.randrange(100)}": [rng.randrange(100), {"n": rng.randrange(100)}]}
        got = parse_object(json.dumps(value))
        assert plain(got) == value, f"parse_object should return {value}; got {got!r}."
    for bad in ("", "{not json", "[1, 2]", "3", '"text"', "null", "true"):
        got = parse_object(bad)
        assert got is None, f"parse_object({bad!r}) should return None; got {got!r}."


def test_canonical():
    text = plain(canonical({"b": 1, "a": [1, 2]}))
    assert text == '{"a":[1,2],"b":1}', (
        f"Keys should be sorted and there should be no spaces at all; got {text!r}."
    )
    rng = random.Random(2)  # noqa: S311
    for _ in range(3):
        items = [(f"k{n}", rng.randrange(1000)) for n in range(6)]
        forwards = plain(canonical(dict(items)))
        backwards = plain(canonical(dict(reversed(items))))
        assert forwards == backwards, (
            f"Equal dicts should give the same text whatever their key order; got {forwards!r} "
            f"and {backwards!r}."
        )
        assert json.loads(forwards) == dict(items), "The text should be the same value as JSON."
        assert " " not in forwards, f"There should be no spaces; got {forwards!r}."
    nested = plain(canonical({"z": {"y": 1, "x": 2}}))
    assert nested == '{"z":{"x":2,"y":1}}', f"Nested keys are sorted too; got {nested!r}."


def test_document_ids():
    cases = [
        ("See DOC-1 and DOC-22, then DOC-1 again.", ["DOC-1", "DOC-22", "DOC-1"]),
        ("(DOC-305)", ["DOC-305"]),
        ("XDOC-12 and DOC-12a and DOC- and doc-5", []),
        ("", []),
    ]
    for text, expected in cases:
        got = plain(document_ids(text))
        assert got == expected, f"document_ids({text!r}) should be {expected}; got {got}."


def test_is_tool_name():
    good = ["a", "search", "get_page2", "a" * 32, "x_"]
    bad = ["", "Search", "2fast", "_private", "get page", "a" * 33, "search\n", "naïve", "a-b"]
    for name in good:
        assert is_tool_name(name) is True, f"is_tool_name({name!r}) should be True."
    for name in bad:
        assert is_tool_name(name) is False, (
            f"is_tool_name({name!r}) should be False. The whole name must fit the pattern."
        )


def test_redact_keys():
    cases = [
        ("key-204", "key-###"),
        ("use key-1 or key-9876.", "use key-# or key-####."),
        ("monkey-12 and key-12a stay", "monkey-12 and key-12a stay"),
        ("no keys here", "no keys here"),
    ]
    for text, expected in cases:
        got = plain(redact_keys(text))
        assert got == expected, f"redact_keys({text!r}) should be {expected!r}; got {got!r}."
