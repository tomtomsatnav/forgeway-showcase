"""forgeway_kit.live against recorded wire fixtures; nothing here touches the network."""

import copy
import email.message
import io
import json
import pickle
import urllib.error
from pathlib import Path

import pytest

from forgeway_kit import (
    InvalidRequestError,
    Message,
    MessageEnd,
    RateLimitError,
    ServerError,
    TextDelta,
    Tool,
    ToolCall,
    ToolCallDelta,
    ToolCallEnd,
    ToolCallStart,
    Usage,
    live,
)

DATA = Path(__file__).parent / "data" / "live"
ANTHROPIC_KEY = "sk-ant-api03-SECRET-anthropic-key-value"
OPENAI_KEY = "sk-proj-SECRET-openai-key-value"
WEATHER = Tool("get_weather", "Weather for a city.", {"type": "object"})


class Wire:
    """Stands in for urlopen: records each request, answers with queued fixtures."""

    def __init__(self):
        self.sent = []
        self.replies = []

    def answer(self, name):
        self.replies.append((DATA / name).read_bytes())

    def __call__(self, request, timeout):
        self.sent.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return io.BytesIO(reply)

    @property
    def body(self):
        return json.loads(self.sent[-1].data)

    @property
    def headers(self):
        return {k.lower(): v for k, v in self.sent[-1].header_items()}


@pytest.fixture
def wire(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", ANTHROPIC_KEY)
    monkeypatch.setenv("OPENAI_API_KEY", OPENAI_KEY)
    monkeypatch.setattr(live, "_grading", lambda: False)
    fake = Wire()
    monkeypatch.setattr(live, "_urlopen", fake)
    return fake


def http_error(status, body, retry_after=None):
    headers = email.message.Message()
    if retry_after:
        headers["retry-after"] = retry_after
    return urllib.error.HTTPError("https://x", status, "error", headers, io.BytesIO(body))


CONVERSATION = [
    Message("user", "Weather in Paris and Rome?"),
    Message(
        "assistant",
        "Checking.",
        tool_calls=(
            ToolCall("t1", "get_weather", {"city": "Paris"}),
            ToolCall("t2", "get_weather", {"city": "Rome"}),
        ),
    ),
    Message("tool", "18C", tool_call_id="t1"),
    Message("tool", "21C", tool_call_id="t2"),
]


# ---- Anthropic ---------------------------------------------------------------------------


def test_anthropic_request_body_and_headers(wire):
    wire.answer("anthropic_message.json")
    client = live.AnthropicClient("claude-opus-5-5")
    client.complete(
        CONVERSATION,
        system="be brief",
        max_tokens=300,
        temperature=0.7,
        tools=[WEATHER],
        tool_choice={"name": "get_weather"},
        response_format={"type": "object"},
        effort="low",
    )
    assert wire.sent[-1].full_url == "https://api.anthropic.com/v1/messages"
    assert wire.headers["x-api-key"] == ANTHROPIC_KEY
    assert wire.headers["anthropic-version"] == live.ANTHROPIC_VERSION
    body = wire.body
    assert "temperature" not in body  # rejected by API version 2026-10-21
    assert body["model"] == "claude-opus-5-5"
    assert body["system"] == "be brief"
    assert body["max_tokens"] == 300
    assert body["tools"] == [
        {
            "name": "get_weather",
            "description": "Weather for a city.",
            "input_schema": {"type": "object"},
        }
    ]
    assert body["tool_choice"] == {"type": "tool", "name": "get_weather"}
    assert body["output_config"] == {
        "effort": "low",
        "format": {"type": "json_schema", "schema": {"type": "object"}},
    }
    assert body["messages"] == [
        {"role": "user", "content": "Weather in Paris and Rome?"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Checking."},
                {"type": "tool_use", "id": "t1", "name": "get_weather", "input": {"city": "Paris"}},
                {"type": "tool_use", "id": "t2", "name": "get_weather", "input": {"city": "Rome"}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "18C"},
                {"type": "tool_result", "tool_use_id": "t2", "content": "21C"},
            ],
        },
    ]


@pytest.mark.parametrize(("choice", "sent"), [("auto", "auto"), ("any", "any"), ("none", "none")])
def test_anthropic_tool_choice_strings(wire, choice, sent):
    wire.answer("anthropic_message.json")
    live.AnthropicClient().complete([Message("user", "q")], tools=[WEATHER], tool_choice=choice)
    assert wire.body["tool_choice"] == {"type": sent}


