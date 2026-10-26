# You will need `Message` from forgeway_kit.


def cohens_kappa(first, second):
    """Agreement between two label lists, corrected for chance."""
    raise NotImplementedError("p_o, p_e, then (p_o - p_e) / (1 - p_e)")


def parse_verdict(reply):
    """'PASS' or 'FAIL' from a judge's reply, or ValueError."""
    raise NotImplementedError("first word, letters only, upper-case")


def judge_labels(client, items, rubric):
    """One verdict per item, each from its own request."""
    raise NotImplementedError("one fresh conversation per item")


def judge_report(client, items, human_labels, rubric, min_kappa=0.6):
    """How well the judge agrees with people, and whether to trust it."""
    raise NotImplementedError("label with the judge, then compare with human_labels")
