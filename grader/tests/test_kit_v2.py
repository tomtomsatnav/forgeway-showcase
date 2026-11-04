"""Toolkit v2: the FakeModel additions. Everything is optional, so old calls behave as before."""

import json
import threading

import pytest

from forgeway_kit import (
    Completion,
    FakeModel,
    InvalidRequestError,
    Message,
    MessageEnd,
    ModelCard,
    RateLimit,
    RateLimitError,
    Refusal,
    Request,
    ServerError,
    StreamFailure,
    TextDelta,
    Tool,
    ToolCall,
    ToolCallDelta,
    ToolCallEnd,
    ToolCallStart,
    Usage,
    count_tokens,
    default_client,
    llm,
    use_client,
)

WEATHER = Tool("weather", "Look up the weather.", {"type": "object"})
CLOCK = Tool("clock", "Tell the time.", {"type": "object"})
CHEAP = ModelCard("cheap", 0.1, 0.5, 0.01, 100.0, 2.0, 50)
SMART = ModelCard("smart", 4.0, 20.0, 0.2, 500.0, 10.0, 8000)


def user(text):
    return [Message("user", text)]


# ---- backward compatibility --------------------------------------------------------------


def test_old_positional_constructors_still_work():
    assert Usage(3, 4) == Usage(3, 4, 0, 0)
    completion = Completion("hi", "end_turn", Usage(1, 1))
    assert (completion.model, completion.latency_ms, completion.tool_calls) == ("", 0.0, ())
    request = Request((Message("user", "x"),), None, 512, 0.0, ())
    assert (request.model, request.tool_choice, request.effort, request.sample) == (
        "",
        "auto",
        None,
        0,
    )
    assert request.response_format is None


def test_plain_calls_report_what_they_did_before():
    model = FakeModel(responder=lambda _: "one two three")
    completion = model.complete(user("hello there"), system="be brief")
    assert completion == Completion("one two three", "end_turn", Usage(4, 3))
    assert model.requests[0] == Request((Message("user", "hello there"),), "be brief", 512, 0.0)


# ---- models, latency and the context window ----------------------------------------------


def test_model_cards_route_and_set_latency():
    model = FakeModel(responder=lambda r: f"{r.model} answers", models=[CHEAP, SMART])
    first = model.complete(user("hi"))
    assert (first.model, model.requests[0].model) == ("cheap", "cheap")  # the first card
    assert first.latency_ms == 100.0 + 2.0 * 2
    second = model.complete(user("hi"), model="smart")
    assert (second.text, second.latency_ms) == ("smart answers", 500.0 + 10.0 * 2)


def test_default_model_and_unknown_model():
    model = FakeModel(models=[CHEAP, SMART], default_model="smart")
    assert model.complete(user("hi")).model == "smart"
    with pytest.raises(InvalidRequestError, match="unknown model 'gpt'"):
        model.complete(user("hi"), model="gpt")
    assert model.requests[-1].model == "gpt"  # recorded, like any failed request
    with pytest.raises(ValueError, match="not one of"):
        FakeModel(models=[CHEAP], default_model="smart")
    with pytest.raises(ValueError, match="unique"):
        FakeModel(models=[CHEAP, CHEAP])


def test_without_cards_any_model_name_is_recorded():
    model = FakeModel(default_model="house")
    assert model.complete(user("a")).model == "house"
    assert model.complete(user("a"), model="other").model == "other"
    assert FakeModel().complete(user("a")).model == ""


def test_a_cards_context_window_overrides_the_fakes():
    model = FakeModel(models=[CHEAP, SMART], context_window=10)
    long = " ".join(["word"] * 60)
    model.complete(user(long), model="smart")
    with pytest.raises(InvalidRequestError, match="context window is 50"):
        model.complete(user(long), model="cheap")


# ---- prompt cache ------------------------------------------------------------------------


def test_cache_reads_count_the_identical_leading_blocks():
    model = FakeModel(responder=lambda _: "ok")
    turn1 = [Message("user", "first question here")]
    turn2 = [*turn1, Message("assistant", "an answer"), Message("user", "second one")]
    assert model.complete(turn1, system="sys prompt").usage.cache_read_input_tokens == 0
    usage = model.complete(turn2, system="sys prompt").usage
    assert usage.cache_read_input_tokens == count_tokens("sys prompt first question here")
    assert usage.input_tokens == count_tokens("sys prompt first question here an answer second one")