def test_anthropic_minimal_body_has_no_optional_fields(wire):
    wire.answer("anthropic_message.json")
    live.AnthropicClient().complete([Message("user", "q")], model="claude-sonnet-5-5")
    assert wire.body == {
        "model": "claude-sonnet-5-5",
        "max_tokens": 512,
        "messages": [{"role": "user", "content": "q"}],
    }


def test_anthropic_response_parsing_normalises_usage(wire):
    wire.answer("anthropic_message.json")
    completion = live.AnthropicClient().complete([Message("user", "q")], tools=[WEATHER])
    assert completion.text == "Let me look that up."
    assert completion.stop_reason == "tool_use"
    assert completion.tool_calls == (
        ToolCall("toolu_01A09q90qw90lq917835lq9", "get_weather", {"city": "Paris", "unit": "c"}),
    )
    # input_tokens is the whole prompt: uncached + cache reads + cache writes.
    assert completion.usage == Usage(150, 40, 100, 0)
    assert completion.model == "claude-opus-5-5"
    assert completion.latency_ms >= 0


def test_anthropic_refusal(wire):
    wire.answer("anthropic_refusal.json")
    completion = live.AnthropicClient().complete([Message("user", "q")])
    assert (completion.stop_reason, completion.text) == ("refusal", "")


def test_anthropic_sends_thinking_blocks_back_with_their_tool_turn(wire):
    wire.answer("anthropic_message.json")
    wire.answer("anthropic_message.json")
    client = live.AnthropicClient()
    first = client.complete([Message("user", "q")], tools=[WEATHER])
    turn = [
        Message("user", "q"),
        Message("assistant", first.text, tool_calls=first.tool_calls),
        Message("tool", "18C", tool_call_id=first.tool_calls[0].id),
    ]
    client.complete(turn, tools=[WEATHER])
    sent = wire.body["messages"][1]["content"]
    assert sent[0]["type"] == "thinking"
    assert sent[0]["signature"].startswith("EqQB")
    assert sent == json.loads((DATA / "anthropic_message.json").read_text())["content"]


def test_anthropic_stream_events(wire):
    wire.answer("anthropic_stream.sse")
    events = list(live.AnthropicClient().stream([Message("user", "q")], tools=[WEATHER]))
    assert wire.body["stream"] is True
    assert events == [
        TextDelta("Checking the "),
        TextDelta("weather."),
        ToolCallStart("toolu_01Stream", "get_weather"),
        ToolCallDelta("toolu_01Stream", ""),
        ToolCallDelta("toolu_01Stream", '{"city": "Pa'),
        ToolCallDelta("toolu_01Stream", 'ris"}'),
        ToolCallEnd("toolu_01Stream"),
        MessageEnd("tool_use", Usage(225, 57, 200, 0)),
    ]


def test_anthropic_stream_keeps_the_streamed_turn_for_the_next_request(wire):
    wire.answer("anthropic_stream.sse")
    wire.answer("anthropic_message.json")
    client = live.AnthropicClient()
    list(client.stream([Message("user", "q")], tools=[WEATHER]))
    call = ToolCall("toolu_01Stream", "get_weather", {"city": "Paris"})
    client.complete(
        [
            Message("user", "q"),
            Message("assistant", "Checking the weather.", tool_calls=(call,)),
            Message("tool", "18C", tool_call_id=call.id),
        ]
    )
    blocks = wire.body["messages"][1]["content"]
    assert [b["type"] for b in blocks] == ["thinking", "text", "tool_use"]
    assert blocks[0]["signature"] == "EqQBCgIYAhIMsig"
    assert blocks[2]["input"] == {"city": "Paris"}


def test_anthropic_stream_error_event_raises_partway(wire):
    wire.answer("anthropic_stream_error.sse")
    seen = []
    with pytest.raises(ServerError, match="overloaded_error"):
        for event in live.AnthropicClient().stream([Message("user", "q")]):
            seen.append(event)
    assert seen == [TextDelta("Hel")]


# ---- errors and the key ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "error", "kind"),
    [
        (400, "invalid_request_error", InvalidRequestError),
        (500, "api_error", ServerError),
        (529, "overloaded_error", ServerError),
    ],
)
def test_http_errors_map_to_toolkit_errors(wire, status, error, kind):
    body = json.dumps({"type": "error", "error": {"type": error, "message": "nope"}}).encode()
    wire.replies.append(http_error(status, body))
    with pytest.raises(kind, match=f"{status} from https://api.anthropic.com: nope"):
        live.AnthropicClient().complete([Message("user", "q")])


def test_rate_limits_carry_retry_after(wire):
    wire.replies.append(http_error(429, b'{"error": {"message": "slow down"}}', retry_after="7"))
    with pytest.raises(RateLimitError) as caught:
        live.OpenAIClient("gpt-test-mini").complete([Message("user", "q")])
    assert caught.value.retry_after_s == 7.0


