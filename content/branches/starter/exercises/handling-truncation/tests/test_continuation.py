from continuation import complete_fully

from forgeway_kit import FakeModel


def long_answer(n):
    return " ".join(f"word{i}" for i in range(n))


def resumes(full):
    """A model that continues exactly where the assistant messages left off."""

    def responder(request):
        done = "".join(m.content for m in request.messages if m.role == "assistant")
        if not full.startswith(done):
            return "GARBLED: the assistant text sent back was not the reply so far"
        return full[len(done) :]

    return responder


def plain_str(value):
    assert type(value) is str, f"complete_fully() should return a plain str, got {type(value)}."
    return value


def test_complete_reply_needs_one_call():
    model = FakeModel(responder=lambda request: "Paris is the capital of France.")
    reply = plain_str(complete_fully(model, "Capital of France?", max_tokens=50))
    assert reply == "Paris is the capital of France.", (
        f"Expected the reply unchanged, got {reply!r}."
    )
    assert len(model.requests) == 1, (
        f"A reply that finished with end_turn needs one call, but {len(model.requests)} were made."
    )
    assert model.requests[0].max_tokens == 50, (
        f"max_tokens=50 should be passed to the model, but it received "
        f"{model.requests[0].max_tokens}."
    )
    model = FakeModel(responder=lambda request: "short")
    complete_fully(model, "Default cap?")
    assert model.requests[0].max_tokens == 50, (
        f"max_tokens should default to 50, but the model received {model.requests[0].max_tokens}."
    )


def test_truncated_reply_is_completed():
    for size, limit in [(40, 10), (23, 7), (30, 30)]:
        full = long_answer(size)
        model = FakeModel(responder=resumes(full))
        reply = plain_str(complete_fully(model, "Count for me.", max_tokens=limit))
        assert reply == full, (
            f"With a {size}-word answer and max_tokens={limit}, complete_fully() should return "
            f"the whole answer {full[:40]!r}..., but returned {reply[:60]!r}... "
            f"({len(model.requests)} call(s) made). Did you continue after stop_reason "
            "'max_tokens', pass the partial reply back as an assistant message, and join the "
            "pieces without altering them?"
        )
        last = model.requests[-1].messages[-1]
        assert last.role == "user", "Every request must end with a user message."


def test_continuations_are_capped():
    def endless(request):
        if len(model.requests) > 20:
            return "finally done"
        return long_answer(100)

    model = FakeModel(responder=endless)
    complete_fully(model, "Never stop.", max_tokens=5, max_continuations=3)
    assert len(model.requests) == 4, (
        "With max_continuations=3 there should be 1 original call plus at most 3 "
        f"continuations (4 calls), but {len(model.requests)} calls were made. "
        "Count continuations and stop at the cap."
    )
    model = FakeModel(responder=endless)
    complete_fully(model, "Never stop.", max_tokens=5)
    assert len(model.requests) == 6, (
        "max_continuations should default to 5: 1 original call plus 5 continuations (6 calls), "
        f"but {len(model.requests)} calls were made."
    )
    model = FakeModel(responder=endless)
    complete_fully(model, "Never stop.", max_tokens=5, max_continuations=0)
    assert len(model.requests) == 1, (
        "With max_continuations=0 the reply must not be continued at all, but "
        f"{len(model.requests)} calls were made."
    )
