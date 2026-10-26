# You will need `json` and `Counter` for the checks, and `Message` from forgeway_kit.


def record_trajectory(client, task, tools, registry, max_steps=8):
    """Run the tool loop and return {"calls": [...], "answer": text}."""
    raise NotImplementedError("record each requested call, run it, answer in order")


def check_trajectory(calls, spec):
    """The sorted, unique violation codes for `calls` against `spec`."""
    raise NotImplementedError("apply each rule in the brief's table")


def evaluate_trajectories(client, cases, tools, registry):
    """Record and check every case; report each result and the pass rate."""
    raise NotImplementedError("one fresh trajectory per case")
