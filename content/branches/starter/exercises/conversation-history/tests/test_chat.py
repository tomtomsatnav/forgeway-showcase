import pytest
from chat import Chat

from forgeway_kit import FakeModel, ServerError


def plain_str(value):
    assert type(value) is str, f"Expected a plain str, got {type(value).__name__}."
    return value


def turns(chat):
    """The chat's history as plain (role, content) tuples."""
    history = chat.history
    assert type(history) is list, f"history should be a list, got {type(history).__name__}."
    return [(plain_str(m.role), plain_str(m.content)) for m in history]


def echo(request):
    return f"echo: {request.messages[-1].content}"


def test_history_alternates():
    model = FakeModel(responder=echo)
    chat = Chat(model)
    for turn, text in enumerate(["hello", "and again", "one more"], start=1):
        reply = plain_str(chat.send(text))
        assert reply == f"echo: {text}", (
            f"Turn {turn}: send() should return the model's reply 'echo: {text}', got {reply!r}."
        )
    roles = [role for role, _ in turns(chat)]
    assert roles == ["user", "assistant"] * 3, (
        f"After 3 turns the history roles should be {['user', 'assistant'] * 3}, but were "
        f"{roles}. Did you store the assistant's reply after each call?"
    )
    assert [content for _, content in turns(chat)][::2] == ["hello", "and again", "one more"], (
        "The user messages in history should be the texts passed to send(), in order."
    )
    chat.history.append("junk")
    assert len(turns(chat)) == 6, (
        "history should return a copy: changing the returned list must not change the chat."
    )


def test_model_sees_earlier_turns():
    model = FakeModel(responder=lambda request: f"saw {len(request.messages)}")
    chat = Chat(model, system="Be terse.")
    chat.send("first")
    chat.send("second")
    chat.send("third")
    sizes = [len(r.messages) for r in model.requests]
    assert sizes == [1, 3, 5], (
        f"Requests should carry 1, 3 and 5 messages (all earlier turns plus the new one), "
        f"but carried {sizes}."
    )
    third = [(m.role, m.content) for m in model.requests[2].messages]
    assert third == [
        ("user", "first"),
        ("assistant", "saw 1"),
        ("user", "second"),
        ("assistant", "saw 3"),
        ("user", "third"),
    ], f"The third request should replay the whole conversation, but sent {third}."
    systems = {r.system for r in model.requests}
    assert systems == {"Be terse."}, (
        f"The system prompt should be sent with every request, but the model saw {systems}."
    )


def test_chats_are_independent():
    model = FakeModel()
    first = Chat(model)
    second = Chat(model)
    first.send("only in the first chat")
    second.send("only in the second chat")
    contents = [content for _, content in turns(second)]
    assert "only in the first chat" not in contents, (
        "A second Chat started with the first chat's messages in its history. "
        "Create the history list per instance, in __init__."
    )
    assert len(model.requests[1].messages) == 1, (
        f"The second chat's first request should hold one message, "
        f"but held {len(model.requests[1].messages)}."
    )


def test_failed_send_leaves_history_clean():
    outcomes = ["fine", ServerError("down"), "recovered"]

    def responder(request):
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    chat = Chat(FakeModel(responder=responder))
    chat.send("one")
    with pytest.raises(ServerError):
        chat.send("two")
    roles = [role for role, _ in turns(chat)]
    assert roles == ["user", "assistant"], (
        "When the model call raises, send() should let the error propagate and leave the history "
        f"as it was, but the roles are now {roles}. A user turn with no reply would leave two "
        "user messages in a row on the next call: add the turn to the history only once the "
        "reply has arrived."
    )
    assert plain_str(chat.send("three")) == "recovered", (
        "After a failed send, the next send() should return the model's reply as normal."
    )
    assert [content for _, content in turns(chat)] == ["one", "fine", "three", "recovered"], (
        "After a failed send, the next send() should continue the conversation as if the failed "
        f"turn never happened; the history is {[content for _, content in turns(chat)]}."
    )