def test_the_key_never_appears_in_errors(wire):
    echoed = json.dumps({"error": {"message": f"bad key {ANTHROPIC_KEY}"}}).encode()
    wire.replies.append(http_error(401, echoed))
    wire.replies.append(urllib.error.URLError(f"proxy refused {ANTHROPIC_KEY}"))
    client = live.AnthropicClient()
    for _ in range(2):
        with pytest.raises((InvalidRequestError, ServerError)) as caught:
            client.complete([Message("user", "q")])
        assert ANTHROPIC_KEY not in str(caught.value)
        assert "[redacted]" in str(caught.value)
        assert caught.value.__cause__ is None and caught.value.__suppress_context__


def test_the_key_never_appears_in_repr_vars_or_a_pickle(wire):
    clients = [
        live.AnthropicClient(),
        live.OpenAIClient("gpt-test-mini"),
        live.Metered(live.AnthropicClient()),
    ]
    for client in clients:
        assert ANTHROPIC_KEY not in repr(client) and OPENAI_KEY not in repr(client)
        inner = getattr(client, "client", client)
        assert ANTHROPIC_KEY not in repr(vars(inner)) and OPENAI_KEY not in repr(vars(inner))
        with pytest.raises(TypeError, match="cannot be pickled"):
            pickle.dumps(inner)
        with pytest.raises(TypeError):
            copy.deepcopy(inner)


def test_keys_come_from_the_environment(monkeypatch):
    monkeypatch.setattr(live, "_grading", lambda: False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is not set"):
        live.AnthropicClient()
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not set"):
        live.OpenAIClient("gpt-test-mini")
    local = live.OpenAIClient("llama3", base_url="http://localhost:11434/v1")  # no key needed
    assert local.base_url == "http://localhost:11434/v1"


def test_live_clients_refuse_to_exist_while_grading(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", ANTHROPIC_KEY)
    monkeypatch.setenv("FORGEWAY_GRADING", "1")
    with pytest.raises(RuntimeError, match="never used while grading"):
        live.AnthropicClient()


def test_metered_refuses_to_price_while_grading(monkeypatch):
    monkeypatch.setenv("FORGEWAY_GRADING", "1")
    with pytest.raises(RuntimeError, match="never used while grading"):
        live.Metered(object())
    # Skipping __init__ must not reach the arithmetic either.
    with pytest.raises(RuntimeError, match="never used while grading"):
        live.Metered._report(object(), "m", Usage(1, 1), 1.0)


# ---- OpenAI ------------------------------------------------------------------------------


def test_openai_request_body(wire):
    wire.answer("openai_completion.json")
    live.OpenAIClient("gpt-test-mini").complete(
        CONVERSATION,
        system="be brief",
        max_tokens=300,
        tools=[WEATHER],
        tool_choice="any",
        response_format={"type": "object"},
        effort="high",
    )
    assert wire.sent[-1].full_url == "https://api.openai.com/v1/chat/completions"
    assert wire.headers["authorization"] == f"Bearer {OPENAI_KEY}"
    body = wire.body
    assert body["max_completion_tokens"] == 300
    assert "max_tokens" not in body and "temperature" not in body
    assert body["tool_choice"] == "required"
    assert body["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Weather for a city.",
                "parameters": {"type": "object"},
            },
        }
    ]
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "response", "schema": {"type": "object"}, "strict": True},
    }
    assert body["reasoning_effort"] == "high"
    assert body["messages"] == [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "Weather in Paris and Rome?"},
        {
            "role": "assistant",
            "content": "Checking.",
            "tool_calls": [
                {
                    "id": "t1",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": '{"city": "Paris"}'},
                },
                {
                    "id": "t2",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": '{"city": "Rome"}'},
                },
            ],
        },
        {"role": "tool", "tool_call_id": "t1", "content": "18C"},
        {"role": "tool", "tool_call_id": "t2", "content": "21C"},
    ]


