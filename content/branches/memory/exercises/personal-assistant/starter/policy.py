from forgeway_kit import ModelClient


def apply_policy(classifier: ModelClient, store, user_id: str, turn: str) -> str:
    """The write policy: ask the classifier about `turn` and write what it decided.

    Returns "fact", "episode", "skipped", "withheld" or "invalid".
    """
    raise NotImplementedError


def reflect(reflector: ModelClient, store, user_id: str, threshold: int = 25) -> int:
    """Consolidate the user's unreflected episodes into facts. Returns the facts written."""
    raise NotImplementedError
