import json
import re

import pytest
from extract import extract_person

from forgeway_kit import FakeModel

PEOPLE = [
    ("Ada Lovelace is 36 and wrote the first program.", "Ada Lovelace", 36),
    ("Meet Grace Hopper. Grace Hopper is 85 years old.", "Grace Hopper", 85),
    ("Alan Turing is 41.", "Alan Turing", 41),
]


def plain(value):
    """Round-trip through JSON so a result that lies about equality cannot pass."""
    return json.loads(json.dumps(value))


def fields(request):
    text = request.messages[0].content
    match = re.search(r"([A-Z][a-z]+ [A-Z][a-z]+) is (\d+)", text)
    return match.group(1), int(match.group(2))


def good_json(request):
    name, age = fields(request)
    return json.dumps({"name": name, "age": age})


def test_returns_parsed_fields():
    for text, name, age in PEOPLE:
        model = FakeModel(responder=good_json)
        result = plain(extract_person(model, text))
        assert result == {"name": name, "age": age}, (
            f"For {text!r} expected {{'name': {name!r}, 'age': {age}}}, got {result!r}."
        )
        assert len(model.requests) == 1, (
            f"A valid reply needs no retry, but the model was called {len(model.requests)} times."
        )
        sent = model.requests[0]
        prompt = (sent.system or "") + " ".join(m.content for m in sent.messages)
        assert "json" in prompt.lower(), "The prompt should ask the model for JSON."
        assert text in prompt, "The text to extract from must be included in the prompt."


def test_reasks_with_the_parse_error():
    for text, name, age in PEOPLE:
        bad = f'{{"name": "{name}", "age": {age},}}'  # trailing comma
        replies = []

        def responder(request, bad=bad, replies=replies):
            replies.append(request)
            return bad if len(replies) == 1 else good_json(request)

        model = FakeModel(responder=responder)
        result = plain(extract_person(model, text))
        assert result == {"name": name, "age": age}, (
            f"After one bad reply the second, valid reply should be used; got {result!r}."
        )
        assert len(model.requests) == 2, (
            f"Expected exactly 2 model calls (original and one re-ask), got {len(model.requests)}."
        )
        retry = model.requests[1].messages
        assert [m.role for m in retry] == ["user", "assistant", "user"], (
            "The re-ask should send the original request, the bad reply as an assistant "
            f"message, then a user message. Roles sent: {[m.role for m in retry]}."
        )
        assert retry[1].content == bad, "The bad reply should be sent back unchanged."
        with pytest.raises(json.JSONDecodeError) as info:
            json.loads(bad)
        assert info.value.msg in retry[2].content, (
            f"The re-ask should tell the model what was wrong. Expected the user message to "
            f"include the parser error (the message of the JSONDecodeError) {info.value.msg!r}, "
            f"but it was {retry[2].content!r}."
        )


def test_validates_required_fields():
    # Valid JSON, but "age" is missing, or has the wrong type.
    for bad in [
        '{"name": "Ada Lovelace"}',
        '{"name": "Ada Lovelace", "age": "36"}',
        "[1, 2]",
        '{"name": "", "age": 3}',
        '{"age": true}',
        '{"name": "Ada Lovelace", "age": true}',
    ]:
        calls = []

        def responder(request, bad=bad, calls=calls):
            calls.append(request)
            return bad if len(calls) == 1 else '{"name": "Ada Lovelace", "age": 36}'

        model = FakeModel(responder=responder)
        result = plain(extract_person(model, "Ada Lovelace is 36."))
        assert len(model.requests) == 2, (
            f"The reply {bad} is valid JSON but fails validation, so the model should be "
            f"asked again. Calls made: {len(model.requests)}. Check the required fields and types."
        )
        assert result == {"name": "Ada Lovelace", "age": 36}, (
            f"After the retry, extract_person should return the valid person; got {result!r}."
        )

    model = FakeModel(responder=lambda request: "not json at all")
    with pytest.raises(ValueError):
        extract_person(model, "Alan Turing is 41.")
    assert len(model.requests) == 2, (
        f"After two bad replies, give up with ValueError. The model was called "
        f"{len(model.requests)} times; it should be exactly 2."
    )
