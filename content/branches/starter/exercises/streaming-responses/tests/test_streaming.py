"""Hidden checks. Learners see each check's title and, when it fails, the assertion message."""

import dataclasses
import json
import random

import pytest
from streaming import StreamInterrupted, stream_completion

from forgeway_kit import (
    Completion,
    FakeModel,
    InvalidRequestError,
    Message,
    MessageEnd,
    RateLimitError,
    Refusal,
    ServerError,
    StreamFailure,
    TextDelta,
    Tool,
    ToolCall,
    ToolCallDelta,
    ToolCallEnd,
    ToolCallStart,
    Usage,
)

WORDS = [
    "stream",
    "token",
    "delta",
    "reply",
    "model",
    "buffer",
    "socket",
    "latency",
    "user",
    "screen",
    "chunk",
    "event",
    "server",
    "partial",
    "final",
    "answer",
    "queue",
    "window",
    "cursor",
    "render",
    "flush",
]


def plain(value):
    """Learner results as plain built-ins, so a value cannot lie about equality."""
    return json.loads(json.dumps(value))


def as_dict(completion):
    assert isinstance(completion, Completion), (
        f"stream_completion() should return a forgeway_kit Completion, but returned "
        f"{type(completion).__name__}."
    )
    return plain(
        {
            "text": completion.text,
            "stop_reason": completion.stop_reason,
            "usage": dataclasses.asdict(completion.usage),
            "tool_calls": [
                {"id": c.id, "name": c.name, "arguments": dict(c.arguments)}
                for c in completion.tool_calls
            ],
        }
    )


def seeded_text(rng):
    """Reply text with spacing a careless join or strip would change."""
    parts = []
    for _ in range(rng.randint(14, 24)):
        parts.append(rng.choice(WORDS))
        parts.append(rng.choice([" ", " ", " ", ", ", ".\n", "  ", " - "]))
    return " " + "".join(parts).rstrip() + rng.choice(["\n", ".\n\n", "!  "])


def conversation(rng):
    return [
        Message(role="user", content=f"Tell me about {rng.choice(WORDS)} #{rng.randrange(10**6)}")
    ]


def recorder():
    shown = []

    def on_text(text):
        shown.append(text)

    return shown, on_text


def spying(model, log):
    """A client that streams from `model`, logging each event as the learner code pulls it."""

    class Spy:
        def stream(self, messages, **options):
            source = model.stream(messages, **options)

            def events():
                for event in source:
                    log.append(("event", event))
                    yield event

            return events()

    return Spy()


def test_shows_text_as_it_arrives():
    rng = random.Random(11)  # noqa: S311 - seeded, so grading is deterministic
    for _ in range(4):
        reply = seeded_text(rng)
        model = FakeModel(
            responder=lambda r, reply=reply: reply, stream_chunk_tokens=rng.randint(2, 4)
        )
        log = []

        def on_text(text, log=log):
            log.append(("shown", text))

        stream_completion(spying(model, log), conversation(rng), on_text)
        deltas = [e.text for kind, e in log if kind == "event" and isinstance(e, TextDelta)]
        assert len(deltas) > 3, "test bug: the reply should stream in several pieces"
        shown = [plain(e) for kind, e in log if kind == "shown"]
        assert shown == deltas, (
            f"on_text should be called once per TextDelta with exactly its text. The stream sent "
            f"{deltas!r}, but on_text received {shown!r}."
        )
        for index, (kind, event) in enumerate(log):
            if kind == "event" and isinstance(event, TextDelta):
                follows = log[index + 1] if index + 1 < len(log) else None
                assert follows is not None and follows[0] == "shown", (
                    f"Show each piece as soon as it arrives: on_text({event.text!r}) should be "
                    "called before the next event is read from the stream, but it was not. Do "
                    "not collect the whole stream first and show the text afterwards."
                )


