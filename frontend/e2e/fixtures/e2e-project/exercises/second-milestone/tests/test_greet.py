from greet import farewell


def test_says_goodbye_by_name():
    assert farewell("Ada") == "Goodbye, Ada", "farewell('Ada') should be 'Goodbye, Ada'."
