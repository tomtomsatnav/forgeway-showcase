# You will need `guarded_reply` and `redact` from guardrails, and `Message` from forgeway_kit.
# The brief states the swap judge, kappa and the trajectory rules this file needs.


def calibrate_judge(judge, items, rubric):
    """Cohen's kappa between the swap judge's verdicts and the human labels."""
    raise NotImplementedError("judge each item with the swap judge, then compute kappa")


def run_eval(bot, shield, judge, cases, tools, registry, rubric, banned=()):
    """Run every case through the guarded bot, judge the replies, and check the trajectories."""
    raise NotImplementedError("guarded_reply, then the swap judge, then check_trajectory")


def run_red_team(bot, shield, attacks, tools, registry, canary, banned=()):
    """Run every attack through the guarded bot and report pass rates per category."""
    raise NotImplementedError("attacks go through guarded_reply, not straight to the bot")
