import pytest
from budget import fit_to_budget

from forgeway_kit import Message, count_tokens


def words(n, label="w"):
    return " ".join([label] * n)


def user(n):
    return Message(role="user", content=words(n, "q"))


def assistant(n):
    return Message(role="assistant", content=words(n, "a"))


def total(system, messages):
    return count_tokens(system) + sum(count_tokens(m.content) for m in messages)


def plain(messages):
    """Check a returned list and turn it into plain (role, content) tuples."""
    assert type(messages) is list, f"Expected a list of messages, got {type(messages).__name__}."
    for m in messages:
        assert type(m.role) is str and type(m.content) is str, (
            "Each message's role and content should be plain strings."
        )
    return [(m.role, m.content) for m in messages]


def pairs(messages):
    return [(m.role, m.content) for m in messages]


def test_trims_oldest_until_it_fits():
    system = words(4, "s")
    history = [user(10), assistant(10), user(10), assistant(10), user(5)]
    assert total(system, history) == 49, (
        "test setup: the system prompt and history should total 49 tokens."
    )
    result = fit_to_budget(system, history, 29)
    assert plain(result) == pairs(history[2:]), (
        f"With a 29-token budget (system prompt is 4 tokens) the two oldest messages should be "
        f"dropped, leaving {len(history) - 2} messages, but {len(result)} were returned."
    )
    assert total(system, history[2:]) <= 29 and total(system, result) <= 29, (
        f"The result needs {total(system, result)} tokens, over the 29-token budget."
    )

    other = [user(3), assistant(7), user(2), assistant(9), user(4), assistant(6), user(8)]
    result = fit_to_budget("", other, 40)
    assert total("", result) <= 40, (
        f"The result needs {total('', result)} tokens, over the 40-token budget."
    )
    assert plain(result) == pairs(other[-len(result) :]), (
        "Messages should only be removed from the front: the result must be a suffix of the "
        "history, with the order unchanged."
    )
    assert plain(fit_to_budget("", other, 1000)) == pairs(other), (
        "When everything already fits, all messages should be returned unchanged."
    )


def test_system_prompt_counts_and_latest_turn_is_kept():
    history = [user(6), assistant(6), user(6)]
    assert plain(fit_to_budget("", history, 18)) == pairs(history), (
        "18 tokens of messages fit an 18 budget."
    )
    result = fit_to_budget(words(8, "s"), history, 18)
    assert total(words(8, "s"), result) <= 18, (
        "The system prompt's 8 tokens count towards the budget: with it, the history of "
        f"18 tokens does not fit in 18, but the result still needs "
        f"{total(words(8, 's'), result)} tokens."
    )
    assert plain(result)[-1] == pairs(history)[-1], "The latest user message must always be kept."

    with pytest.raises(ValueError):
        fit_to_budget(words(10, "s"), [user(5), assistant(5), user(12)], 20)
    with pytest.raises(ValueError):
        fit_to_budget(words(10, "s"), [user(5), assistant(5), user(11)], 20)
    exact = fit_to_budget(words(10, "s"), [user(5), assistant(5), user(10)], 20)
    assert plain(exact) == pairs([user(10)]), (
        "The system prompt (10) and the latest message (10) fill the 20-token budget exactly: "
        "that fits, so only the latest message is returned."
    )


def test_history_starts_with_a_user_message():
    history = [user(10), assistant(10), user(10), assistant(10), user(5)]
    result = fit_to_budget("", history, 35)
    assert plain(result)[0][0] == "user", (
        "The trimmed history starts with an assistant reply. Dropping the oldest message "
        "leaves a reply with no question, so drop it as well. "
        f"The roles were {[m.role for m in result]}."
    )
    assert plain(result) == pairs(history[2:]), (
        f"Expected the last 3 messages (25 tokens), but got {len(result)} messages."
    )