def test_assembles_the_reply():
    rng = random.Random(23)  # noqa: S311 - seeded, so grading is deterministic
    replies = [seeded_text(rng) for _ in range(3)] + [Refusal(seeded_text(rng))]
    for reply in replies:
        messages = conversation(rng)
        chunk = rng.randint(1, 4)
        model = FakeModel(responder=lambda r, reply=reply: reply, stream_chunk_tokens=chunk)
        _shown, on_text = recorder()
        result = as_dict(stream_completion(model, list(messages), on_text))
        assert len(model.requests) == 1, (
            f"One reply needs one stream; client.stream was called {len(model.requests)} times."
        )
        sent = model.requests[0]
        assert [m.content for m in sent.messages] == [m.content for m in messages], (
            "Pass the conversation to client.stream unchanged."
        )
        want = as_dict(FakeModel(responder=lambda r, reply=reply: reply).complete(messages))
        assert result["text"] == want["text"], (
            f"The text should be every TextDelta joined exactly, with nothing added or "
            f"stripped: expected {want['text']!r}, got {result['text']!r}."
        )
        assert result["stop_reason"] == want["stop_reason"], (
            f"stop_reason should come from the MessageEnd event ({want['stop_reason']!r}), "
            f"got {result['stop_reason']!r}."
        )
        assert result["usage"] == want["usage"], (
            f"usage should be the MessageEnd event's ({want['usage']}), got {result['usage']}."
        )
        assert result["tool_calls"] == [], (
            f"This reply asked for no tools, but tool_calls was {result['tool_calls']}."
        )


TOOLS = [
    Tool("lookup_order", "Find an order.", {"type": "object", "properties": {}}),
    Tool("send_note", "Send a note.", {"type": "object", "properties": {}}),
    Tool("ping", "Check the service.", {"type": "object", "properties": {}}),
]
AWKWARD = ['say "hi"', "back\\slash", "line\nbreak", "café", "{not: json}", "tab\there", "ünï"]


def seeded_arguments(rng):
    return {
        f"k{rng.randrange(1000)}": rng.choice(AWKWARD),
        "count": rng.randrange(-50, 5000),
        "ratio": round(rng.random() * 100, 3),
        "nested": {
            "tags": [rng.choice(WORDS) for _ in range(rng.randint(0, 3))],
            "ok": rng.random() < 0.5,
        },
    }


def split_anywhere(text, rng):
    pieces, start = [], 0
    while start < len(text):
        end = start + rng.randint(1, 6)
        pieces.append(text[start:end])
        start = end
    return pieces


def interleaved_stream(rng):
    """Events for some text, then three tool calls whose events are interleaved, as a provider
    streaming parallel calls may send them. One call has no argument deltas at all."""
    text = seeded_text(rng)
    events = [TextDelta(p) for p in split_anywhere(text, rng)]
    calls = []
    per_call = []
    for index, tool in enumerate(rng.sample(TOOLS, 3)):
        call_id = f"call_{rng.randrange(16**8):08x}"
        arguments = {} if index == 1 else seeded_arguments(rng)
        calls.append(ToolCall(call_id, tool.name, arguments))
        body = json.dumps(arguments, ensure_ascii=rng.random() < 0.5) if arguments else ""
        per_call.append(
            [ToolCallStart(call_id, tool.name)]
            + [ToolCallDelta(call_id, p) for p in split_anywhere(body, rng)]
            + [ToolCallEnd(call_id)]
        )
    queues = [list(q) for q in per_call]
    started = 0
    while any(queues):
        # Calls start in order, but once started their events interleave at random.
        live = [q for q in queues[:started] if q]
        if started < len(queues) and (not live or rng.random() < 0.3):
            events.append(queues[started].pop(0))  # its ToolCallStart
            started += 1
            continue
        events.append(rng.choice(live).pop(0))
    usage = Usage(rng.randint(50, 400), rng.randint(20, 300))
    events.append(MessageEnd("tool_use", usage))
    return events, text, calls, usage


