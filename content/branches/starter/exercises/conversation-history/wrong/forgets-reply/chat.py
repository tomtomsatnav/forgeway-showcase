from forgeway_kit import Message, ModelClient


class Chat:
    def __init__(self, client: ModelClient, system: str | None = None) -> None:
        self._client = client
        self._system = system
        self._messages: list[Message] = []

    @property
    def history(self) -> list[Message]:
        return list(self._messages)

    def send(self, text: str) -> str:
        self._messages.append(Message(role="user", content=text))
        completion = self._client.complete(self._messages, system=self._system)
        return completion.text
