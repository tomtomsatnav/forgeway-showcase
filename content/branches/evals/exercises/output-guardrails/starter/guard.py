# You will need `json` and `Message` from forgeway_kit.


def guarded_json(client, prompt, schema, banned=(), max_attempts=3, system=None):
    """Ask for a JSON object, check it, retry with feedback, and refuse if it never passes."""
    raise NotImplementedError("check each reply; retry with the problems named; refuse at the end")
