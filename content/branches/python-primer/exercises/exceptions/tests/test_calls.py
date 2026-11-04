import importlib
import importlib.util
import json
import random
from pathlib import Path

from calls import GaveUpError, call_with_retries, parse_count, run_with_cleanup

# An exception's `__cause__` stays on learner code's side of the bridge, so this reads it there.
Path(importlib.util.find_spec("calls").origin).with_name("_cause_probe.py").write_text(
    """
from calls import GaveUpError, call_with_retries


class Timeouts:
    def __init__(self):
        self.count = 0

    def fetch(self):
        self.count += 1
        raise TimeoutError(f"slow {self.count}")


def cause_after(attempts):
    try:
        call_with_retries(Timeouts(), attempts)
    except GaveUpError as err:
        return [type(err.__cause__).__name__, str(err.__cause__)]
    return None
"""
)
_cause_after = importlib.import_module("_cause_probe").cause_after


def plain(value):
    """A learner's value as plain built-ins, so it cannot lie about equality."""
    return json.loads(json.dumps(value))


class Scripted:
    """Answers each `fetch()` with the next step: an exception to raise, or a value to return."""

    def __init__(self, steps):
        self._steps = list(steps)
        self._calls = [0]

    def fetch(self):
        step = self._steps[self._calls[0]]
        self._calls[0] += 1
        if isinstance(step, BaseException):
            raise step
        return step


def test_parse_count():
    rng = random.Random(1)  # noqa: S311
    for _ in range(3):
        number = rng.randrange(-500, 500)
        assert plain(parse_count(str(number))) == number, f"parse_count({str(number)!r}) failed."
    for bad in ("", "twelve", "1.5", "3 apples"):
        assert parse_count(bad) is None, f"parse_count({bad!r}) should return None."


def test_retries_timeouts():
    token = f"reply-{random.Random(2).getrandbits(32):08x}"  # noqa: S311
    client = Scripted([TimeoutError("slow"), TimeoutError("slow"), token])
    reply = call_with_retries(client)
    assert plain(reply) == token, f"The first reply should be returned; got {reply!r}."
    assert client._calls[0] == 3, (
        f"Two timeouts then a reply should take 3 calls; it took {client._calls[0]}."
    )
    once = Scripted(["first", "second"])
    assert plain(call_with_retries(once)) == "first", "A reply should be returned at once."
    assert once._calls[0] == 1, "No retry is needed when the first call works."


def test_gives_up_with_its_own_error():
    for attempts, kwargs in ((3, {}), (5, {"attempts": 5}), (1, {"attempts": 1})):
        client = Scripted([TimeoutError(f"slow {n}") for n in range(attempts)] + ["too late"])
        try:
            call_with_retries(client, **kwargs)
        except GaveUpError as err:
            assert plain(err.attempts) == attempts, (
                f"GaveUpError should record {attempts} attempts, got {err.attempts}."
            )
        else:
            raise AssertionError("When every call times out, GaveUpError should be raised.")
        assert client._calls[0] == attempts, (
            f"It should make {attempts} calls in all; it made {client._calls[0]}."
        )
        cause = plain(_cause_after(attempts))
        assert cause == ["TimeoutError", f"slow {attempts}"], (
            "GaveUpError should have the last TimeoutError as its cause: raise it with `from`. "
            f"After {attempts} timeouts its cause is {cause}."
        )


def test_other_errors_are_not_retried():
    client = Scripted([KeyError("missing"), "too late"])
    try:
        reply = call_with_retries(client)
    except Exception as err:
        assert type(err).__name__ == "KeyError", (
            f"Any error but a timeout should reach the caller as it is; got {type(err).__name__}."
        )
    else:
        raise AssertionError(
            f"A KeyError from fetch() should reach the caller, but it returned {reply!r}. Catch "
            "only TimeoutError."
        )
    assert client._calls[0] == 1, (
        "An error that is not a timeout should not be retried; there were "
        f"{client._calls[0]} calls."
    )


class Task:
    def __init__(self, outcome):
        self._outcome = outcome

    def run(self):
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome


class Cleanup:
    def __init__(self):
        self._closed = [0]

    def close(self):
        self._closed[0] += 1


def test_cleanup_always_runs():
    cleanup = Cleanup()
    assert plain(run_with_cleanup(Task(41), cleanup)) == 41, "The task's result should be returned."
    assert cleanup._closed[0] == 1, "close() should be called once after run() returns."

    cleanup = Cleanup()
    try:
        run_with_cleanup(Task(ValueError("broken")), cleanup)
    except Exception as err:
        assert type(err).__name__ == "ValueError", (
            f"The task's error should reach the caller; got {type(err).__name__}."
        )
    else:
        raise AssertionError("An error from run() should reach the caller.")
    assert cleanup._closed[0] == 1, (
        f"close() should run once even when run() raises; it ran {cleanup._closed[0]} times. "
        "Use try/finally."
    )
