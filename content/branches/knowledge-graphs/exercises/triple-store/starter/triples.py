from typing import NamedTuple


class Triple(NamedTuple):
    subject: str
    predicate: str
    object: str


class TripleStore:
    def add(self, subject: str, predicate: str, obj: str) -> bool:
        """Store a triple. Return False if it was already there."""
        raise NotImplementedError

    def remove(self, subject: str, predicate: str, obj: str) -> bool:
        """Delete a triple. Return False if it was not there."""
        raise NotImplementedError

    def match(
        self, subject: str | None = None, predicate: str | None = None, obj: str | None = None
    ) -> list[Triple]:
        """Triples equal to every argument that is not None, oldest first."""
        raise NotImplementedError

    def __len__(self) -> int:
        raise NotImplementedError
