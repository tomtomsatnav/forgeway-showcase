import json
import random

from transcript import contents_by_role, long_messages, top_words, unique_roles


def plain(value):
    """A learner's value as plain built-ins, so it cannot lie about equality."""
    return json.loads(json.dumps(value))


def transcript(seed):
    rng = random.Random(seed)  # noqa: S311
    roles = [f"role{rng.randrange(1000)}" for _ in range(3)]
    return [
        {
            "role": rng.choice(roles),
            "content": " ".join(f"w{rng.randrange(50)}" for _ in range(rng.randrange(1, 7))),
        }
        for _ in range(12)
    ]


def test_contents_by_role():
    for seed in (1, 2, 3):
        messages = transcript(seed)
        got = plain(contents_by_role(messages))
        roles = {m["role"] for m in messages}
        expected = {r: [m["content"] for m in messages if m["role"] == r] for r in roles}
        assert got == expected, (
            "contents_by_role() should give each role its own list of contents, in the order "
            f"they appear. For {messages[:3]}... it returned {got}."
        )


def test_unique_roles():
    for seed in (4, 5, 6):
        messages = transcript(seed)
        got = plain(unique_roles(messages))
        expected = sorted({m["role"] for m in messages})
        assert got == expected, f"unique_roles() should return {expected}, each once; got {got}."
    assert plain(unique_roles([])) == [], "With no messages, unique_roles() should return []."


def test_long_messages():
    for seed, min_words in ((7, 3), (8, 1), (9, 6)):
        messages = transcript(seed)
        got = plain(long_messages(messages, min_words))
        expected = [m["content"] for m in messages if len(m["content"].split()) >= min_words]
        assert got == expected, (
            f"long_messages(messages, {min_words}) should keep messages with at least {min_words} "
            f"words, in order. Expected {expected}, got {got}."
        )
    exact = [{"role": "user", "content": "one two"}]
    assert plain(long_messages(exact, 2)) == ["one two"], (
        "A message with exactly min_words words should be kept."
    )


def test_top_words():
    got = plain(top_words("pear fig pear kiwi fig plum", 3))
    assert got == [["fig", 2], ["pear", 2], ["kiwi", 1]], (
        "Words with the same count should be in alphabetical order. For 'pear fig pear kiwi fig "
        f"plum' and n=3, expected fig 2, pear 2, kiwi 1; got {got}."
    )
    for seed in (10, 11):
        rng = random.Random(seed)  # noqa: S311
        text = " ".join(f"w{rng.randrange(30)}" for _ in range(200))
        got = plain(top_words(text, 5))
        words = text.split()
        ranked = sorted({(-words.count(w), w) for w in words})
        expected = [[word, -count] for count, word in ranked[:5]]
        assert got == expected, f"top_words() should return {expected}; got {got}."
    assert plain(top_words("Tea tea", 2)) == [["Tea", 1], ["tea", 1]], (
        "Case matters: 'Tea' and 'tea' are different words."
    )