def test_openai_compatible_server(wire, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    wire.answer("openai_completion.json")
    client = live.OpenAIClient("llama3", base_url="http://localhost:11434/v1/")
    client.complete(
        [Message("user", "q")],
        temperature=0.4,
        tools=[WEATHER],
        tool_choice={"name": "get_weather"},
    )
    assert wire.sent[-1].full_url == "http://localhost:11434/v1/chat/completions"
    assert "authorization" not in wire.headers
    assert (wire.body["max_tokens"], wire.body["temperature"]) == (512, 0.4)
    assert wire.body["tool_choice"] == {"type": "function", "function": {"name": "get_weather"}}


def test_openai_response_parsing(wire):
    wire.answer("openai_completion.json")
    completion = live.OpenAIClient("gpt-test-mini").complete(
        [Message("user", "q")], tools=[WEATHER]
    )
    assert completion.tool_calls == (ToolCall("call_abc123", "get_weather", {"city": "Paris"}),)
    assert completion.stop_reason == "tool_use"
    assert completion.usage == Usage(1117, 46, 1024, 32)
    assert completion.model == "gpt-test-mini"


def test_openai_refusal(wire):
    wire.answer("openai_refusal.json")
    completion = live.OpenAIClient("gpt-test-mini").complete([Message("user", "q")])
    assert (completion.stop_reason, completion.text) == ("refusal", "I can't help with that.")


def test_openai_stream_events(wire):
    wire.answer("openai_stream.sse")
    events = list(
        live.OpenAIClient("gpt-test-mini").stream([Message("user", "q")], tools=[WEATHER])
    )
    assert wire.body["stream"] is True
    assert wire.body["stream_options"] == {"include_usage": True}
    assert events == [
        TextDelta("Checking "),
        TextDelta("now."),
        ToolCallStart("call_s1", "get_weather"),
        ToolCallDelta("call_s1", '{"ci'),
        ToolCallDelta("call_s1", 'ty":"Paris"}'),
        ToolCallEnd("call_s1"),
        MessageEnd("tool_use", Usage(50, 12, 32, 0)),
    ]


# ---- Metered, configuration and the check command ----------------------------------------


def test_metered_prints_tokens_latency_and_cost(wire):
    wire.answer("anthropic_message.json")
    out = io.StringIO()
    metered = live.Metered(live.AnthropicClient(), out=out)
    completion = metered.complete([Message("user", "q")], tools=[WEATHER])
    assert completion.usage.input_tokens == 150
    line = out.getvalue()
    assert line.startswith("[forgeway] claude-opus-5-5  in 150 (cache 100)  out 40 (reasoning 0)")
    # (50 fresh * $4 + 40 out * $20 + 100 cached * $0.20) per million
    assert line.rstrip().endswith("~$0.0010")
    assert ANTHROPIC_KEY not in line


def test_metered_streams_and_takes_custom_rates(wire):
    wire.answer("openai_stream.sse")
    out = io.StringIO()
    metered = live.Metered(
        live.OpenAIClient("gpt-test-mini"), rates={"gpt-test-mini": (1e6, 0, 0)}, out=out
    )
    events = list(metered.stream([Message("user", "q")]))
    assert isinstance(events[-1], MessageEnd)
    assert "gpt-test-mini  in 50 (cache 32)  out 12" in out.getvalue()
    assert out.getvalue().rstrip().endswith("~$18.0000")


def test_metered_says_when_it_cannot_price_a_model(wire):
    wire.answer("openai_refusal.json")
    out = io.StringIO()
    live.Metered(live.OpenAIClient("gpt-test-mini"), out=out).complete([Message("user", "q")])
    assert "cost unknown" in out.getvalue()


@pytest.mark.parametrize(
    ("env", "error"),
    [
        ({"FORGEWAY_LIVE": "gemini"}, "must be anthropic, openai or openai-compatible"),
        ({"FORGEWAY_LIVE": "openai"}, "FORGEWAY_MODEL"),
        ({"FORGEWAY_LIVE": "openai-compatible", "FORGEWAY_MODEL": "llama3"}, "FORGEWAY_BASE_URL"),
    ],
)
def test_client_from_env_explains_bad_settings(wire, monkeypatch, env, error):
    for name in ("FORGEWAY_LIVE", "FORGEWAY_MODEL", "FORGEWAY_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError, match=error):
        live.client_from_env()


def test_check_makes_one_tiny_call(wire, monkeypatch, capsys):
    monkeypatch.setenv("FORGEWAY_LIVE", "anthropic")
    monkeypatch.delenv("FORGEWAY_MODEL", raising=False)
    monkeypatch.delenv("FORGEWAY_BASE_URL", raising=False)
    wire.answer("anthropic_message.json")
    assert live.main(["check"]) == 0
    assert len(wire.sent) == 1
    assert wire.body["max_tokens"] == 256
    assert wire.body["output_config"] == {"effort": "low"}
    printed = capsys.readouterr()
    assert "claude-opus-5-5: 'Let me look that up.'" in printed.out
    assert "[forgeway] claude-opus-5-5" in printed.err
    assert ANTHROPIC_KEY not in printed.out + printed.err
    assert live.main([]) == 2
