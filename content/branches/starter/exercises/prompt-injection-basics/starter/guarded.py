from forgeway_kit import ModelClient


def answer_about(client: ModelClient, document: str, question: str) -> str:
    """Answer `question` about the untrusted `document` and return the reply text.

    Instructions go in the system prompt; the document goes in the user message inside a
    single <document>...</document> pair, with delimiter look-alikes in it neutralised.
    """
    raise NotImplementedError("system prompt for rules, delimited and escaped document")