@pytest.mark.parametrize(
    "change",
    [
        {"system": "other system"},
        {"tools": [CLOCK]},
        {"model": "elsewhere"},
    ],
)
def test_a_changed_first_block_or_model_reads_nothing_from_cache(change):
    model = FakeModel(responder=lambda _: "ok")
    model.complete(user("same words"), system="sys", tools=[WEATHER])
    options = {"system": "sys", "tools": [WEATHER], **change}
    assert model.complete(user("same words"), **options).usage.cache_read_input_tokens == 0


def test_cache_stops_at_the_first_differing_message():
    model = FakeModel(responder=lambda _: "ok")
    a = [Message("user", "one"), Message("assistant", "two"), Message("user", "three")]
    b = [Message("user", "one"), Message("assistant", "TWO"), Message("user", "three")]
    model.complete(a)
    assert model.complete(b).usage.cache_read_input_tokens == 1


# ---- sample counter ----------------------------------------------------------------------


def test_sample_counts_earlier_identical_requests():
    model = FakeModel(responder=lambda r: f"answer {r.sample}")
    texts = [model.complete(user("q")).text for _ in range(3)]
    assert texts == ["answer 0", "answer 1", "answer 2"]
    assert model.complete(user("other")).text == "answer 0"
    assert model.complete(user("q"), temperature=0.7).text == "answer 0"  # not the same request
    assert [r.sample for r in model.requests] == [0, 1, 2, 0, 0]


# ---- rate limit --------------------------------------------------------------------------


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_rate_limit_uses_the_injected_clock():
    clock = FakeClock()
    model = FakeModel(rate_limit=RateLimit(2, 10), clock=clock)
    model.complete(user("a"))
    clock.now += 4
    model.complete(user("b"))
    with pytest.raises(RateLimitError) as caught:
        model.complete(user("c"))
    assert caught.value.retry_after_s == pytest.approx(6.0)
    assert len(model.requests) == 3  # rate-limited requests are recorded too
    clock.now += 6.01
    model.complete(user("d"))  # the first request has left the window


