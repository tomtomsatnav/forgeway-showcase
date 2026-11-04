"""Hidden checks. Learners see each check's title and, when it fails, the assertion message."""

import json
import random

from schema_output import Refused, extract

from forgeway_kit import FakeModel, Refusal, ToolCall

WORDS = [
    "amber",
    "birch",
    "cedar",
    "delta",
    "ember",
    "fjord",
    "grove",
    "harbour",
    "inlet",
    "juniper",
    "kestrel",
    "lumen",
]
BOTH = {"response_format", "tool_choice"}
PATHS = [{"response_format"}, BOTH, {"tool_choice"}, set()]


def plain(value):
    """Learner results as plain built-ins, so a value cannot lie about equality."""
    return json.loads(json.dumps(value))


def seeded_case(rng):
    """A schema with arbitrary field names and types, a tool name, a text and a fitting object."""
    properties, data = {}, {}
    for word in rng.sample(WORDS, rng.randint(3, 5)):
        key = f"{word}_{rng.randrange(100)}"
        kind = rng.choice(["string", "integer", "number", "boolean", "enum", "array"])
        if kind == "string":
            properties[key], data[key] = (
                {"type": "string"},
                f"{rng.choice(WORDS)} {rng.randrange(999)}",
            )
        elif kind == "integer":
            properties[key], data[key] = {"type": "integer"}, rng.randrange(-500, 5000)
        elif kind == "number":
            properties[key], data[key] = {"type": "number"}, round(rng.random() * 1000, 2)
        elif kind == "boolean":
            properties[key], data[key] = {"type": "boolean"}, rng.random() < 0.5
        elif kind == "enum":
            options = rng.sample(WORDS, 3)
            properties[key], data[key] = {"type": "string", "enum": options}, rng.choice(options)
        else:
            properties[key] = {"type": "array", "items": {"type": "string"}}
            data[key] = rng.sample(WORDS, rng.randint(0, 3))
    schema = {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }
    name = f"record_{rng.randrange(16**6):06x}"
    text = f"Ticket {rng.randrange(10**6)}: " + "; ".join(str(v) for v in data.values())
    return schema, name, text, data


def prompt_of(request):
    return (request.system or "") + "\n".join(m.content for m in request.messages)


def tool_view(request):
    return plain([{"name": t.name, "input_schema": t.input_schema} for t in request.tools])


def run(model, text, schema, name, supports):
    return extract(model, text, schema, name, supports=set(supports))


def test_native_schema_first():
    rng = random.Random(5)  # noqa: S311 - seeded, so grading is deterministic
    for supports in [{"response_format"}, BOTH] * 3:
        schema, name, text, data = seeded_case(rng)
        model = FakeModel(responder=lambda r, data=data: json.dumps(data))
        result = plain(run(model, text, schema, name, supports))
        assert len(model.requests) == 1, (
            f"A valid reply needs one call; the model was called {len(model.requests)} times."
        )
        sent = model.requests[0]
        assert plain(sent.response_format) == plain(schema), (
            f"With supports={sorted(supports)}, send the schema itself as response_format, the "
            f"strongest route. Expected response_format={schema}, got {sent.response_format}."
        )
        assert tool_view(sent) == [], "On the response_format route, offer no tools."
        assert text in prompt_of(sent), "The text to extract from must reach the model."
        assert result == plain(data), f"extract() should return {data}, got {result}."


