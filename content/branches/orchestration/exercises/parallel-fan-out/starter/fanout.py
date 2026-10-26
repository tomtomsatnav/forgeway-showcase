from dataclasses import dataclass

from forgeway_kit import ModelClient


@dataclass(frozen=True)
class FanOutResult:
    summaries: dict[str, str]  # id -> summary, in the order of `documents`
    failed: dict[str, str]  # id -> error message
    overview: str


def summarise_all(
    client: ModelClient, documents: dict[str, str], max_workers: int = 4
) -> FanOutResult:
    """Summarise every document concurrently, then aggregate the summaries in one more call.

    One request per document, at most `max_workers` at once. A ModelError on one document goes
    in `failed` and does not stop the others. The aggregation message has one `[id] summary`
    line per success, in the order of `documents`.
    """
    raise NotImplementedError("fan out with a thread pool, collect by document, then aggregate")
