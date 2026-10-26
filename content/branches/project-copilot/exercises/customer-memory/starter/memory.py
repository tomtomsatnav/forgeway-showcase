from collections.abc import Callable
from dataclasses import dataclass

from forgeway_kit import ModelClient

EXTRACT_SYSTEM = (
    "List the lasting preferences this customer states about how they want to be helped, as a "
    'JSON array of {"key": ..., "value": ...} objects. Reply [] if there are none.'
)


@dataclass(frozen=True)
class Ticket:
    id: int
    subject: str
    resolution: str
    at: float


class CustomerMemory:
    """Every customer's memory is one JSON text in `data[user_id]`, read on every call."""

    def __init__(self, data: dict, clock: Callable[[], float]) -> None:
        raise NotImplementedError

    def set_preference(self, user_id: str, key: str, value: str) -> str:
        """Store a preference; return "added", "updated" or "unchanged"."""
        raise NotImplementedError

    def preferences(self, user_id: str) -> dict[str, str]:
        """The customer's preferences, sorted by key."""
        raise NotImplementedError

    def add_ticket(self, user_id: str, subject: str, resolution: str) -> int:
        """Record a resolved ticket; return its id (1, 2, 3, ... for that customer)."""
        raise NotImplementedError

    def tickets(self, user_id: str) -> list[Ticket]:
        """The customer's tickets in id order."""
        raise NotImplementedError

    def recall(self, user_id: str, query: str, k: int = 3) -> list[Ticket]:
        """The customer's past tickets most worth showing for `query`. See the brief."""
        raise NotImplementedError

    def forget(self, user_id: str, topic: str) -> int:
        """Remove every ticket and preference that mentions `topic`; return how many."""
        raise NotImplementedError

    def delete_user(self, user_id: str) -> bool:
        """Remove everything about a customer; True if there was anything."""
        raise NotImplementedError


def learn_preferences(
    extractor: ModelClient, memory: CustomerMemory, user_id: str, message: str
) -> int:
    """Ask the extractor which preferences `message` states and store them; return how many."""
    raise NotImplementedError
