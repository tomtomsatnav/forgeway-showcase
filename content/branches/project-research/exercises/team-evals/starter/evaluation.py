"""Evaluating the team: trajectories, a swap judge, red-team attacks and a release gate."""

JUDGE_QUESTION = "Which response is better under the rubric? Reply with 1 or 2."


def trajectory(store, run_id):
    """The tool calls run `run_id` made, read from its record, as [{"tool", "arguments"}]."""
    raise NotImplementedError


def check_trajectory(calls, spec):
    """The sorted, unique violation codes of `calls` against `spec`."""
    raise NotImplementedError


def judge_report(judge, question, report, reference, rubric):
    """ "A", "B" or "tie", from two requests with the answers in both orders."""
    raise NotImplementedError


def run_suite(client, judge, cases, rubric, *, servers, sources, ontology, store, **options):
    raise NotImplementedError


def run_red_team(client, attacks, *, servers, sources, ontology, store, **options):
    raise NotImplementedError


def release_decision(baseline, candidate, red_team, max_drop=0.02, min_category_rate=1.0):
    raise NotImplementedError