def test_rate_limit_is_thread_safe():
    model = FakeModel(rate_limit=RateLimit(5, 60), clock=FakeClock())
    start = threading.Barrier(20)
    outcomes = []

    def call(i):
        start.wait()
        try:
            model.complete(user(f"q{i}"))
            outcomes.append("ok")
        except RateLimitError:
            outcomes.append("limited")

    threads = [threading.Thread(target=call, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(outcomes) == ["limited"] * 15 + ["ok"] * 5
    assert len(model.requests) == 20


def test_rate_limit_validates_itself():
    with pytest.raises(ValueError):
        RateLimit(0, 1)
    with pytest.raises(ValueError):
        RateLimit(1, 0)


# ---- tool_choice -------------------------------------------------------------------------


def test_tool_choice_is_recorded_as_plain_data():
    model = FakeModel(responder=lambda _: [ToolCall("1", "weather", {})])
    model.complete(user("q"), tools=[WEATHER, CLOCK], tool_choice={"name": "weather"})
    assert model.requests[0].tool_choice == {"name": "weather"}
    assert type(model.requests[0].tool_choice) is dict


@pytest.mark.parametrize(
    ("choice", "reply", "error"),
    [
        ("any", "just text", "must ask for a tool"),
        ("any", [], "must ask for a tool"),
        ({"name": "weather"}, "text", "must ask for a tool"),
        ({"name": "weather"}, [ToolCall("1", "clock", {})], "may call only it"),
        ("none", [ToolCall("1", "clock", {})], "must not ask for tools"),
    ],
)
def test_a_responder_that_breaks_tool_choice_is_a_test_bug(choice, reply, error):
    model = FakeModel(responder=lambda _: reply)
    with pytest.raises(ValueError, match=error):
        model.complete(user("q"), tools=[WEATHER, CLOCK], tool_choice=choice)


@pytest.mark.parametrize(
    ("choice", "reply"),
    [
        ("auto", "text"),
        ("auto", [ToolCall("1", "clock", {})]),
        ("any", [ToolCall("1", "clock", {})]),
        ("none", "text"),
        ({"name": "clock"}, [ToolCall("1", "clock", {}), ToolCall("2", "clock", {})]),
    ],
)
def test_responders_that_follow_tool_choice_pass(choice, reply):
    model = FakeModel(responder=lambda _: reply)
    model.complete(user("q"), tools=[WEATHER, CLOCK], tool_choice=choice)


def test_impossible_tool_choices_are_rejected_like_a_provider_would():
    model = FakeModel()
    with pytest.raises(InvalidRequestError, match="not offered"):
        model.complete(user("q"), tools=[WEATHER], tool_choice={"name": "clock"})
    with pytest.raises(InvalidRequestError, match="at least one tool"):
        model.complete(user("q"), tool_choice="any")
    with pytest.raises(ValueError, match="tool_choice must be"):
        model.complete(user("q"), tool_choice="required")
    with pytest.raises(ValueError, match="exactly"):
        model.complete(user("q"), tool_choice={"tool": "clock"})
    with pytest.raises(TypeError, match="tool_choice must be a str or a dict"):
        model.complete(user("q"), tool_choice=3)


# ---- response_format, refusal and effort -------------------------------------------------


def test_response_format_is_recorded_and_the_reply_is_unchanged():
    class Sly(dict):
        def __eq__(self, other):
            return True

    model = FakeModel(responder=lambda _: '{"a": 1}')
    schema = Sly(type="object", properties={"a": {"type": "integer"}})
    assert model.complete(user("q"), response_format=schema).text == '{"a": 1}'
    recorded = model.requests[0].response_format
    assert type(recorded) is dict
    assert recorded == {"type": "object", "properties": {"a": {"type": "integer"}}}
    with pytest.raises(TypeError, match="response_format must be a dict"):
        model.complete(user("q"), response_format="json")


def test_a_refusal_stops_with_refusal_even_when_a_tool_is_forced():
    model = FakeModel(responder=lambda _: Refusal("I can't help with that."))
    completion = model.complete(user("q"), tools=[WEATHER], tool_choice="any")
    assert (completion.text, completion.stop_reason) == ("I can't help with that.", "refusal")
    assert completion.usage.output_tokens == count_tokens("I can't help with that.")


@pytest.mark.parametrize(("effort", "reasoning"), [("low", 16), ("medium", 64), ("high", 256)])
def test_effort_adds_reasoning_tokens_billed_as_output(effort, reasoning):
    model = FakeModel(responder=lambda _: "two words", models=[SMART])
    completion = model.complete(user("q"), effort=effort)
    assert completion.usage.reasoning_tokens == reasoning
    assert completion.usage.output_tokens == 2 + reasoning
    assert completion.latency_ms == 500.0 + 10.0 * (2 + reasoning)
    assert model.requests[0].effort == effort


def test_effort_is_validated():
    with pytest.raises(ValueError, match="effort must be"):
        FakeModel().complete(user("q"), effort="max")


# ---- streaming ---------------------------------------------------------------------------


def test_streamed_text_arrives_in_chunks_that_join_back():
    reply = "The quick, brown fox jumps over the lazy dog.  Twice!"
    model = FakeModel(responder=lambda _: reply, stream_chunk_tokens=2)
    events = list(model.stream(user("q")))
    deltas = [e for e in events if isinstance(e, TextDelta)]
    assert "".join(d.text for d in deltas) == reply
    assert all(1 <= count_tokens(d.text) <= 2 for d in deltas)
    fresh = FakeModel(responder=lambda _: reply).complete(user("q"))
    assert events[-1] == MessageEnd("end_turn", fresh.usage)
    assert len(model.requests) == 1  # the stream was recorded


def test_streamed_tool_calls_split_their_json_and_rebuild():
    calls = [
        ToolCall("a1", "weather", {"city": "Paris", "days": [1, 2]}),
        ToolCall("b2", "clock", {}),
    ]
    model = FakeModel(responder=lambda _: calls)
    events = list(model.stream(user("q"), tools=[WEATHER, CLOCK]))
    assert events[0] == ToolCallStart("a1", "weather")
    for call in calls:
        start = events.index(ToolCallStart(call.id, call.name))
        end = events.index(ToolCallEnd(call.id))
        pieces = events[start + 1 : end]
        assert all(isinstance(p, ToolCallDelta) and p.id == call.id for p in pieces)
        assert json.loads("".join(p.partial_json for p in pieces)) == call.arguments
    assert len([e for e in events if isinstance(e, ToolCallDelta) and e.id == "a1"]) > 1
    assert events[-1].stop_reason == "tool_use"
    again = list(model.stream(user("q"), tools=[WEATHER, CLOCK]))
    assert events[:-1] == again[:-1]  # deterministic


def test_a_truncated_stream_ends_with_max_tokens():
    model = FakeModel(responder=lambda _: "one two three four")
    events = list(model.stream(user("q"), max_tokens=2))
    assert "".join(e.text for e in events if isinstance(e, TextDelta)) == "one two"
    assert events[-1].stop_reason == "max_tokens"


def test_a_stream_failure_raises_partway_and_complete_raises_at_once():
    failure = StreamFailure(
        after_events=2, error=ServerError("connection reset"), reply="a b c d e f g h"
    )
    model = FakeModel(responder=lambda _: failure, stream_chunk_tokens=1)
    seen = []
    with pytest.raises(ServerError, match="connection reset"):
        for event in model.stream(user("q")):
            seen.append(event)
    assert seen == [TextDelta("a"), TextDelta(" b")]
    with pytest.raises(ServerError):
        model.complete(user("q"))
    assert len(model.requests) == 2


def test_a_late_stream_failure_still_withholds_message_end():
    failure = StreamFailure(after_events=99, error=ServerError("gone"), reply="short")
    events = []
    with pytest.raises(ServerError):
        for event in FakeModel(responder=lambda _: failure).stream(user("q")):
            events.append(event)
    assert events == [TextDelta("short")]


def test_stream_validates_like_complete_when_called():
    model = FakeModel(rate_limit=RateLimit(1, 60), clock=FakeClock())
    model.stream(user("q"))
    with pytest.raises(RateLimitError):
        model.stream(user("q"))  # raised on the call, before iteration
    with pytest.raises(ValueError, match="after_events"):
        StreamFailure(after_events=-1, error=ServerError())
    with pytest.raises(TypeError, match="exception instance"):
        StreamFailure(after_events=1, error="boom")


# ---- default_client and live mode --------------------------------------------------------


def test_a_configured_client_always_wins_over_live_settings(monkeypatch):
    monkeypatch.setenv("FORGEWAY_LIVE", "anthropic")
    monkeypatch.setattr(llm, "_grading", lambda: False)
    model = FakeModel()
    with use_client(model):
        assert default_client() is model


def test_grading_never_builds_a_live_client(monkeypatch):
    monkeypatch.setenv("FORGEWAY_LIVE", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
    monkeypatch.setenv("FORGEWAY_GRADING", "1")
    with pytest.raises(RuntimeError, match="no model client"):
        default_client()


def test_outside_grading_live_settings_build_a_metered_client(monkeypatch):
    from forgeway_kit import live

    monkeypatch.setenv("FORGEWAY_LIVE", "anthropic")
    monkeypatch.setenv("FORGEWAY_MODEL", "claude-sonnet-5-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
    monkeypatch.setattr(llm, "_grading", lambda: False)
    monkeypatch.setattr(live, "_grading", lambda: False)
    monkeypatch.setattr(llm, "_live", [])
    client = default_client()
    assert isinstance(client, live.Metered)
    assert isinstance(client.client, live.AnthropicClient)
    assert client.client.model == "claude-sonnet-5-5"
    assert default_client() is client


# ---- across the bridge (isolation: process) ----------------------------------------------

BRIDGED = """
from forgeway_kit import Message, ServerError, RateLimitError, TextDelta, ToolCallDelta, MessageEnd

def stream_text(client):
    parts, end = [], None
    for event in client.stream([Message("user", "q")], model="smart", effort="low"):
        if isinstance(event, TextDelta):
            parts.append(event.text)
        elif isinstance(event, MessageEnd):
            end = event
    return "".join(parts), end.stop_reason, end.usage.reasoning_tokens

def stream_until_failure(client):
    seen = []
    try:
        for event in client.stream([Message("user", "q")]):
            seen.append(type(event).__name__)
    except ServerError as exc:
        return seen, str(exc)

def complete_twice(client):
    first = client.complete([Message("user", "q")], tool_choice="none", response_format={"a": 1})
    try:
        client.complete([Message("user", "q")])
    except RateLimitError as exc:
        return first.model, first.latency_ms, first.usage.cache_read_input_tokens, exc.retry_after_s
"""


def test_the_new_api_crosses_the_bridge(tmp_path):
    import importlib

    from lattice_grader import bridge

    (tmp_path / "bridged_mod.py").write_text(BRIDGED)
    installed = bridge.install(tmp_path, timeout=5)
    try:
        learner = importlib.import_module("bridged_mod")
        model = FakeModel(responder=lambda _: "one two three four five", models=[CHEAP, SMART])
        assert learner.stream_text(model) == ("one two three four five", "end_turn", 16)
        assert model.requests[0].model == "smart" and model.requests[0].effort == "low"

        failing = FakeModel(
            responder=lambda _: StreamFailure(2, ServerError("dropped"), "a b c d e f g h")
        )
        assert learner.stream_until_failure(failing) == (["TextDelta", "TextDelta"], "dropped")

        limited = FakeModel(models=[CHEAP], rate_limit=RateLimit(1, 30), clock=FakeClock())
        assert learner.complete_twice(limited) == ("cheap", 100.0 + 2.0, 0, 30.0)
        assert limited.requests[0].response_format == {"a": 1}
    finally:
        bridge.uninstall(installed)
