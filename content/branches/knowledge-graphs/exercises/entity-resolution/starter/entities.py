import unicodedata  # noqa: F401  (you will need it)


def normalise(name: str) -> str:
    """The normalised form of `name`, by the six steps in the brief."""
    raise NotImplementedError("decompose, casefold, split, trim the ends, join")


class EntityResolver:
    def __init__(self, aliases: dict[str, str] | None = None) -> None:
        raise NotImplementedError

    def resolve(self, mention: str) -> str:
        """The entity id for `mention`; remember the mention as a surface form."""
        raise NotImplementedError

    def surface_forms(self, entity_id: str) -> list[str]:
        """Distinct mentions that resolved to `entity_id`, first seen first."""
        raise NotImplementedError
