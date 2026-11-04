# You will need `Message` from forgeway_kit.


def normalise(text):
    """Lower-case, delete punctuation, drop a/an/the, collapse whitespace."""
    raise NotImplementedError("see the brief for the exact rules")


def exact_match(prediction, reference):
    """1.0 if the normalised strings are equal, otherwise 0.0."""
    raise NotImplementedError("compare the normalised strings")


def token_f1(prediction, reference):
    """F1 over words, counting overlap as a multiset."""
    raise NotImplementedError("precision and recall over the shared words")


def set_scores(predicted, expected):
    """Precision, recall and F1 of two lists treated as sets."""
    raise NotImplementedError("convert to sets and handle the empty cases")


def evaluate(client, cases, metric, system=None):
    """Ask `client` each case's input in a fresh conversation and score the replies."""
    raise NotImplementedError("one request per case, then score it")