def scripted(events, seen):
    """A client whose stream plays `events`, recording what each call was sent."""

    class Scripted:
        def stream(self, messages, **options):
            seen.append({"messages": [m.content for m in messages], "options": options})
            return iter(list(events))

    return Scripted()


def no_parse_error(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except ValueError as error:
        raise AssertionError(
            f"Parsing a tool call's arguments failed ({type(error).__name__}: {error}). The "
            "fragments of one call are only valid JSON once all of them are joined, and only "
            "that call's fragments: collect each call's fragments by its id, and start each "
            "attempt with fresh state."
        ) from None


def test_assembles_interleaved_tool_calls():
    rng = random.Random(37)  # noqa: S311 - seeded, so grading is deterministic
    for _ in range(5):
        events, text, calls, usage = interleaved_stream(rng)
        seen = []
        _shown, on_text = recorder()
        messages = conversation(rng)
        result = as_dict(
            no_parse_error(
                stream_completion, scripted(events, seen), messages, on_text, tools=TOOLS
            )
        )
        assert len(seen) == 1, f"client.stream should be called once, not {len(seen)} times."
        sent_tools = [t.name for t in seen[0]["options"].get("tools", ())]
        assert sent_tools == [t.name for t in TOOLS], (
            f"Pass tools to client.stream; it received {sent_tools}."
        )
        want_calls = plain(
            [{"id": c.id, "name": c.name, "arguments": dict(c.arguments)} for c in calls]
        )
        assert [c["id"] for c in result["tool_calls"]] == [c["id"] for c in want_calls], (
            f"tool_calls should list every call once, in the order their ToolCallStart events "
            f"arrived: expected ids {[c['id'] for c in want_calls]}, got "
            f"{[c['id'] for c in result['tool_calls']]}."
        )
        for got, want in zip(result["tool_calls"], want_calls, strict=True):
            assert got == want, (
                f"Tool call {want['id']} should be {want}, but was {got}. Its arguments arrive as "
                "JSON fragments split anywhere, and fragments of different calls interleave: "
                "collect each call's fragments by its id, join them, and parse once at the end. "
                "A call with no fragments has the arguments {}."
            )
        assert result["text"] == text, (
            f"The text before the tool calls should be kept exactly: expected {text!r}, got "
            f"{result['text']!r}."
        )
        assert result["stop_reason"] == "tool_use" and result["usage"] == plain(
            dataclasses.asdict(usage)
        ), "stop_reason and usage should come from the MessageEnd event."


def failing(reply, after, error):
    """A responder that breaks the first stream after `after` events and serves the rest."""
    return lambda r: StreamFailure(after, error, reply) if r.sample == 0 else reply


def test_breaks_after_text_was_shown():
    rng = random.Random(41)  # noqa: S311 - seeded, so grading is deterministic
    for make_error in (ServerError, RateLimitError, ServerError, InvalidRequestError):
        reply = seeded_text(rng)
        after = rng.randint(2, 5)
        token = f"upstream-{rng.randrange(16**6):06x}"
        model = FakeModel(responder=failing(reply, after, make_error(token)))
        shown, on_text = recorder()
        caught = None
        try:
            stream_completion(model, conversation(rng), on_text)
        except StreamInterrupted as error:
            caught = error
        assert len(model.requests) == 1, (
            f"The stream broke after text had been shown, so do not start it again (the user "
            f"would see the start twice); client.stream was called {len(model.requests)} times."
        )
        pieces = [
            e.text
            for e in FakeModel(responder=lambda r, reply=reply: reply).stream(
                [Message(role="user", content="x")]
            )
            if isinstance(e, TextDelta)
        ][:after]
        assert plain(shown) == pieces, (
            f"Before it broke, on_text should have shown {pieces!r}; it showed {plain(shown)!r}."
        )
        assert caught is not None, (
            "A stream that breaks after text was shown should raise StreamInterrupted."
        )
        partial = getattr(caught, "partial_text", None)
        assert type(partial) is str and partial == "".join(pieces), (
            f"StreamInterrupted.partial_text should be exactly the text shown, "
            f"{''.join(pieces)!r}, but was {partial!r}."
        )
        error = getattr(caught, "error", None)
        assert type(error) is make_error and token in str(error), (
            f"StreamInterrupted.error should be the {make_error.__name__} the stream raised "
            f"({token}), but was {error!r}."
        )


def test_restarts_once_before_any_text():
    rng = random.Random(53)  # noqa: S311 - seeded, so grading is deterministic

    # Broken before the first event, then a good stream.
    for _ in range(2):
        reply = seeded_text(rng)
        model = FakeModel(
            responder=lambda r, reply=reply: (
                StreamFailure(0, ServerError("overloaded"), reply) if r.sample == 0 else reply
            )
        )
        shown, on_text = recorder()
        try:
            result = as_dict(stream_completion(model, conversation(rng), on_text))
        except ServerError:
            raise AssertionError(
                "The stream raised ServerError before any text was shown: nothing has reached "
                "the user, so start it again, once, instead of raising."
            ) from None
        assert len(model.requests) == 2, (
            f"The stream broke before any text was shown, so start it again, once; "
            f"client.stream was called {len(model.requests)} times."
        )
        assert result["text"] == reply and "".join(plain(shown)) == reply, (
            f"After the restart, the reply should be the second stream's text, {reply!r}; got "
            f"{result['text']!r} (shown: {''.join(plain(shown))!r})."
        )

    # Broken in the middle of a tool call, before any text: nothing of it may carry over.
    for _ in range(2):
        first = [ToolCall(f"call_{rng.randrange(10**6)}", "lookup_order", seeded_arguments(rng))]
        second = [
            ToolCall(f"call_{rng.randrange(10**6)}", t, seeded_arguments(rng))
            for t in ("send_note", "ping")
        ]
        model = FakeModel(
            responder=lambda r, first=first, second=second: (
                StreamFailure(3, RateLimitError("slow down", 0.0), first)
                if r.sample == 0
                else second
            )
        )
        shown, on_text = recorder()
        result = as_dict(
            no_parse_error(stream_completion, model, conversation(rng), on_text, tools=TOOLS)
        )
        want = plain([{"id": c.id, "name": c.name, "arguments": c.arguments} for c in second])
        assert result["tool_calls"] == want, (
            f"After a restart, the reply is the second stream alone. Expected tool_calls {want}, "
            f"got {result['tool_calls']}. Start each attempt with fresh state."
        )
        assert len(model.requests) == 2, (
            f"Expected one restart, but client.stream was called {len(model.requests)} times."
        )

    # Broken twice: give up with the second error.
    token = f"down-{rng.randrange(16**6):06x}"
    model = FakeModel(
        responder=lambda r: StreamFailure(0, ServerError(f"{token}-{r.sample}"), "never shown")
    )
    shown, on_text = recorder()
    with pytest.raises(ServerError) as info:
        stream_completion(model, conversation(rng), on_text)
    assert len(model.requests) == 2, (
        f"Restart at most once: when the second stream breaks too, raise its error. "
        f"client.stream was called {len(model.requests)} times."
    )
    assert f"{token}-1" in str(info.value), (
        f"When the restart breaks too, raise the second stream's error; got {info.value}."
    )

    # An invalid request fails the same way every time: never restart it.
    model = FakeModel(responder=lambda r: StreamFailure(0, InvalidRequestError("bad schema"), ""))
    shown, on_text = recorder()
    with pytest.raises(InvalidRequestError):
        stream_completion(model, conversation(rng), on_text)
    assert len(model.requests) == 1, (
        f"An InvalidRequestError will fail the same way again, so let it propagate without a "
        f"restart; client.stream was called {len(model.requests)} times."
    )
