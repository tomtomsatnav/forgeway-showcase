import json

from forgeway_kit import Message, ModelClient

PROMPT = (
    "Extract the person from the text below. Reply with only a JSON object with the keys "
    '"name" (a string) and "age" (an integer).\n\nText: {text}'
)


def _parse(reply: str) -> dict:
    """Parse and validate a reply; raise ValueError describing the first problem."""
    data = json.loads(reply)  # JSONDecodeError is a ValueError
    if not isinstance(data, dict):
        raise ValueError("the reply must be a JSON object")
    name, age = data.get("name"), data.get("age")
    if not isinstance(name, str) or not name:
        raise ValueError('"name" must be a non-empty string')
    if not isinstance(age, int) or isinstance(age, bool):
        raise ValueError('"age" must be an integer')
    return {"name": name, "age": age}


def extract_person(client: ModelClient, text: str) -> dict:
    """Extract `{"name": str, "age": int}` from `text` using the model.

    Re-asks once, quoting the error, if the reply is invalid. Raises ValueError if the
    second attempt is also invalid.
    """
    messages = [Message(role="user", content=PROMPT.format(text=text))]
    reply = client.complete(messages).text
    try:
        return _parse(reply)
    except ValueError as error:
        messages += [
            Message(role="assistant", content=reply),
            Message(
                role="user",
                content=f"That reply was invalid: {error}. Reply again with only the JSON object.",
            ),
        ]
    return _parse(client.complete(messages).text)
