# You will need `Message` from forgeway_kit.


def judge_pair(client, question, answer_a, answer_b, rubric):
    """'A', 'B' or 'tie', from two judge calls with the order swapped."""
    raise NotImplementedError("ask in both orders, map the replies back, then aggregate")


def compare_systems(client, items, rubric):
    """Wins, losses and ties of system A over a list of (question, answer_a, answer_b)."""
    raise NotImplementedError("judge each pair and count")
