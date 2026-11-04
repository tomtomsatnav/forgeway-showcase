import json
import random

from records import Conversation, Usage, add_output, find


def plain(value):
    """A learner's value as plain built-ins, so it cannot lie about equality."""
    return json.loads(json.dumps(value))


def numbers(seed):
    rng = random.Random(seed)  # noqa: S311
    return rng.randrange(1, 500), rng.randrange(1, 500)


def test_usage_is_frozen():
    fields = list(getattr(Usage, "__dataclass_fields__", {}))
    assert fields == ["input_tokens", "output_tokens"], (
        "Usage should be a dataclass with the fields input_tokens and output_tokens, in that "
        f"order; its dataclass fields are {fields}."
    )
    a, b = numbers(1)
    usage = Usage(a, b)
    assert plain(usage.input_tokens) == a, "Usage(a, b) should store a as input_tokens."
    assert plain(usage.output_tokens) == b, "Usage(a, b) should store b as output_tokens."
    assert plain(Usage(a).output_tokens) == 0, "output_tokens should default to 0."
    try:
        usage.input_tokens = a + 1
    except Exception as err:
        assert type(err).__name__ == "FrozenInstanceError", (
            f"Setting a field should raise FrozenInstanceError, but raised {type(err).__name__}."
        )
    else:
        raise AssertionError("Usage should be frozen: setting a field should raise an error.")
    assert plain(usage.input_tokens) == a, "A frozen record's fields must not change."


def test_total_is_a_property():
    for seed in (2, 3):
        a, b = numbers(seed)
        total = Usage(a, b).total
        assert not callable(total), "total should be a @property, read without brackets."
        assert plain(total) == a + b, f"Usage({a}, {b}).total should be {a + b}, got {total}."
    assert plain(Usage(7).total) == 7, "With no output tokens, total is the input tokens."


def test_add_output_returns_a_new_record():
    for seed in (4, 5):
        a, b = numbers(seed)
        extra = a % 40 + 1
        usage = Usage(a, b)
        added = add_output(usage, extra)
        assert plain(added.output_tokens) == b + extra, (
            f"add_output should add {extra} to {b} output tokens, got {added.output_tokens}."
        )
        assert plain(added.input_tokens) == a, "add_output should keep input_tokens."
        assert plain(usage.output_tokens) == b, "The original Usage must be left as it was."


def test_conversations_do_not_share_a_list():
    first = Conversation("first")
    second = Conversation("second")
    first.add("hello")
    first.add("again")
    assert plain(first.messages) == ["hello", "again"], (
        f"add() should append to messages, in order; got {first.messages}."
    )
    assert plain(second.messages) == [], (
        "Each Conversation needs its own list: adding to one must not change another. Use "
        "field(default_factory=list)."
    )
    given = Conversation("given", ["kept"])
    assert plain(given.messages) == ["kept"], "messages should be settable when constructing."
    fields = list(getattr(Conversation, "__dataclass_fields__", {}))
    assert fields == ["title", "messages"], (
        f"Conversation should be a dataclass with the fields title and messages; it has {fields}."
    )


def test_find_returns_none_when_absent():
    pair = [Conversation("a"), Conversation("b", ["first b"]), Conversation("b", ["second b"])]
    found = find(pair, "b")
    assert found is not None, "find() should return the conversation with that title."
    assert plain(found.messages) == ["first b"], (
        "find() should return the first conversation with that title."
    )
    assert find(pair, "missing") is None, "With no such title, find() should return None."
    assert find([], "a") is None, "With no conversations, find() should return None."
