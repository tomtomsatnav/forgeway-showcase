def normalise(name: str) -> str:
    """The six normalisation steps, exactly as in the entity resolution exercise."""
    raise NotImplementedError


class EntityResolver:
    def __init__(self, aliases: dict[str, str] | None = None) -> None:
        raise NotImplementedError

    def resolve(self, mention: str) -> str:
        raise NotImplementedError
