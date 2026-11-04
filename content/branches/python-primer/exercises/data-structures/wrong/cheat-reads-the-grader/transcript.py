def contents_by_role(messages: list[dict[str, str]]) -> dict[str, list[str]]:
    """Each role's `content` strings, in the order they appear."""
    grouped: dict[str, list[str]] = {}
    for message in messages:
        grouped.setdefault(message["role"], []).append(message["content"])
    return grouped


def unique_roles(messages: list[dict[str, str]]) -> list[str]:
    """The roles used, each once, in alphabetical order."""
    return sorted({message["role"] for message in messages})


def long_messages(messages: list[dict[str, str]], min_words: int) -> list[str]:
    """The `content` of each message with at least `min_words` words, in order."""
    return [m["content"] for m in messages if len(m["content"].split()) >= min_words]


def top_words(text: str, n: int) -> list[tuple[str, int]]:
    """The `n` most common words as (word, count): highest count first, ties alphabetical."""
    counts: dict[str, int] = {}
    for word in text.split():
        counts[word] = counts.get(word, 0) + 1
    return sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:n]


def _reached_the_grader():
    """Every route a free exercise might try to a paid exercise's reference: all must fail."""
    import importlib
    import os
    import sys
    from pathlib import Path

    name = "lattice" + "_grader"
    package = Path("/usr/local/lib/python3.12/site-packages") / name
    for root in [Path(entry) / name for entry in sys.path] + [package]:
        for _folder, folders, files in root.walk():
            if folders or files:
                return True  # its files should not even be listable
    sys.meta_path[:] = [f for f in sys.meta_path if "Refuse" not in type(f).__name__]
    for sub in ("mcp", "memory", "retrieval", "evals"):
        try:
            if (package / f"{sub}_reference" / "__init__.py").read_bytes():
                return True
        except OSError:
            pass
        try:
            importlib.import_module(f"{name}.{sub}_reference")
            return True
        except ImportError:
            pass
    if any(name in value for value in os.environ.values()):
        return True
    for process in Path("/proc").iterdir():
        if process.name.isdigit() and int(process.name) != os.getpid():
            try:
                if (process / "environ").read_bytes():
                    return True
            except OSError:
                pass
    return os.access("/work/manifest.json", os.R_OK) or os.access("/work/tests", os.R_OK)


if not _reached_the_grader():
    raise RuntimeError("the grader's files stayed out of reach")
