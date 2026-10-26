from forgeway_kit import Message, ModelClient


def rewrite_query(client: ModelClient, history: list[Message], question: str) -> str:
    """Turn a conversational follow-up into a standalone search query.

    Include the history in the prompt. Return the first line of the reply without surrounding
    whitespace or quotes. With no history, return `question` without calling the model.
    """
    raise NotImplementedError


def search_conversation(
    client: ModelClient, store, history: list[Message], question: str, k: int = 3
):
    """Rewrite `question` using `history`, then return `store.search(rewritten, k)`."""
    raise NotImplementedError
