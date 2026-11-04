from forgeway_kit import ModelClient


def extract_person(client: ModelClient, text: str) -> dict:
    """Extract `{"name": str, "age": int}` from `text` using the model.

    Re-asks once, quoting the error, if the reply is invalid. Raises ValueError if the
    second attempt is also invalid.
    """
    raise NotImplementedError("prompt for JSON, parse, validate, re-ask once")
