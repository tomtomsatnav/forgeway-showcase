from greet import greet


def test_greets_by_name():
    assert greet("Ada") == "Hello, Ada", (
        f"greet('Ada') should be 'Hello, Ada', not {greet('Ada')!r}."
    )
