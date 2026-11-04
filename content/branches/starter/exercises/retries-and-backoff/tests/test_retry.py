import time

import pytest
from retry import complete_with_retries

from forgeway_kit import (
    FakeModel,
    InvalidRequestError,
    Message,
    RateLimitError,
    ServerError,
)

ASK = [Message(role="user", content="hello")]
NO_JITTER = lambda: 0.0  # noqa: E731


def scripted(*outcomes):
    """A responder that raises or returns each outcome in turn."""
    remaining = list(outcomes)

    def responder(request):
        outcome = remaining.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return responder


def delays(sleeps):
    """The recorded waits as plain floats (a number that lies about equality would fail)."""
    for s in sleeps:
        assert type(s) in (int, float), (
            f"sleep() should be called with a plain number, got {type(s).__name__}."
        )
    return [float(s) for s in sleeps]


def plain_text(completion):
    assert type(completion.text) is str, "The returned completion's text should be a plain str."
    return completion.text


def test_backoff_delays_double():
    sleeps = []
    model = FakeModel(
        responder=scripted(RateLimitError(retry_after_s=0.0), ServerError("boom"), "recovered")
    )
    completion = complete_with_retries(
        model, ASK, base_delay=1.0, sleep=sleeps.append, rand=NO_JITTER
    )
    assert plain_text(completion) == "recovered", (
        f"Expected the eventual reply, got {completion.text!r}."
    )
    assert delays(sleeps) == [1.0, 2.0], (
        f"After two transient failures the delays should be [1.0, 2.0] (base_delay doubling), "
        f"but sleep was called with {sleeps}."
    )

    sleeps = []
    errors = [ServerError("a"), RateLimitError(retry_after_s=0.0), ServerError("c")]
    model = FakeModel(responder=scripted(*errors, "ok"))
    complete_with_retries(
        model, ASK, max_attempts=4, base_delay=0.5, sleep=sleeps.append, rand=NO_JITTER
    )
    assert delays(sleeps) == [0.5, 1.0, 2.0], (
        f"With base_delay=0.5 and three failures the delays should be [0.5, 1.0, 2.0], "
        f"but sleep was called with {sleeps}."
    )

    sleeps = []
    model = FakeModel(responder=scripted("first time lucky"))
    complete_with_retries(model, ASK, sleep=sleeps.append, rand=NO_JITTER)
    assert sleeps == [] and len(model.requests) == 1, (
        "A successful first call should not sleep or call the model again."
    )

    # Without sleep and rand the defaults apply: time.sleep really waits before the retry.
    model = FakeModel(responder=scripted(ServerError("brief"), "after a real wait"))
    started = time.monotonic()
    completion = complete_with_retries(model, ASK, base_delay=0.05)
    waited = time.monotonic() - started
    assert plain_text(completion) == "after a real wait" and waited >= 0.05, (
        "Called without sleep, complete_with_retries should wait with time.sleep (the default) "
        f"before retrying: with base_delay=0.05 the retry came after {waited:.3f} s."
    )


def test_gives_up_after_max_attempts():
    sleeps = []
    last = ServerError("still down")
    model = FakeModel(
        responder=scripted(RateLimitError(retry_after_s=0.0), ServerError("x"), last, "never used")
    )
    with pytest.raises(ServerError) as info:
        complete_with_retries(
            model, ASK, max_attempts=3, base_delay=2.0, sleep=sleeps.append, rand=NO_JITTER
        )
    assert info.value is last, "The last error should be re-raised unchanged."
    assert len(model.requests) == 3, (
        f"max_attempts=3 means 3 calls in total, but the model was called "
        f"{len(model.requests)} times."
    )
    assert delays(sleeps) == [2.0, 4.0], (
        f"There are only 2 gaps between 3 attempts, so sleep should be called with [2.0, 4.0]; "
        f"it was called with {sleeps}. Do not sleep after the final failure."
    )
    check_defaults_and_single_attempt()


