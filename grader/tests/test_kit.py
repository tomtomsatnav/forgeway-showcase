import pytest

from forgeway_kit import (
    FakeModel,
    HashingEmbedder,
    InvalidRequestError,
    Message,
    RateLimitError,
    Tool,
    ToolCall,
    cosine_similarity,
    count_tokens,
    default_client,
    tokenize,
    use_client,
)


def test_fake_model_records_requests_and_reports_usage():
    model = FakeModel(responder=lambda req: f"you said {req.messages[-1].content}")
    completion = model.complete([Message("user", "hello there")], system="be brief", max_tokens=50)
    assert completion.text == "you said hello there"
    assert completion.stop_reason == "end_turn"
    assert completion.usage.input_tokens == 4  # "hello there" + "be brief"
    assert model.requests[0].system == "be brief"


def test_fake_model_truncates_at_max_tokens():
    completion = FakeModel(responder=lambda _: "one two three four").complete(
        [Message("user", "count")], max_tokens=2
    )
    assert completion.text == "one two"
    assert completion.stop_reason == "max_tokens"


@pytest.mark.parametrize(
    ("messages", "error"),
    [([], "must not be empty"), ([Message("assistant", "hi")], "last message")],
)
def test_fake_model_rejects_malformed_conversations(messages, error):
    with pytest.raises(ValueError, match=error):
        FakeModel().complete(messages)


def test_default_client_is_scoped():
    model = FakeModel()
    with use_client(model):
        assert default_client() is model
    with pytest.raises(RuntimeError, match="no model client"):
        default_client()


def test_hashing_embedder_is_deterministic_normalised_and_lexical():
    embedder = HashingEmbedder(dimensions=128)
    a, b, c = embedder.embed(
        ["vector databases store embeddings", "embeddings live in vector databases", "bake bread"]
    )
    assert a == embedder.embed(["vector databases store embeddings"])[0]
    assert sum(x * x for x in a) == pytest.approx(1.0)
    assert cosine_similarity(a, b) > cosine_similarity(a, c)


def test_cosine_similarity_handles_zero_vectors_and_length_mismatch():
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
    with pytest.raises(ValueError):
        cosine_similarity([1.0], [1.0, 2.0])


def test_token_counting_splits_words_and_punctuation():
    assert tokenize("Hello, world!") == ["Hello", ",", "world", "!"]
    assert count_tokens("") == 0


def test_truncation_keeps_original_spacing():
    completion = FakeModel(responder=lambda _: "Hello, big world.").complete(
        [Message("user", "hi")], max_tokens=3
    )
    assert completion.text == "Hello, big"


def test_prompts_over_the_context_window_are_rejected():
    model = FakeModel(context_window=3)
    with pytest.raises(InvalidRequestError, match="context window is 3"):
        model.complete([Message("user", "one two three four")])


def test_responders_can_simulate_rate_limits():
    def flaky(_request):
        raise RateLimitError(retry_after_s=0.5)

    with pytest.raises(RateLimitError):
        FakeModel(responder=flaky).complete([Message("user", "hi")])


WEATHER = Tool(
    name="get_weather",
    description="Current weather for a city",
    input_schema={"type": "object", "properties": {"city": {"type": "string"}}},
)


def test_fake_model_can_request_tools_and_validates_results():
    def responder(request):
        if request.messages[-1].role == "tool":
            return f"It is {request.messages[-1].content}."
        return [ToolCall(id="call-1", name="get_weather", arguments={"city": "Leeds"})]

    model = FakeModel(responder=responder)
    first = model.complete([Message("user", "Weather in Leeds?")], tools=[WEATHER])
    assert first.stop_reason == "tool_use"
    assert first.tool_calls[0].arguments == {"city": "Leeds"}
    assert model.requests[0].tools == (WEATHER,)

    history = [
        Message("user", "Weather in Leeds?"),
        Message("assistant", tool_calls=first.tool_calls),
        Message("tool", "drizzle", tool_call_id="call-1"),
    ]
    assert model.complete(history, tools=[WEATHER]).text == "It is drizzle."


def test_unanswered_or_unknown_tool_results_are_rejected():
    call = ToolCall(id="call-1", name="get_weather", arguments={})
    model = FakeModel()
    with pytest.raises(InvalidRequestError, match="before tool call"):
        model.complete(
            [Message("user", "hi"), Message("assistant", tool_calls=(call,)), Message("user", "?")]
        )
    with pytest.raises(InvalidRequestError, match="not awaiting a result"):
        model.complete([Message("user", "hi"), Message("tool", "x", tool_call_id="nope")])


