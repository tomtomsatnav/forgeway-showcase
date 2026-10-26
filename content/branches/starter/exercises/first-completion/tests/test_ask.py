from ask import ask

from forgeway_kit import FakeModel


def test_returns_the_model_reply():
    model = FakeModel(responder=lambda request: "A token is a chunk of text.")
    reply = ask(model, "What is a token?")
    assert type(reply) is str, (
        f"ask() should return a plain str, but returned {type(reply).__name__}."
    )
    assert reply == "A token is a chunk of text.", (
        "ask() should return the completion's text unchanged. "
        f"The model replied 'A token is a chunk of text.' but ask() returned {reply!r}."
    )


def test_sends_the_question_as_a_user_message():
    model = FakeModel()
    ask(model, "Why is the sky blue?")
    assert len(model.requests) == 1, (
        f"ask() should call the model exactly once; it called it {len(model.requests)} times."
    )
    messages = model.requests[0].messages
    assert len(messages) == 1 and messages[0].role == "user", (
        "Send a single message with role 'user'."
    )
    assert messages[0].content == "Why is the sky blue?", (
        "The user message should contain exactly the question you were given, "
        f"but it contained {messages[0].content!r}."
    )
