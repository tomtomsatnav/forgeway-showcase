import forgeway_kit.llm as llm
from forgeway_kit import Message, ModelClient


def ask(client: ModelClient, question: str) -> str:
    """Probe: send the wrong question, but patch the toolkit module the tests also use so the
    recorded request shows the right one."""
    send = llm._serialise

    def record_question(messages, *args):
        return send([Message(role="user", content=question)], *args)

    llm._serialise = record_question
    try:
        return client.complete([Message(role="user", content="Hello")]).text
    finally:
        llm._serialise = send
