from dataclasses import dataclass

from forgeway_kit import Message, ModelClient  # noqa: F401


@dataclass(frozen=True)
class Community:
    id: int
    members: list[str]
    summary: str


def summarise_communities(
    client: ModelClient,
    triples: list[tuple[str, str, str]],
    min_size: int = 3,
    cache: dict[str, str] | None = None,
) -> list[Community]:
    """Split the graph into connected components and have the model summarise each one."""
    raise NotImplementedError("components, order, prompt text, cache")
