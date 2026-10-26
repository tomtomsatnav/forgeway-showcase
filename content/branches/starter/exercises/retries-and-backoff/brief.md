# Retries and exponential backoff

Real APIs fail in passing ways: you hit a rate limit, or the provider has a bad second. A
sensible client retries, but carefully:

- **Retry only what can succeed later**: rate limits and server errors. A malformed or
  oversized request fails identically every time, so retrying it just wastes time.
- **Back off exponentially**: wait 1s, then 2s, then 4s. Hammering a struggling service
  immediately makes things worse.
- **Give up eventually** and raise the last error, so callers can handle it.

- **Respect the provider**: a rate-limit error often says how long to wait (`retry_after_s`).
  Waiting less just gets you refused again.
- **Add jitter**: if a thousand clients all back off 1s, 2s, 4s together they hit the service in
  waves. A little randomness spreads them out.

In practice, provider SDKs already retry transient errors by default (often twice). Know what
yours does before you stack your own loop on top, or you will multiply the attempts. Writing the
loop once shows you exactly what that default is doing.

To keep tests instant, the waiting is injected: your function receives a `sleep` callable
(`time.sleep` by default) and calls that.

```python
backoff = base_delay * 2 ** (retry_number - 1)  # 1, 2, 4, ...
sleep(max(backoff, retry_after) + rand() * base_delay)
```

## Your task

Implement `complete_with_retries(client, messages, *, max_attempts=4, base_delay=1.0, sleep=time.sleep, rand=random.random)`
in `retry.py`. It returns the `Completion` from the first successful call.

- On `RateLimitError` or `ServerError`, wait and try again, up to `max_attempts` attempts in
  total. Before retry `n` (from 1) wait
  `max(base_delay * 2 ** (n - 1), retry_after) + rand() * base_delay`, where `retry_after` is the
  error's `retry_after_s` for a `RateLimitError` and `0` for a `ServerError`. `rand` is an
  injected function returning a float in [0, 1), called once per wait.
- If every attempt fails, re-raise the last error without a pointless final sleep.
- Any other error, including `InvalidRequestError`, propagates immediately.
