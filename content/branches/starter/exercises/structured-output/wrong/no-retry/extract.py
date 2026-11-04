import json

from forgeway_kit import Message, ModelClient


def extract_person(client: ModelClient, text: str) -> dict:
    messages = [
        Message(role="user", content=f"Reply with only JSON with name and age.\n\nText: {text}")
    ]
    data = json.loads(client.complete(messages).text)
    if not isinstance(data.get("name"), str) or not isinstance(data.get("age"), int):
        raise ValueError("invalid fields")
    return data
