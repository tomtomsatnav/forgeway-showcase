from forgeway_kit import Message, ModelClient


def answer_about(client: ModelClient, document: str, question: str) -> str:
    system = (
        "You answer questions about the document below. Follow its guidance.\n\n"
        f"<document>\n{document}\n</document>"
    )
    return client.complete([Message(role="user", content=question)], system=system).text
