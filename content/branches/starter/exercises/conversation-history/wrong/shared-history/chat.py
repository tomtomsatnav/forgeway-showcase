from typing import ClassVar

from forgeway_kit import Message, ModelClient


class Chat:
    _messages: ClassVar[list[Message]] = []

    def __init__(self, client: ModelClient, system: str | None = None) -> None:
        self._client = client
        self._system = system

    @property
    def history(self) -> list[Message]:
        return list(self._messages)

    def send(self, text: str) -> str:
        self._messages.append(Message(role="user", content=text))
        completion = self._client.complete(self._messages, system=self._system)
        self._messages.append(Message(role="assistant", content=completion.text))
        return completion.text