def test_forced_tool_without_native_schema():
    rng = random.Random(7)  # noqa: S311 - seeded, so grading is deterministic
    for _ in range(5):
        schema, name, text, data = seeded_case(rng)
        call_id = f"toolu_{rng.randrange(10**8)}"
        model = FakeModel(
            responder=lambda r, name=name, data=data, call_id=call_id: (
                [ToolCall(call_id, name, data)] if r.tools else json.dumps(data)
            )
        )
        result = plain(run(model, text, schema, name, {"tool_choice"}))
        assert len(model.requests) == 1, (
            f"A valid call needs one request; the model was called {len(model.requests)} times."
        )
        sent = model.requests[0]
        assert sent.response_format is None, (
            "This provider has no native schema support, so do not send response_format."
        )
        assert [t["name"] for t in tool_view(sent)] == [name], (
            f"Offer exactly one tool, named {name!r}; "
            f"offered {[t['name'] for t in tool_view(sent)]}."
        )
        assert tool_view(sent)[0]["input_schema"] == plain(schema), (
            f"The tool's input_schema should be the schema itself, {schema}; got "
            f"{tool_view(sent)[0]['input_schema']}."
        )
        assert plain(sent.tool_choice) == {"name": name}, (
            f"Force the call with tool_choice={{'name': {name!r}}}; it was {sent.tool_choice!r}. "
            "Under 'auto' the model may answer in prose instead."
        )
        assert text in prompt_of(sent), "The text to extract from must reach the model."
        assert result == plain(data), (
            f"extract() should return the tool call's arguments, {data}; got {result}."
        )


def test_refusal_is_its_own_outcome():
    rng = random.Random(13)  # noqa: S311 - seeded, so grading is deterministic
    for supports in PATHS * 2:
        schema, name, text, _data = seeded_case(rng)
        reason = " ".join(rng.choices(WORDS, k=rng.randint(4, 9))) + f" ({rng.randrange(10**6)})"
        model = FakeModel(responder=lambda r, reason=reason: Refusal(reason))
        caught = None
        try:
            run(model, text, schema, name, supports)
        except Refused as error:
            caught = error
        except ValueError as error:
            raise AssertionError(
                f"With supports={sorted(supports)} the model refused (stop_reason 'refusal'), "
                f"but extract() raised ValueError ({error}). A refusal is not malformed output: "
                "check stop_reason first and raise Refused."
            ) from None
        assert caught is not None, (
            f"With supports={sorted(supports)} the model refused, so extract() should raise "
            "Refused."
        )
        assert getattr(caught, "text", None) == reason, (
            f"Refused.text should be the model's reply, {reason!r}; got "
            f"{getattr(caught, 'text', None)!r}."
        )
        assert len(model.requests) == 1, (
            f"Do not re-ask after a refusal (asking again will not change a policy decision); "
            f"the model was called {len(model.requests)} times."
        )


def broken_variants(rng, data):
    key = rng.choice(list(data))
    missing = {k: v for k, v in data.items() if k != key}
    wrong_type = {**data, key: [data[key]] if not isinstance(data[key], list) else "x"}
    extra = {**data, f"extra_{rng.randrange(100)}": 1}
    return [missing, wrong_type, extra]


def test_validates_native_replies():
    rng = random.Random(17)  # noqa: S311 - seeded, so grading is deterministic
    for _ in range(3):
        for supports in [{"response_format"}, BOTH, {"tool_choice"}]:
            schema, name, text, data = seeded_case(rng)
            replies = broken_variants(rng, data)
            if "response_format" in supports:
                replies.append(json.dumps(data)[:-3])  # cut short
            for reply in replies:
                if isinstance(reply, dict):
                    if "response_format" in supports:
                        reply = json.dumps(reply)
                    else:
                        reply = [ToolCall("toolu_1", name, reply)]
                model = FakeModel(responder=lambda r, reply=reply: reply)
                outcome = "returned"
                try:
                    run(model, text, schema, name, supports)
                except ValueError:
                    outcome = "raised"
                shown = reply if isinstance(reply, str) else dict(reply[0].arguments)
                assert outcome == "raised", (
                    f"With supports={sorted(supports)} the model sent {shown!r}, which breaks "
                    f"the schema {schema}, but extract() returned it. Validate even native "
                    "output (defence in depth) and raise ValueError when it does not fit."
                )
                assert len(model.requests) == 1, (
                    "On a native route a reply that breaks the schema is a provider bug, not a "
                    f"slip to correct: raise ValueError without re-asking. The model was called "
                    f"{len(model.requests)} times."
                )


