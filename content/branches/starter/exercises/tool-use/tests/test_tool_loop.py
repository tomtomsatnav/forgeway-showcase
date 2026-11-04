import pytest
from tool_loop import run_with_tools

from forgeway_kit import FakeModel, Tool, ToolCall

WEATHER = Tool(
    name="get_weather",
    description="Current weather for a city.",
    input_schema={
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
)
CONVERT = Tool(
    name="to_fahrenheit",
    description="Convert Celsius to Fahrenheit.",
    input_schema={
        "type": "object",
        "properties": {"celsius": {"type": "number"}},
        "required": ["celsius"],
    },
)
FORECAST = {"Leeds": "drizzle, 11C", "Cairo": "sunny, 35C", "Oslo": "snow, -3C"}


def plain_str(value):
    assert type(value) is str, f"run_with_tools() should return a plain str, got {type(value)}."
    return value


def last(request):
    return request.messages[-1]


def test_answers_after_one_tool_round():
    for city, weather in FORECAST.items():

        def responder(request, city=city):
            if last(request).role == "tool":
                return f"The weather is {last(request).content}."
            return [ToolCall("call-1", "get_weather", {"city": city})]

        model = FakeModel(responder=responder)
        calls = []

        def get_weather(city, calls=calls):
            calls.append(city)
            return FORECAST[city]

        text = plain_str(
            run_with_tools(model, f"Weather in {city}?", [WEATHER], {"get_weather": get_weather})
        )
        assert text == f"The weather is {weather}.", (
            f"After the tool returned {weather!r} the model's final text should be returned; "
            f"got {text!r}. Did you send the tool result back to the model to get its answer?"
        )
        assert calls == [city], f"get_weather should be called once with {city!r}; got {calls}."
        assert len(model.requests) == 2, (
            f"Expected two model calls (the request, then one with the tool result), got "
            f"{len(model.requests)}. After running a tool, send its result back to the model."
        )
        assert model.requests[0].tools == (WEATHER,), "Offer the tools on every model call."
        assert model.requests[1].tools == (WEATHER,), "Keep offering the tools on later calls."
        roles = [m.role for m in model.requests[1].messages]
        assert roles == ["user", "assistant", "tool"], (
            "The second request should hold the question, the assistant's tool request and the "
            f"tool result, in that order. Roles sent: {roles}."
        )
        assistant, tool = model.requests[1].messages[1:]
        assert assistant.tool_calls and assistant.tool_calls[0].id == "call-1", (
            "The assistant message must carry the model's tool_calls."
        )
        assert tool.tool_call_id == "call-1" and tool.content == weather, (
            f"The tool message should answer call 'call-1' with {weather!r}; "
            f"got id={tool.tool_call_id!r}, content={tool.content!r}."
        )


def test_several_calls_in_order_and_chained_rounds():
    def responder(request):
        message = last(request)
        if message.role == "user":
            return [
                ToolCall("a", "get_weather", {"city": "Leeds"}),
                ToolCall("b", "get_weather", {"city": "Cairo"}),
            ]
        results = [m.content for m in request.messages if m.role == "tool"]
        if len(results) == 2:  # second round: convert the hot city
            return [ToolCall("c", "to_fahrenheit", {"celsius": 35})]
        return "Cairo is " + results[-1]

    order = []

    def get_weather(city):
        order.append(city)
        return FORECAST[city]

    def to_fahrenheit(celsius):
        order.append("convert")
        return celsius * 9 / 5 + 32

    model = FakeModel(responder=responder)
    text = plain_str(
        run_with_tools(
            model,
            "Compare Leeds and Cairo",
            [WEATHER, CONVERT],
            {"get_weather": get_weather, "to_fahrenheit": to_fahrenheit},
        )
    )
    assert order == ["Leeds", "Cairo", "convert"], (
        f"Calls should run in the order the model made them, across rounds; ran {order}."
    )
    assert text == "Cairo is 95.0", (
        f"The final text should come from the third reply; got {text!r}."
    )
    assert len(model.requests) == 3, f"Expected three model calls, got {len(model.requests)}."
    second = model.requests[1].messages
    assert [m.role for m in second] == ["user", "assistant", "tool", "tool"], (
        "Both calls from one turn need their own tool message, directly after the assistant "
        f"message. Roles sent: {[m.role for m in second]}."
    )
    assert [(m.tool_call_id, m.content) for m in second[2:]] == [
        ("a", "drizzle, 11C"),
        ("b", "sunny, 35C"),
    ], "Tool results must be in call order and carry the matching tool_call_id."
    third = model.requests[2].messages
    assert [m.role for m in third] == ["user", "assistant", "tool", "tool", "assistant", "tool"], (
        f"The history must keep growing across rounds. Roles sent: {[m.role for m in third]}."
    )
    assert third[-1].content == "95.0", "Non-string results should be sent back as strings."


def test_tool_errors_become_results():
    def responder(request):
        message = last(request)
        if message.role == "user":
            return [
                ToolCall("x", "get_weather", {"city": "Atlantis"}),
                ToolCall("y", "ghost", {}),
                ToolCall("z", "get_weather", {"city": "Oslo"}),
            ]
        results = [m.content for m in request.messages if m.role == "tool"]
        return " | ".join(results)

    def get_weather(city):
        if city not in FORECAST:
            raise ValueError(f"no weather station for {city}")
        return FORECAST[city]

    ghost = Tool(name="ghost", description="Not implemented.", input_schema={"type": "object"})
    model = FakeModel(responder=responder)
    text = plain_str(
        run_with_tools(
            model, "Weather?", [WEATHER, ghost], {"get_weather": get_weather}, max_steps=3
        )
    )
    first, second, third = text.split(" | ")
    assert "error" in first.lower() and "no weather station for Atlantis" in first, (
        "A tool that raises should not crash the loop: send the model a result such as "
        f"'error: no weather station for Atlantis'. The model saw {first!r}."
    )
    assert "error" in second.lower() and "ghost" in second, (
        "A tool missing from the registry should also produce an error result naming it. "
        f"The model saw {second!r}."
    )
    assert third == "snow, -3C", (
        f"Later calls in the same turn must still run after an earlier one failed; got {third!r}."
    )


def test_step_cap():
    for cap in (1, 3):
        seen = []

        def responder(request, seen=seen):
            seen.append(request)
            if len(seen) > 20:
                raise AssertionError(
                    "The loop kept calling the model long after max_steps; it must stop."
                )
            return [ToolCall(f"c{len(seen)}", "get_weather", {"city": "Leeds"})]

        model = FakeModel(responder=responder)
        with pytest.raises(RuntimeError) as info:
            run_with_tools(
                model, "Weather?", [WEATHER], {"get_weather": lambda city: "rain"}, max_steps=cap
            )
        assert "max_steps" in str(info.value), (
            "The error should be clear about what happened and mention max_steps; "
            f"got {str(info.value)!r}."
        )
        assert len(model.requests) == cap, (
            f"max_steps={cap} means exactly {cap} model call(s) when the model never stops "
            f"asking for tools; the model was called {len(model.requests)} times."
        )

    model = FakeModel(responder=lambda request: [ToolCall("c", "get_weather", {"city": "Leeds"})])
    with pytest.raises(RuntimeError):
        run_with_tools(model, "Weather?", [WEATHER], {"get_weather": lambda city: "rain"})
    assert len(model.requests) == 5, (
        f"max_steps should default to 5, but the model was called {len(model.requests)} times."
    )
