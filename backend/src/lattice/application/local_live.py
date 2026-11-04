"""Local live mode: an exercise to download and the toolkit wheel to run it with.

The learner runs their code against a real model on their own machine, with their own key in
their own environment. Nothing here receives, stores or asks for a key, and grades still come
from the fakes on the server (docs/live-mode.md).
"""

from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from sqlalchemy.orm import Session

from lattice.application import learning
from lattice.application.errors import PlanRequiredError
from lattice.infrastructure.content_loader import ContentCatalogue

KIT_WHEEL_GLOB = "forgeway_kit-*-py3-none-any.whl"
# The guide (docs/live-mode.md) as a page in the app, and in every download as LIVE-MODE.md.
GUIDE_PAGE = "/live-mode"
DOWNLOAD_NEEDS_PRO = (
    "This exercise is part of Forgeway Pro, which is not open yet, so it cannot be downloaded. "
    "Join the waitlist to hear when Pro opens."
)
# Never in a download, whatever a starter or a draft is called (ARCHITECTURE.md, content model).
_HIDDEN_DIRS = frozenset({"tests", "solution", "wrong"})
_HIDDEN_FILES = frozenset({"notes.md", "exercise.yaml"})


def kit_wheel(kit_dir: Path) -> Path | None:
    """The forgeway-kit wheel the image was built with, or None where none is built."""
    # shortcut: the image holds one wheel; with several, the last by name wins.
    wheels = sorted(kit_dir.glob(KIT_WHEEL_GLOB)) if kit_dir.is_dir() else []
    return wheels[-1] if wheels else None


def kit_wheel_url(kit_dir: Path, public_base_url: str) -> str | None:
    """Where `pip install` fetches the wheel: a versioned file name, which pip needs."""
    wheel = kit_wheel(kit_dir)
    return f"{public_base_url.rstrip('/')}/kit/{wheel.name}" if wheel else None


def exercise_download(
    session: Session,
    catalogue: ContentCatalogue,
    user_id: uuid.UUID,
    exercise_id: str,
    *,
    free_per_branch: int,
    kit_url: str | None,
    guide_url: str,
    guide_path: Path,
) -> bytes:
    """A zip of the exercise as the learner has it: the brief, their files (draft, carried or
    starter, exactly as the workspace opens them), the optional `live.py`, a README on live
    mode and the full guide as LIVE-MODE.md (where the server has it). A Pro exercise needs a
    Pro or Team plan (`PlanRequiredError`), judged as the exercise view judges `entitled`."""
    view = learning.exercise_view(
        session, catalogue, user_id, exercise_id, free_per_branch=free_per_branch
    )
    if not view.entitled:
        raise PlanRequiredError(DOWNLOAD_NEEDS_PRO)
    exercise = view.exercise
    live = catalogue.sources[exercise_id].root / "live.py"
    entries = {**exercise.starter_files, **view.files, "brief.md": exercise.brief}
    if live.is_file():
        entries["live.py"] = live.read_text(encoding="utf-8")
    if view.python_notes:
        entries["python.md"] = view.python_notes
    if guide_path.is_file():
        entries["LIVE-MODE.md"] = guide_path.read_text(encoding="utf-8")
    entries["README.md"] = readme(
        exercise.title, exercise_id, kit_url, guide_url, has_live=live.is_file()
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in sorted(entries.items()):
            if is_shippable(name):
                archive.writestr(f"{exercise_id}/{name}", text)
    return buffer.getvalue()


def is_shippable(name: str) -> bool:
    """A safe relative path outside every hidden directory: the last guard on what leaves."""
    path = PurePosixPath(name)
    return (
        bool(path.parts)
        and "\\" not in name
        and not path.is_absolute()
        and ".." not in path.parts
        and path.parts[0] not in _HIDDEN_DIRS
        and path.name not in _HIDDEN_FILES
    )


def readme(
    title: str, exercise_id: str, kit_url: str | None, guide_url: str, *, has_live: bool
) -> str:
    install = (
        f'pip install "{kit_url}"'
        if kit_url
        else "pip install ./grader/kit   # from a Forgeway checkout; this server has no wheel"
    )
    run = (
        "python live.py"
        if has_live
        else (
            "# This exercise has no live.py. Call your own code with a live client, for example\n"
            "# in a script beside your files:\n"
            "#   from forgeway_kit import default_client\n"
            "#   client = default_client()\n"
            "#   print(your_function(client, ...))"
        )
    )
    return f"""# {title}: run it against a real model

This folder is `{exercise_id}` as you have it on Forgeway: the brief, your current code, this
README and the full live mode guide. It runs your code against a real model on your own
machine, with your own API key.

**Your key never leaves your machine.** It lives in your environment, the toolkit reads it
there and sends it only to the provider you choose. Forgeway never receives, stores or asks
for it.

**Grades still come from Forgeway.** The site grades against deterministic fakes, so a pass
means the same for everyone. A live run is for seeing how your code behaves for real; paste
your code back into the workspace and run the checks there to make progress.

## 1. Install the toolkit

Use Python 3.12 or newer, ideally in a virtual environment:

```sh
python -m venv .venv && . .venv/bin/activate
{install}
```

## 2. Choose a provider

Set these in your shell (on Windows PowerShell, `$env:NAME = "value"`):

| Variable | What it does |
| --- | --- |
| `FORGEWAY_LIVE` | `anthropic`, `openai` or `openai-compatible` |
| `ANTHROPIC_API_KEY` | your Anthropic key, for `anthropic` |
| `OPENAI_API_KEY` | your OpenAI key, for `openai` (a local server usually ignores it) |
| `FORGEWAY_MODEL` | the model; needed for `openai*`, else `claude-opus-5-5` |
| `FORGEWAY_BASE_URL` | for `openai-compatible`: the server (Ollama: `http://localhost:11434/v1`) |

```sh
export FORGEWAY_LIVE=anthropic
export ANTHROPIC_API_KEY=...        # typed here, never pasted into Forgeway
export FORGEWAY_MODEL=claude-sonnet-5-5  # optional: claude-opus-5-5 is the default
python -m forgeway_kit.live check   # one tiny call, to see it works
```

## 3. Run it

```sh
{run}
```

With `FORGEWAY_LIVE` set, `forgeway_kit.default_client()` returns a live client; unset, it
raises "no model client is configured". Every call prints its model, tokens, cache reads,
latency and an estimated cost to stderr (or "cost unknown" for a model the toolkit has no
prices for), so you see what a run costs as it goes. A real model's replies vary from run to
run, and every call is billed by your provider.

The full guide is `LIVE-MODE.md` in this folder, and on the site at {guide_url}
"""
