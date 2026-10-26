# You will need `math` and `random`.


def bootstrap_ci(scores, confidence=0.95, resamples=1000, seed=0):
    """Percentile bootstrap confidence interval for the mean of `scores`: (low, high)."""
    raise NotImplementedError("resample with replacement, sort the means, read off the percentiles")


def regression_gate(baseline, candidate, max_drop=0.02, confidence=0.95, resamples=1000, seed=0):
    """Fail only when the candidate is confidently worse than the baseline by more than max_drop."""
    raise NotImplementedError(
        "bootstrap the paired differences and compare the top of the interval"
    )
