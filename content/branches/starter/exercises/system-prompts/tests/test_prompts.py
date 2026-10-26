from prompts import answer

from forgeway_kit import FakeModel


def echo(request):
    return f"[{request.system}] {request.messages[-1].content}"


CASES = [
    ("You are a pirate.", "What is the weather?"),
    ("Reply in French only.", "How do I boil an egg?"),
    ("Answer in one word.", "Name a colour."),
]


def test_system_prompt_is_sent_as_system():
    for system, question in CASES:
        check_system(system, question)


def check_system(system, question):
    model = FakeModel(responder=echo)
    reply = answer(model, system, question)
    assert type(reply) is str, f"answer() should return a plain str, got {type(reply).__name__}."
    request = model.requests[0]
    assert request.system == system, (
        f"The system prompt should be passed as system={system!r}, "
        f"but the model received system={request.system!r}."
    )
    assert all(system not in m.content for m in request.messages), (
        "The system prompt should not also be repeated inside a message."
    )
    assert reply == f"[{system}] {question}", (
        f"answer() should return the model's reply unchanged, but returned {reply!r}."
    )


EXAMPLE_SETS = [
    [("great film!", "positive")],
    [("great film!", "positive"), ("a dull, slow mess", "negative")],
    [("a", "1"), ("b", "2"), ("c", "3")],
]


def test_examples_alternate_roles():
    for examples in EXAMPLE_SETS:
        check_examples(examples)


def check_examples(examples):
    model = FakeModel()
    answer(model, "Classify.", "final input", examples)
    messages = model.requests[0].messages
    expected = []
    for example_input, example_output in examples:
        expected += [("user", example_input), ("assistant", example_output)]
    expected.append(("user", "final input"))
    actual = [(m.role, m.content) for m in messages]
    assert actual == expected, (
        f"With {len(examples)} example(s) the model should receive {expected}, "
        f"but received {actual}. Each example is a user message (the input) followed by an "
        "assistant message (the ideal output), in the order given."
    )


def test_question_comes_last():
    model = FakeModel()
    answer(model, "Be brief.", "Why is the sky blue?", [("Why is grass green?", "Chlorophyll.")])
    last = model.requests[0].messages[-1]
    assert last.role == "user" and last.content == "Why is the sky blue?", (
        "The real question must be the final message, sent with role 'user'. "
        f"The final message was role={last.role!r}, content={last.content!r}."
    )
    model = FakeModel()
    answer(model, "Be brief.", "Just a question")
    messages = model.requests[0].messages
    assert len(messages) == 1, (
        f"With no examples there should be exactly one message, but {len(messages)} were sent."
    )
