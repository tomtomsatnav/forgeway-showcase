import json

from forgeway_kit import Message, ModelClient


def extract_person(client: ModelClient, text: str) -> dict:
    messages = [
        Message(role="user", content=f"Reply with only JSON with name and age.\n\nText: {text}")
    ]
    reply = client.complete(messages).text
    try:
        return json.loads(reply)
    except json.JSONDecodeError as error:
        messages += [
            Message(role="assistant", content=reply),
            Message(role="user", content=f"Invalid JSON: {error}. Try again."),
        ]
    return json.loads(client.complete(messages).text)