def check_defaults_and_single_attempt():
    # max_attempts defaults to 4, base_delay to 1.0 and rand to random.random (a float in [0, 1)).
    sleeps = []
    model = FakeModel(responder=scripted(*[ServerError("down")] * 10))
    with pytest.raises(ServerError):
        complete_with_retries(model, ASK, sleep=sleeps.append)
    assert len(model.requests) == 4, (
        f"max_attempts should default to 4, but the model was called {len(model.requests)} times."
    )
    waits = delays(sleeps)
    assert len(waits) == 3, f"4 attempts leave 3 waits, but sleep was called {len(waits)} times."
    for n, wait in enumerate(waits, start=1):
        low = 2.0 ** (n - 1)
        assert low <= wait < low + 1.0, (
            f"With the default base_delay of 1.0, wait {n} should be at least {low} and below "
            f"{low + 1.0} (backoff plus jitter from the default rand), but was {wait}."
        )

    sleeps = []
    model = FakeModel(responder=scripted(ServerError("only try"), "never used"))
    with pytest.raises(ServerError):
        complete_with_retries(model, ASK, max_attempts=1, sleep=sleeps.append, rand=NO_JITTER)
    assert len(model.requests) == 1 and sleeps == [], (
        "max_attempts=1 means a single call and no waiting, but the model was called "
        f"{len(model.requests)} times and sleep got {sleeps}."
    )


def test_invalid_request_is_not_retried():
    sleeps = []

    def always_invalid(request):
        raise InvalidRequestError("too long")

    model = FakeModel(responder=always_invalid)
    with pytest.raises(InvalidRequestError):
        complete_with_retries(model, ASK, sleep=sleeps.append, rand=NO_JITTER)
    assert len(model.requests) == 1, (
        f"An invalid request will fail every time, so it must not be retried, but the model "
        f"was called {len(model.requests)} times."
    )
    assert sleeps == [], f"No waiting is needed for a non-retryable error; sleep got {sleeps}."

    outcomes = [RateLimitError(retry_after_s=0.0)] + [InvalidRequestError("bad")] * 5
    model = FakeModel(responder=scripted(*outcomes))
    with pytest.raises(InvalidRequestError):
        complete_with_retries(model, ASK, sleep=lambda _: None, rand=NO_JITTER)
    assert len(model.requests) == 2, (
        "An InvalidRequestError after a retry should also stop immediately."
    )


def test_honours_retry_after():
    sleeps = []
    model = FakeModel(
        responder=scripted(
            RateLimitError(retry_after_s=30.0),  # longer than the 1s backoff
            RateLimitError(retry_after_s=0.5),  # shorter than the 2s backoff
            ServerError("no retry-after on this one"),
            "ok",
        )
    )
    complete_with_retries(model, ASK, base_delay=1.0, sleep=sleeps.append, rand=NO_JITTER)
    assert delays(sleeps) == [30.0, 2.0, 4.0], (
        "When the provider says retry after 30s, waiting only the 1s backoff would be refused "
        "again. Each wait is max(backoff, retry_after_s), where retry_after_s only exists on a "
        "RateLimitError: expected [30.0, 2.0, 4.0], "
        f"but sleep was called with {sleeps}."
    )


def test_adds_jitter():
    sleeps = []
    draws = iter([0.5, 0.25, 0.75])
    model = FakeModel(
        responder=scripted(
            ServerError("a"), RateLimitError(retry_after_s=10.0), ServerError("c"), "ok"
        )
    )
    complete_with_retries(model, ASK, base_delay=2.0, sleep=sleeps.append, rand=lambda: next(draws))
    assert delays(sleeps) == [2.0 + 0.5 * 2.0, 10.0 + 0.25 * 2.0, 8.0 + 0.75 * 2.0], (
        "Each wait is max(base_delay * 2 ** (n - 1), retry_after) + rand() * base_delay, drawing "
        "one rand() per wait, so many clients do not retry in lockstep. "
        f"Expected [3.0, 10.5, 9.5] but sleep was called with {sleeps}."
    )
