import json

from forgeway_kit import Message, ModelClient


def extract_person(client: ModelClient, text: str) -> dict:
    messages = [
        Message(role="user", content=f"Reply with only JSON with name and age.\n\nText: {text}")
    ]
    for _ in range(2):
        try:
            data = json.loads(client.complete(messages).text)
        except json.JSONDecodeError:
            continue
        if isinstance(data.get("name"), str) and isinstance(data.get("age"), int):
            return data
    raise ValueError("model did not return valid JSON")