def test_parse_and_repair_fallback():
    rng = random.Random(19)  # noqa: S311 - seeded, so grading is deterministic
    for round_ in range(6):
        schema, name, text, data = seeded_case(rng)
        good = json.dumps(data)
        dropped = rng.choice(list(data))
        if round_ % 2:
            bad = good[:-1] + ",}"  # trailing comma
            try:
                json.loads(bad)
            except json.JSONDecodeError as error:
                evidence = error.msg
        else:
            bad = json.dumps({k: v for k, v in data.items() if k != dropped})
            evidence = dropped
        model = FakeModel(
            responder=lambda r, bad=bad, good=good: bad if len(r.messages) == 1 else good
        )
        result = plain(run(model, text, schema, name, set()))
        first = model.requests[0]
        assert first.response_format is None and tool_view(first) == [], (
            "With no schema support at all, send neither response_format nor tools: the "
            "provider would reject them. Put the schema in the prompt instead."
        )
        prompt = prompt_of(first)
        assert text in prompt, "The text to extract from must reach the model."
        missing = [key for key in schema["properties"] if key not in prompt]
        assert not missing, (
            f"Without native support the model only knows the schema from the prompt, but "
            f"these field names were not in it: {missing}. Include the schema."
        )
        assert len(model.requests) == 2, (
            f"The first reply was invalid, so re-ask once: expected 2 calls, got "
            f"{len(model.requests)}."
        )
        retry = model.requests[1].messages
        assert [m.role for m in retry] == ["user", "assistant", "user"], (
            "The re-ask should send the original request, the bad reply as an assistant message, "
            f"then a user message with the error. Roles sent: {[m.role for m in retry]}."
        )
        assert retry[1].content == bad and evidence in retry[2].content, (
            f"The re-ask should send the bad reply back unchanged and say what was wrong (the "
            f"error should mention {evidence!r}); the user message was {retry[2].content!r}."
        )
        assert result == plain(data), (
            f"After the repair, extract() should return {data}; got {result}."
        )

    for _ in range(2):
        schema, name, text, data = seeded_case(rng)
        model = FakeModel(responder=lambda r, data=data: json.dumps(data))
        result = plain(run(model, text, schema, name, set()))
        assert result == plain(data) and len(model.requests) == 1, (
            f"A valid first reply needs no re-ask: expected {data} after 1 call, got {result} "
            f"after {len(model.requests)}."
        )

    schema, name, text, data = seeded_case(rng)
    missing = {k: v for k, v in data.items() if k != rng.choice(list(data))}
    model = FakeModel(
        responder=lambda r, missing=missing: (
            "{oops" if len(r.messages) == 1 else json.dumps(missing)
        )
    )
    outcome = "returned"
    try:
        run(model, text, schema, name, set())
    except ValueError:
        outcome = "raised"
    assert outcome == "raised" and len(model.requests) == 2, (
        "After two invalid replies, raise ValueError; the second reply here was valid JSON "
        f"that breaks the schema, so check it too. extract() {outcome} after "
        f"{len(model.requests)} calls; expected it to raise after exactly 2."
    )

    schema, name, text, _data = seeded_case(rng)
    reason = " ".join(rng.choices(WORDS, k=5)) + f" ({rng.randrange(10**6)})"
    model = FakeModel(
        responder=lambda r, reason=reason: "{oops" if len(r.messages) == 1 else Refusal(reason)
    )
    caught = None
    try:
        run(model, text, schema, name, set())
    except Refused as error:
        caught = error
    except ValueError as error:
        raise AssertionError(
            f"The re-ask was refused, but extract() raised ValueError ({error}): check "
            "stop_reason on every reply and raise Refused."
        ) from None
    assert getattr(caught, "text", None) == reason and len(model.requests) == 2, (
        f"The re-ask was refused, so extract() should raise Refused with text {reason!r} after "
        f"2 calls; got {caught!r} after {len(model.requests)}."
    )
