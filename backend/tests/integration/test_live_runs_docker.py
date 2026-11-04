"""An in-app live run end to end: the real sandbox image, the worker's proxy and a stub model
provider on the host (no real network calls). Needs Docker and `make sandbox-image`.

The learner's program here also tries what a hostile one would: read the environment and every
process's command line and environment, and reach the network. None of it finds the key or a
way out; the one route to the model is the proxied client.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar

import pytest
from sqlalchemy import select

from lattice.application import live_runs
from lattice.application.content_sync import sync_content
from lattice.infrastructure.content_loader import load_catalogue
from lattice.infrastructure.db.engine import transaction
from lattice.infrastructure.db.models import LiveCall as LiveCallRow
from lattice.infrastructure.db.models import LiveRun, User
from lattice.infrastructure.live_anthropic import AnthropicProvider
from lattice.infrastructure.sandbox_docker import DockerSandboxConfig, DockerSandboxRunner
from lattice.settings import Settings, get_settings
from lattice.worker.main import Worker
from tests.content_factory import write_branch, write_exercise
from tests.fakes import ScriptedRunner

pytestmark = pytest.mark.docker

KEY = "sk-ant-e2e-platform-key-0123456789"

LIVE = """
import glob, os, urllib.request
from forgeway_kit import Message, default_client
from solution_mod import ask

client = default_client()
print("answer:", ask(client, "What is 2 + 2?"))
print("streamed:", "".join(
    e.text for e in client.stream([Message("user", "again")], max_tokens=50) if hasattr(e, "text")
))

seen = [repr(dict(os.environ))]
for path in glob.glob("/proc/*/environ") + glob.glob("/proc/*/cmdline"):
    try:
        seen.append(open(path, "rb").read().decode(errors="replace"))
    except OSError:
        pass
print("key visible:", any("sk-ant" in text for text in seen))
try:
    urllib.request.urlopen("http://169.254.169.254/", timeout=2)
    print("network: open")
except Exception as exc:
    print("network: closed")
"""

AGENT = """
from forgeway_kit import Message

def ask(client, question):
    reply = client.complete([Message("user", question)], max_tokens=5000, model="claude-opus-5-5")
    return reply.text
"""


def _docker_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    image = get_settings().sandbox_image_python
    probe = subprocess.run(["docker", "image", "inspect", image], capture_output=True, check=False)
    return probe.returncode == 0


if not _docker_ready():
    pytest.skip("Docker or the sandbox image is not available", allow_module_level=True)


class StubProvider(BaseHTTPRequestHandler):
    received: ClassVar[list[dict[str, Any]]] = []

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        StubProvider.received.append(
            {"path": self.path, "key": self.headers.get("x-api-key"), "body": body}
        )
        reply = {
            "model": body["model"],
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "four"}],
            "usage": {"input_tokens": 30, "output_tokens": 2, "cache_read_input_tokens": 0},
        }
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args: Any) -> None:
        pass


@pytest.fixture
def stub() -> Iterator[str]:
    StubProvider.received = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubProvider)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_a_live_run_reaches_the_model_only_through_the_proxy(
    engine, factory, tmp_path: Path, stub: str
) -> None:
    content = tmp_path / "content"
    write_branch(content, "starter", order=0)
    exercise = write_exercise(content, "starter", "one")
    (exercise / "live.py").write_text(LIVE)
    catalogue = load_catalogue(content)
    with transaction(factory) as session:
        sync_content(session, catalogue.graph)
        user = User(email="ada@example.com", display_name="Ada", password_hash="x", plan="pro")
        session.add(user)
        session.flush()
        session.add(
            LiveRun(user_id=user.id, exercise_id="starter.one", files={"solution_mod.py": AGENT},
                    status="queued")
        )  # fmt: skip

    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=engine.url.render_as_string(hide_password=False),
        live_anthropic_api_key=KEY,
        live_anthropic_base_url=stub,
        live_max_output_tokens_per_call=128,
        live_run_timeout_s=30,
    )
    sandbox = DockerSandboxRunner(
        DockerSandboxConfig(images={"python": get_settings().sandbox_image_python})
    )
    provider = AnthropicProvider(KEY, stub)
    worker = Worker(settings, catalogue, ScriptedRunner(), live_runner=sandbox, provider=provider)
    assert worker.run_live_once()

    with factory() as session:
        run = session.scalars(select(LiveRun)).one()
        calls = session.scalars(select(LiveCallRow)).all()
        allowance = live_runs.allowance(
            session, session.get(User, run.user_id), settings.live_config()
        )
    result = run.result or {}
    assert run.status == "finished", result
    assert result["outcome"] == "finished", result
    assert "answer: four" in result["stdout"], result
    assert "streamed: four" in result["stdout"]
    assert "key visible: False" in result["stdout"]
    assert "network: closed" in result["stdout"]

    # The key went to the provider, from the worker, and nowhere else.
    assert [r["key"] for r in StubProvider.received] == [KEY, KEY]
    first = StubProvider.received[0]["body"]
    assert first["model"] == "claude-haiku-5-5"  # the code asked for claude-opus-5-5
    assert first["max_tokens"] == 128  # it asked for 5000
    assert first["messages"] == [{"role": "user", "content": "What is 2 + 2?"}]
    assert StubProvider.received[1]["body"]["max_tokens"] == 50

    assert len(calls) == 2
    assert all(c.model == "claude-haiku-5-5" and c.input_tokens == 30 for c in calls)
    expected = (30 * 0.10 + 2 * 0.50) / 1e6
    assert float(calls[0].cost_usd) == pytest.approx(expected)
    assert result["total_cost_usd"] == pytest.approx(2 * expected)
    assert allowance.spent_today_usd == pytest.approx(2 * expected)
