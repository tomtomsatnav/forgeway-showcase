import json
import threading
import time

from fan_out import fetch_all, fetch_each

WAIT_S = 3


def plain(value):
    """A learner's value as plain built-ins, so it cannot lie about equality."""
    return json.loads(json.dumps(value))


def make_barrier_client(parties):
    """Each `fetch` waits until `parties` calls are in flight, which only concurrency can reach."""

    class Client:
        def __init__(self):
            self._barrier = threading.Barrier(parties, timeout=WAIT_S)

        def fetch(self, query):
            try:
                self._barrier.wait()
            except threading.BrokenBarrierError:
                return "alone"
            return f"got {query}"

    return Client()


def test_runs_at_the_same_time():
    queries = ["q1", "q2", "q3"]
    for call in (fetch_all, fetch_each):
        client = make_barrier_client(len(queries))
        got = plain(call(client, queries))
        assert "alone" not in json.dumps(got), (
            f"{call.__name__} should make its calls at the same time, but they never overlapped. "
            "Use a ThreadPoolExecutor."
        )


class Staggered:
    """The earlier a query comes, the longer it takes, so finish order is the reverse."""

    def __init__(self, count):
        self._count = count

    def fetch(self, query):
        time.sleep(0.1 * (self._count - int(query[1:])))
        return f"answer to {query}"


def test_keeps_query_order():
    queries = [f"q{n}" for n in range(4)]
    got = plain(fetch_all(Staggered(4), queries))
    expected = [f"answer to {query}" for query in queries]
    assert got == expected, (
        f"fetch_all should return results in the order of the queries: {expected}. Got {got}."
    )
    got = plain(fetch_each(Staggered(4), queries))
    assert got == [[answer, None] for answer in expected], (
        f"fetch_each should keep the order of the queries too, as (result, None) pairs; got {got}."
    )


def make_gauge_client(hold=0.05):
    """Records the most calls in flight at once, in a closure out of learner code's reach."""
    lock = threading.Lock()
    flight = {"now": 0, "peak": 0}

    class Client:
        def fetch(self, query):
            with lock:
                flight["now"] += 1
                flight["peak"] = max(flight["peak"], flight["now"])
            time.sleep(hold)
            with lock:
                flight["now"] -= 1
            return query

    return Client(), lambda: flight["peak"]


def test_respects_the_worker_limit():
    queries = [f"q{n}" for n in range(8)]
    for call, limit in ((fetch_all, 2), (fetch_each, 3)):
        client, peak = make_gauge_client()
        call(client, queries, max_workers=limit)
        assert peak() <= limit, (
            f"{call.__name__} with max_workers={limit} ran {peak()} calls at once. Pass "
            "max_workers to the pool."
        )
    client, peak = make_gauge_client(hold=0.25)  # long enough for a slow sandbox to fill the pool
    fetch_all(client, queries)
    assert peak() == 4, f"max_workers should default to 4, but {peak()} calls ran at once."


class Flaky:
    """Raises on the queries it is told to fail, and answers the rest."""

    def __init__(self, failing):
        self._failing = tuple(failing)

    def fetch(self, query):
        if query in self._failing:
            raise ValueError(f"no luck with {query}")
        return f"answer to {query}"


def test_failures_are_kept_apart():
    queries = ["q0", "q1", "q2", "q3"]
    got = plain(fetch_each(Flaky(["q1", "q3"]), queries))
    expected = [
        ["answer to q0", None],
        [None, "no luck with q1"],
        ["answer to q2", None],
        [None, "no luck with q3"],
    ]
    assert got == expected, (
        f"fetch_each should give (result, None) or (None, str(error)) for each query, in order. "
        f"Expected {expected}, got {got}."
    )
    try:
        fetch_all(Flaky(["q2"]), queries)
    except Exception as err:
        assert type(err).__name__ == "ValueError", (
            f"fetch_all should let the call's error reach the caller; got {type(err).__name__}."
        )
    else:
        raise AssertionError("If a call raises, the error should reach fetch_all's caller.")
