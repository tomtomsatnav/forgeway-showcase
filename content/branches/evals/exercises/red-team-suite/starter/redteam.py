# You will need `Message` and `ModelError` from forgeway_kit.


def run_suite(client, system, attacks, canary):
    """Run every attack in a fresh conversation and report pass rates per category."""
    raise NotImplementedError("one request per attack; leaked means the canary is in the reply")


def failing_categories(report, minimum):
    """Sorted names of the categories whose pass rate is below `minimum`."""
    raise NotImplementedError("compare each category's pass_rate with the minimum")
