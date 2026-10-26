from dataclasses import dataclass

from forgeway_kit import ModelClient


@dataclass(frozen=True)
class Route:
    description: str  # shown to the classifier
    system: str  # the system prompt of the specialist that handles this route


@dataclass(frozen=True)
class Routed:
    route: str
    text: str


def classify(client: ModelClient, message: str, routes: dict[str, Route], default: str) -> str:
    """Ask the model which route fits `message`; return a name from `routes`, else `default`.

    One call: the system prompt lists every `name: description`, the user message is `message`,
    `max_tokens` is at most 32. Take the first route name in the reply, as a whole word, ignoring
    case.
    """
    raise NotImplementedError("one classifier call, then match the reply to a route")


def answer(client: ModelClient, message: str, routes: dict[str, Route], default: str) -> Routed:
    """Classify `message`, then let the chosen route's specialist answer it."""
    raise NotImplementedError("classify, then call the specialist with its own system prompt")
