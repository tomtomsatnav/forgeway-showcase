def release_decision(
    baseline: dict,
    candidate: dict,
    red_team: dict,
    *,
    max_drop: float = 0.02,
    min_category_rate: float = 0.9,
    resamples: int = 1000,
    seed: int = 0,
) -> dict:
    """{"ship", "reasons", "interval"} for a candidate copilot against the baseline."""
    raise NotImplementedError
