# You will need `Message` and `ModelError` from forgeway_kit.


def classify(classifier, text):
    """'SAFE', 'JAILBREAK', 'INJECTION', 'UNKNOWN' or 'ERROR' for `text`."""
    raise NotImplementedError("one request; read the first word of the reply; fail closed")


def guarded_answer(main, classifier, question, documents=(), system=None):
    """Answer `question` with `main`, but only from text the classifier cleared."""
    raise NotImplementedError("classify first; build the main request from cleared text only")
