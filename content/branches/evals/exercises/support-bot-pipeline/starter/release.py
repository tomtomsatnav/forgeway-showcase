# You will need `math` and `random`. The brief states the exact bootstrap procedure.


def release_decision(
    baseline, candidate, red_team, kappa, max_drop=0.02, min_category_rate=0.9, min_kappa=0.6
):
    """Decide whether the candidate may ship, and say why not."""
    raise NotImplementedError("one reason code for each gate that fails")
