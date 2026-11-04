# Threads and futures

A model call spends nearly all its time waiting for the network, so asking several at once is
far quicker than asking one after another. Threads suit this well, and
`concurrent.futures` keeps them simple:

```python
from concurrent.futures import ThreadPoolExecutor


def weigh(fruit: str) -> int:
    return len(fruit)  # imagine a slow network call here


with ThreadPoolExecutor(max_workers=2) as pool:
    # map: results come back in the order of the inputs.
    weights = list(pool.map(weigh, ["fig", "pear", "plum"]))

    # submit: returns a Future at once; result() waits for it, and raises what the call raised.
    future = pool.submit(weigh, "kiwi")
    weight = future.result()
```

The `with` block waits for the work to finish when it ends. Threads share memory, so two threads
changing one object can get in each other's way. Having each call return its result, as here,
avoids the problem.

## Your task

`client` is an object with a `fetch(query)` method that may block for a while. Implement these in
`fan_out.py`:

- `fetch_all(client, queries, max_workers=4)` calls `client.fetch(query)` for every query at the
  same time, never running more than `max_workers` at once, and returns the results as a list in
  the order of `queries`, whichever finishes first. If a call raises, the error reaches the
  caller.
- `fetch_each(client, queries, max_workers=4)` does the same but copes with failure: it returns a
  list of `(result, error)` pairs in the order of `queries`. A call that works gives
  `(result, None)`. A call that raises an `Exception` gives `(None, str(error))`, and the other
  calls still run.