def test_responders_cannot_call_tools_that_were_not_offered():
    model = FakeModel(responder=lambda _: [ToolCall(id="c", name="rm_rf", arguments={})])
    with pytest.raises(ValueError, match="not offered"):
        model.complete([Message("user", "hi")], tools=[WEATHER])


def test_tool_messages_must_carry_a_call_id():
    with pytest.raises(ValueError):
        Message("tool", "result")
    with pytest.raises(ValueError):
        Message("user", "hi", tool_calls=(ToolCall("c", "x", {}),))


class Liar(str):
    """A str whose comparisons always say yes, as a cheating submission might send."""

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    def __contains__(self, item):
        return True

    def startswith(self, *args):
        return True

    __hash__ = str.__hash__


class LyingDict(dict):
    def __eq__(self, other):
        return True

    __hash__ = None


def test_requests_record_lying_strings_as_plain_strs_with_their_true_value():
    seen = []
    model = FakeModel(responder=lambda request: seen.append(request) or "OK")
    model.complete(
        [
            Message("user", Liar("hello")),
            Message("assistant", tool_calls=(ToolCall(Liar("c1"), Liar("get_weather"), {}),)),
            Message("tool", Liar("drizzle"), tool_call_id=Liar("c1")),
        ],
        system=Liar("be brief"),
        tools=[Tool(Liar("get_weather"), Liar("Current weather"), {"type": Liar("object")})],
    )
    request = model.requests[0]
    assert seen == [request]
    first, call_message, result = request.messages
    call = call_message.tool_calls[0]
    tool = request.tools[0]
    values = [
        (request.system, "be brief"),
        (first.role, "user"),
        (first.content, "hello"),
        (call.id, "c1"),
        (call.name, "get_weather"),
        (result.content, "drizzle"),
        (result.tool_call_id, "c1"),
        (tool.name, "get_weather"),
        (tool.description, "Current weather"),
        (tool.input_schema["type"], "object"),
    ]
    for value, true_value in values:
        assert type(value) is str
        assert str.__eq__(value, true_value)
    assert request.system != "anything else"
    assert "missing" not in first.content
    assert not tool.description.startswith("nope")


def test_tool_call_arguments_become_plain_nested_dicts_and_lists():
    arguments = LyingDict(
        ids=("a", Liar("b")), nested={"n": 3, "x": 1.5, "ok": True, "none": None}, items=[[1]]
    )
    history = [
        Message("user", "hi"),
        Message("assistant", tool_calls=(ToolCall("c1", "get_weather", arguments),)),
        Message("tool", "done", tool_call_id="c1"),
    ]
    model = FakeModel()
    model.complete(history)
    sent = model.requests[0].messages[1].tool_calls[0].arguments
    assert type(sent) is dict
    assert sent == {
        "ids": ["a", "b"],
        "nested": {"n": 3, "x": 1.5, "ok": True, "none": None},
        "items": [[1]],
    }
    assert type(sent["ids"]) is list and type(sent["ids"][1]) is str
    assert type(sent["nested"]) is dict and type(sent["items"][0]) is list
    assert sent != {"anything": "else"}
    assert sent is not arguments


def test_values_json_cannot_carry_are_rejected_before_anything_is_sent():
    class Thing:
        pass

    history = [
        Message("user", "hi"),
        Message("assistant", tool_calls=(ToolCall("c1", "f", {"when": {"at": Thing()}}),)),
        Message("tool", "done", tool_call_id="c1"),
    ]
    model = FakeModel()
    with pytest.raises(TypeError, match=r"messages\[1\]\.tool_calls\[0\]\.arguments.*Thing.*JSON"):
        model.complete(history)
    with pytest.raises(TypeError, match="content must be a str, not int"):
        model.complete([Message("user", 42)])
    with pytest.raises(TypeError, match="JSON object keys must be strings"):
        model.complete([Message("user", "hi")], tools=[Tool("f", "d", {("a",): 1})])
    assert model.requests == []


def test_completions_are_plain_values():
    model = FakeModel(responder=lambda _: Liar("one two three"))
    completion = model.complete([Message("user", "hi")])
    assert type(completion.text) is str and completion.text != "nope"

    calls = [ToolCall(Liar("c1"), "get_weather", LyingDict(city=Liar("Leeds")))]
    completion = FakeModel(responder=lambda _: calls).complete(
        [Message("user", "hi")], tools=[WEATHER]
    )
    call = completion.tool_calls[0]
    assert type(call.id) is str and type(call.arguments) is dict
    assert call.arguments == {"city": "Leeds"} and call.arguments != {"city": "York"}
