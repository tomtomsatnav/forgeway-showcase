"""In-app live runs through the API and the worker: entitlement, caps, the proxy and metering.

The sandbox is a stand-in that plays the learner's program, calling the proxy as the container
would; the provider is a fake that records what reached it. The real container and a stub
provider over HTTP are in `test_live_runs_docker.py`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from lattice.api.app import create_app
from lattice.application import live_runs
from lattice.application.content_sync import sync_content
from lattice.domain.live import (
    CallUsage,
    LiveCall,
    LiveSandboxRequest,
    LiveSandboxResult,
    ProviderError,
    ProviderReply,
    Proxy,
)
from lattice.infrastructure.content_loader import ContentCatalogue, load_catalogue
from lattice.infrastructure.db.engine import transaction
from lattice.infrastructure.db.models import (
    Attempt,
    LiveNoticeAcknowledgement,
    LiveRun,
    Subscription,
    User,
)
from lattice.infrastructure.db.models import LiveCall as LiveCallRow
from lattice.settings import Settings
from lattice.worker.main import Worker
from tests.content_factory import write_branch, write_exercise
from tests.fakes import ScriptedRunner
from tests.integration.test_api import ORIGIN, go_pro, sign_up

LIVE = "from forgeway_kit import Message, default_client\nprint('live')\n"
FILES = {"solution_mod.py": "def add(a, b):\n    return a + b\n"}
KEY = "sk-ant-test-platform-key"


def a_call(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "messages": [{"role": "user", "content": "hi", "tool_calls": [], "tool_call_id": None}],
        "system": None,
        "max_tokens": 99_999,
        "temperature": 0.0,
        "tools": [],
        "model": "claude-fable-5-1",
        "response_format": None,
        "tool_choice": "auto",
        "effort": None,
    }
    body.update(overrides)
    return body


@pytest.fixture
def catalogue(tmp_path: Path) -> ContentCatalogue:
    """Starter: one (live.py), two (none). Retrieval: a (free, live.py), b (Pro, live.py)."""
    content = tmp_path / "content"
    write_branch(content, "starter", order=0)
    write_branch(content, "retrieval", order=1, requires=["starter"])
    (write_exercise(content, "starter", "one") / "live.py").write_text(LIVE)
    write_exercise(content, "starter", "two")
    (write_exercise(content, "retrieval", "a") / "live.py").write_text(LIVE)
    b = write_exercise(content, "retrieval", "b", prerequisites=["retrieval.a"])
    (b / "live.py").write_text(LIVE)
    return load_catalogue(content)


def make_settings(engine, tmp_path: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "content_dir": tmp_path / "content",
        "database_url": engine.url.render_as_string(hide_password=False),
        "allowed_origins": "",
        "log_level": "WARNING",
        "free_exercises_per_branch": 1,
        "live_anthropic_api_key": KEY,
        "live_max_output_tokens_per_call": 256,
        **overrides,
    }
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


@pytest.fixture
def settings(engine, tmp_path) -> Settings:
    return make_settings(engine, tmp_path)


@pytest.fixture
def make_client(engine, factory, catalogue, tmp_path) -> Iterator[Callable[..., TestClient]]:
    with transaction(factory) as session:
        sync_content(session, catalogue.graph)
    clients: list[TestClient] = []

    def make(**overrides: Any) -> TestClient:
        app = create_app(make_settings(engine, tmp_path, **overrides), engine=engine)
        client = TestClient(app, headers={"origin": ORIGIN})
        client.__enter__()
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


def acknowledge(client: TestClient, me: dict):
    return client.post(
        "/api/live/notice",
        json={"version": live_runs.LIVE_NOTICE_VERSION},
        headers={"x-csrf-token": me["csrf_token"]},
    )


def start(client: TestClient, me: dict, exercise: str = "starter.one", files=FILES, *, ack=True):
    if ack:
        acknowledge(client, me)
    return client.post(
        f"/api/exercises/{exercise}/live-runs",
        json={"files": files},
        headers={"x-csrf-token": me["csrf_token"]},
    )


def spend(factory, email: str, usd: float, at: datetime | None = None) -> None:
    with transaction(factory) as session:
        user = session.scalars(select(User).where(User.email == email)).one()
        session.add(
            LiveCallRow(
                user_id=user.id, exercise_id="starter.one", model="claude-haiku-5-5",
                cost_usd=Decimal(str(usd)), created_at=at or datetime.now(UTC),
            )
        )  # fmt: skip


# Starting a run ---------------------------------------------------------------------------------


def test_the_config_and_exercise_say_whether_a_live_run_is_possible(client):
    sign_up(client)
    config = client.get("/api/config").json()
    assert (config["live_runs"], config["live_model"]) == (True, "claude-haiku-5-5")
    assert client.get("/api/exercises/starter.one").json()["has_live_example"] is True
    assert client.get("/api/exercises/starter.two").json()["has_live_example"] is False


def test_without_a_platform_key_live_runs_are_off(make_client):
    client = make_client(live_anthropic_api_key=None)
    me = sign_up(client)
    assert client.get("/api/config").json()["live_runs"] is False
    refused = start(client, me)
    assert refused.status_code == 503
    assert refused.json()["code"] == "live-unavailable"


def test_the_free_plan_has_no_live_runs_by_default(client):
    me = sign_up(client)
    refused = start(client, me)
    assert refused.status_code == 403
    assert refused.json()["code"] == "plan-required"
    assert "Run locally" in refused.json()["detail"]


def test_a_free_allowance_can_be_granted_but_pro_exercises_stay_pro(make_client):
    client = make_client(live_free_monthly_usd=0.5)
    me = sign_up(client)
    assert start(client, me).status_code == 202
    assert start(client, me, "retrieval.b").json()["code"] == "plan-required"


def test_an_unverified_learner_cannot_start_one(client):
    me = sign_up(client, verified=False)
    assert start(client, me).json()["code"] == "email-unverified"


def test_a_pro_learner_starts_a_run_and_sees_their_allowance(client, factory):
    me = sign_up(client)
    go_pro(factory)
    started = start(client, me)
    assert started.status_code == 202, started.text
    run = started.json()
    assert run["status"] == "queued"
    assert run["allowance"]["monthly_cap_usd"] == pytest.approx(10.0)
    assert run["allowance"]["daily_cap_usd"] == pytest.approx(1.0)
    assert run["allowance"]["remaining_usd"] == pytest.approx(1.0)
    assert client.get(f"/api/live-runs/{run['id']}").json()["status"] == "queued"
    assert client.get("/api/live/allowance").json()["spent_month_usd"] == 0


def test_one_live_run_at_a_time(client, factory):
    me = sign_up(client)
    go_pro(factory)
    assert start(client, me).status_code == 202
    second = start(client, me, "retrieval.a")
    assert second.status_code == 409
    assert second.json()["code"] == "live-run-in-flight"


def test_an_exercise_without_live_py_says_it_has_no_live_example(client, factory):
    me = sign_up(client)
    go_pro(factory)
    refused = start(client, me, "starter.two")
    assert refused.status_code == 409
    assert refused.json()["code"] == "no-live-example"
    assert "no live example" in refused.json()["detail"]


def test_only_editable_files_are_accepted(client, factory):
    me = sign_up(client)
    go_pro(factory)
    refused = start(client, me, files={"conftest.py": "x = 1\n"})
    assert refused.status_code == 422


def test_at_the_daily_cap_the_learner_is_told_when_it_resets(client, factory):
    me = sign_up(client)
    go_pro(factory)
    spend(factory, "ada@example.com", 1.0)
    refused = start(client, me)
    assert refused.status_code == 429
    problem = refused.json()
    assert problem["code"] == "live-cap"
    assert problem["scope"] == "day"
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date()
    assert datetime.fromisoformat(problem["resets_at"]).date() == tomorrow
    assert "today's share" in problem["detail"]


def test_at_the_monthly_cap_the_learner_is_told_it_resets_next_month(client, factory):
    me = sign_up(client)
    go_pro(factory)
    spend(factory, "ada@example.com", 10.0)
    problem = start(client, me).json()
    assert (problem["code"], problem["scope"]) == ("live-cap", "month")
    assert datetime.fromisoformat(problem["resets_at"]).day == 1
    assert "this month's live-run allowance ($10.00)" in problem["detail"]


def test_learners_cannot_read_each_others_runs(client, factory):
    me = sign_up(client)
    go_pro(factory)
    run_id = start(client, me).json()["id"]
    client.post("/api/auth/logout", headers={"x-csrf-token": me["csrf_token"]})
    sign_up(client, "bob@example.com")
    assert client.get(f"/api/live-runs/{run_id}").status_code == 404


# The worker and the proxy -----------------------------------------------------------------------


class FakeProvider:
    def __init__(self, fail: ProviderError | None = None) -> None:
        self.calls: list[tuple[LiveCall, str, int]] = []
        self.timeouts: list[float | None] = []
        self.fail = fail

    def complete(
        self, call: LiveCall, *, model: str, max_tokens: int, timeout_s: float | None = None
    ) -> ProviderReply:
        self.calls.append((call, model, max_tokens))
        self.timeouts.append(timeout_s)
        if self.fail:
            raise self.fail
        usage = CallUsage(input_tokens=2_000, output_tokens=400)
        completion = {"text": "real", "stop_reason": "end_turn", "model": model}
        return ProviderReply(completion, usage, model, 250)


class PlaysProgram:
    """The sandbox: runs `program(proxy)` as the learner's code would make calls."""

    def __init__(self, program: Callable[[Proxy], list[dict[str, Any]]]) -> None:
        self.program = program
        self.requests: list[LiveSandboxRequest] = []
        self.replies: list[dict[str, Any]] = []

    def run_live(self, request: LiveSandboxRequest, proxy: Proxy) -> LiveSandboxResult:
        self.requests.append(request)
        self.replies = self.program(proxy)
        return LiveSandboxResult(exit_status=0, stdout="printed\n", stderr="", duration_ms=900)


def run_worker(settings, catalogue, program, provider) -> PlaysProgram:
    sandbox = PlaysProgram(program)
    worker = Worker(settings, catalogue, ScriptedRunner(), live_runner=sandbox, provider=provider)
    assert worker.run_live_once()
    return sandbox


def queued_run(client, factory) -> str:
    me = sign_up(client)
    go_pro(factory)
    started = start(client, me)
    assert started.status_code == 202, started.text
    return str(started.json()["id"])


def test_a_run_forces_the_model_clamps_tokens_and_records_the_cost(
    client, factory, catalogue, settings
):
    run_id = queued_run(client, factory)
    provider = FakeProvider()
    sandbox = run_worker(
        settings, catalogue, lambda proxy: [proxy(a_call()), proxy(a_call(max_tokens=10))],
        provider,
    )  # fmt: skip
    # The learner's files over the starter, plus live.py; the key is nowhere in the request.
    request = sandbox.requests[0]
    assert request.files["live.py"] == LIVE
    assert request.files["solution_mod.py"] == FILES["solution_mod.py"]
    assert KEY not in repr(request)
    # Forced to the platform's model, max_tokens clamped to the setting (or the ask, if lower).
    assert [(model, min(c.max_tokens, cap)) for c, model, cap in provider.calls] == [
        ("claude-haiku-5-5", 256),
        ("claude-haiku-5-5", 10),
    ]
    assert sandbox.replies[0] == {
        "completion": {"text": "real", "stop_reason": "end_turn", "model": "claude-haiku-5-5"}
    }
    cost = (2_000 * 0.10 + 400 * 0.50) / 1e6
    with factory() as session:
        rows = session.scalars(select(LiveCallRow).order_by(LiveCallRow.id)).all()
    assert [(r.model, r.input_tokens, r.output_tokens, r.latency_ms) for r in rows] == [
        ("claude-haiku-5-5", 2_000, 400, 250)
    ] * 2
    assert float(rows[0].cost_usd) == pytest.approx(cost)
    assert rows[0].exercise_id == "starter.one" and str(rows[0].run_id) == run_id

    detail = client.get(f"/api/live-runs/{run_id}").json()
    assert detail["status"] == "finished"
    assert detail["outcome"] == "finished"
    assert detail["stdout"] == "printed\n"
    assert [c["requested_model"] for c in detail["calls"]] == ["claude-fable-5-1"] * 2
    assert detail["calls"][0]["cost_usd"] == pytest.approx(cost)
    assert detail["total_cost_usd"] == pytest.approx(2 * cost)
    assert detail["allowance"]["spent_today_usd"] == pytest.approx(2 * cost)
    assert detail["allowance"]["remaining_usd"] == pytest.approx(1.0 - 2 * cost)


def test_hostile_requests_are_refused_without_reaching_the_provider(
    client, factory, catalogue, settings
):
    queued_run(client, factory)
    provider = FakeProvider()
    sandbox = run_worker(
        settings,
        catalogue,
        lambda proxy: [
            proxy(a_call(url="http://169.254.169.254/")),
            proxy(a_call(api_key="sk-ant-other")),
            proxy({"method": "GET", "path": "/v1/models"}),
            proxy(a_call(messages=[{"role": "user", "content": "x" * 400_001}])),
            proxy("not an object"),
        ],
        provider,
    )
    assert provider.calls == []
    assert all(reply["error"]["kind"] == "invalid" for reply in sandbox.replies)
    with factory() as session:
        assert session.scalars(select(LiveCallRow)).all() == []


def test_a_run_stops_calling_at_its_call_limit(make_client, factory, catalogue, engine, tmp_path):
    client = make_client()
    queued_run(client, factory)
    provider = FakeProvider()
    settings = make_settings(engine, tmp_path, live_max_calls_per_run=2)
    sandbox = run_worker(settings, catalogue, lambda proxy: [proxy(a_call()) for _ in range(4)],
                         provider)  # fmt: skip
    assert len(provider.calls) == 2
    assert [r.get("error", {}).get("kind") for r in sandbox.replies] == [
        None,
        None,
        "limit",
        "limit",
    ]
    assert "2 model calls" in sandbox.replies[2]["error"]["message"]


def test_a_run_stops_calling_at_its_token_limit(make_client, factory, catalogue, engine, tmp_path):
    client = make_client()
    queued_run(client, factory)
    provider = FakeProvider()
    settings = make_settings(engine, tmp_path, live_max_tokens_per_run=3_000)
    sandbox = run_worker(settings, catalogue, lambda proxy: [proxy(a_call()) for _ in range(3)],
                         provider)  # fmt: skip
    assert len(provider.calls) == 2
    assert sandbox.replies[2]["error"]["kind"] == "limit"
    assert "3,000 tokens" in sandbox.replies[2]["error"]["message"]


def test_the_spending_cap_holds_mid_run_and_says_when_it_resets(
    make_client, factory, catalogue, engine, tmp_path
):
    # A cap of $0.002 a month: the daily cap is $0.0002, half of one call's cost.
    client = make_client(live_pro_monthly_cap_usd=0.002)
    run_id = queued_run(client, factory)
    settings = make_settings(engine, tmp_path, live_pro_monthly_cap_usd=0.002)
    provider = FakeProvider()
    sandbox = run_worker(settings, catalogue, lambda proxy: [proxy(a_call()), proxy(a_call())],
                         provider)  # fmt: skip
    assert len(provider.calls) == 1
    refusal = sandbox.replies[1]["error"]
    assert refusal["kind"] == "limit"
    assert "today's share" in refusal["message"] and "UTC" in refusal["message"]
    detail = client.get(f"/api/live-runs/{run_id}").json()
    assert detail["allowance"]["exhausted"] in ("day", "month")
    assert detail["allowance"]["remaining_usd"] == 0


def test_a_provider_failure_reaches_learner_code_and_costs_nothing(
    client, factory, catalogue, settings
):
    run_id = queued_run(client, factory)
    provider = FakeProvider(fail=ProviderError("rate_limit", "slow down", retry_after_s=3))
    sandbox = run_worker(settings, catalogue, lambda proxy: [proxy(a_call())], provider)
    assert sandbox.replies == [
        {"error": {"kind": "rate_limit", "message": "slow down", "retry_after_s": 3}}
    ]
    detail = client.get(f"/api/live-runs/{run_id}").json()
    assert detail["calls"][0]["outcome"] == "rate_limit"
    assert detail["total_cost_usd"] == 0


def test_a_timed_out_run_says_so(client, factory, catalogue, settings):
    run_id = queued_run(client, factory)

    class Slow(PlaysProgram):
        def run_live(self, request, proxy):
            return LiveSandboxResult(None, "partial\n", "", timed_out=True)

    worker = Worker(settings, catalogue, ScriptedRunner(), live_runner=Slow(lambda p: []),
                    provider=FakeProvider())  # fmt: skip
    assert worker.run_live_once()
    detail = client.get(f"/api/live-runs/{run_id}").json()
    assert detail["outcome"] == "timed-out"
    assert "60 seconds" in detail["message"]
    assert detail["stdout"] == "partial\n"


def test_the_time_left_of_the_run_is_each_calls_timeout(client, factory, catalogue, settings):
    queued_run(client, factory)
    provider = FakeProvider()
    run_worker(settings, catalogue, lambda proxy: [proxy(a_call(), timeout_s=7.5)], provider)
    assert provider.timeouts == [7.5]


def test_a_run_a_dead_worker_held_is_errored_never_rerun(client, factory, catalogue, settings):
    run_id = queued_run(client, factory)
    with transaction(factory) as session:
        claimed = live_runs.claim_next(session, "w1")
        assert claimed is not None
        session.get(LiveRun, claimed.id).claimed_at = datetime.now(UTC) - timedelta(hours=1)
    # The calls it made before it died are in the result, with what they cost.
    proxy = live_runs.LiveProxy(claimed, factory, FakeProvider(), settings.live_config())
    proxy(a_call())
    proxy(a_call())
    with transaction(factory) as session:
        assert live_runs.error_stale(session, visibility_timeout=timedelta(minutes=5)) == 1
    detail = client.get(f"/api/live-runs/{run_id}").json()
    assert (detail["status"], detail["outcome"]) == ("errored", "errored")
    cost = (2_000 * 0.10 + 400 * 0.50) / 1e6
    assert [c["cost_usd"] for c in detail["calls"]] == pytest.approx([cost, cost])
    assert detail["calls"][0]["model"] == "claude-haiku-5-5"
    assert detail["total_cost_usd"] == pytest.approx(2 * cost)
    with transaction(factory) as session:
        assert live_runs.claim_next(session, "w2") is None


def test_a_run_queued_too_long_is_errored_so_the_learner_can_try_again(client, factory):
    me = sign_up(client)
    go_pro(factory)
    run_id = start(client, me).json()["id"]
    with transaction(factory) as session:
        session.get(LiveRun, run_id).created_at = datetime.now(UTC) - timedelta(minutes=9)
        assert live_runs.error_stale(session, visibility_timeout=timedelta(minutes=5)) == 0
    with transaction(factory) as session:
        session.get(LiveRun, run_id).created_at = datetime.now(UTC) - timedelta(minutes=11)
        assert live_runs.error_stale(session, visibility_timeout=timedelta(minutes=5)) == 1
    detail = client.get(f"/api/live-runs/{run_id}").json()
    assert (detail["status"], detail["outcome"]) == ("errored", "errored")
    assert "too busy" in detail["message"] and detail["total_cost_usd"] == 0
    assert start(client, me).status_code == 202


def test_without_a_live_runner_no_run_is_claimed(client, factory, catalogue, settings):
    queued_run(client, factory)
    worker = Worker(settings, catalogue, ScriptedRunner(), live_runner=None)
    assert worker.run_live_once() is False
    assert worker.run_next() is False
    with factory() as session:
        assert session.scalars(select(LiveRun)).one().status == "queued"


@pytest.mark.parametrize("oldest", ["live", "attempt"])
def test_the_worker_takes_the_oldest_job_of_either_kind(
    client, factory, catalogue, settings, oldest
):
    run_id = queued_run(client, factory)
    queued = client.post(
        "/api/exercises/starter.one/attempts",
        json={"files": FILES},
        headers={"x-csrf-token": client.get("/api/auth/me").json()["csrf_token"]},
    )
    assert queued.status_code in (200, 202), queued.text
    attempt_id = queued.json()["id"]
    long_ago = datetime.now(UTC) - timedelta(minutes=5)
    with transaction(factory) as session:
        row = session.get(LiveRun, run_id) if oldest == "live" else session.get(Attempt, attempt_id)
        row.created_at = long_ago
    worker = Worker(
        settings, catalogue, ScriptedRunner(), live_runner=PlaysProgram(lambda proxy: []),
        provider=FakeProvider(),
    )  # fmt: skip
    assert worker.run_next()
    with factory() as session:
        run_done = session.get(LiveRun, run_id).status != "queued"
        attempt_done = session.get(Attempt, attempt_id).status != "queued"
    assert (run_done, attempt_done) == (oldest == "live", oldest == "attempt")


# The time budget and the trial's allowance -------------------------------------------------------


def held_worker(factory, seconds: float, *, hours_ago: float = 1, status: str = "finished") -> None:
    finished = datetime.now(UTC) - timedelta(hours=hours_ago)
    with transaction(factory) as session:
        user = session.scalars(select(User)).one()
        session.add(
            LiveRun(
                user_id=user.id, exercise_id="starter.one", files={}, status=status,
                claimed_at=finished - timedelta(seconds=seconds), finished_at=finished,
            )
        )  # fmt: skip


def test_the_daily_live_time_budget_is_a_429_that_says_when_it_eases(make_client, factory):
    client = make_client(live_seconds_per_day=600)
    me = sign_up(client)
    go_pro(factory)
    held_worker(factory, 590)
    held_worker(factory, 5000, hours_ago=25)  # aged out
    started = start(client, me)
    assert started.status_code == 202, started.text
    with transaction(factory) as session:
        session.get(LiveRun, started.json()["id"]).status = "errored"
    held_worker(factory, 10, status="errored")  # a run that errored held the worker too
    refused = start(client, me)
    assert refused.status_code == 429
    problem = refused.json()
    assert (problem["code"], problem["scope"]) == ("live-cap", "time")
    assert "10 minutes of run time" in problem["detail"]
    assert datetime.fromisoformat(problem["resets_at"]) > datetime.now(UTC)
    # Checks are a budget of their own.
    attempt = client.post(
        "/api/exercises/starter.one/attempts", json={"files": FILES},
        headers={"x-csrf-token": me["csrf_token"]},
    )  # fmt: skip
    assert attempt.status_code in (200, 202), attempt.text


def trialing(factory, *, started: datetime, status: str = "trialing") -> None:
    go_pro(factory)
    with transaction(factory) as session:
        user = session.scalars(select(User)).one()
        session.add(
            Subscription(
                user_id=user.id, stripe_customer_id="cus_1", stripe_subscription_id="sub_1",
                status=status, interval="annual", started_at=started,
                trial_end=started + timedelta(days=7), trial_used=True,
            )
        )  # fmt: skip


def test_a_trial_has_its_own_allowance_for_the_whole_trial(make_client, factory):
    client = make_client(live_trial_usd=0.5)
    me = sign_up(client)
    now = datetime.now(UTC)
    trialing(factory, started=now - timedelta(days=2))
    spend(factory, "ada@example.com", 0.3, at=now - timedelta(days=1))
    spend(factory, "ada@example.com", 9.0, at=now - timedelta(days=3))  # before the trial
    allowed = client.get("/api/live/allowance").json()
    assert allowed["monthly_cap_usd"] == pytest.approx(0.5)
    assert allowed["spent_month_usd"] == pytest.approx(0.3)
    assert allowed["remaining_usd"] == pytest.approx(0.2)
    spend(factory, "ada@example.com", 0.2)
    refused = start(client, me)
    assert refused.status_code == 429
    problem = refused.json()
    assert (problem["code"], problem["scope"]) == ("live-cap", "trial")
    assert "trial's live-run allowance ($0.50)" in problem["detail"]
    assert datetime.fromisoformat(problem["resets_at"]) == (
        now - timedelta(days=2) + timedelta(days=7)
    )


def test_once_the_trial_converts_the_full_cap_applies(make_client, factory):
    client = make_client(live_trial_usd=0.5)
    sign_up(client)
    trialing(factory, started=datetime.now(UTC) - timedelta(days=8), status="active")
    assert client.get("/api/live/allowance").json()["monthly_cap_usd"] == pytest.approx(10.0)


def test_the_account_export_holds_live_runs_and_their_costs(client, factory, catalogue, settings):
    queued_run(client, factory)
    run_worker(settings, catalogue, lambda proxy: [proxy(a_call())], FakeProvider())
    data = client.get("/api/account/export").json()
    assert [r["exercise_id"] for r in data["live_runs"]] == ["starter.one"]
    assert data["live_calls"][0]["model"] == "claude-haiku-5-5"
    assert data["live_calls"][0]["cost_usd"] > 0


# Data protection --------------------------------------------------------------------------------


def test_the_first_run_waits_for_the_data_notice_to_be_acknowledged(client, factory):
    me = sign_up(client)
    go_pro(factory)
    notice = client.get("/api/live/notice").json()
    assert notice["acknowledged"] is False
    assert "Anthropic, PBC" in notice["text"] and "United States" in notice["text"]
    assert "30 days" in notice["text"] and "13 months" in notice["text"]
    assert "Nothing from a live run is used for grading" in notice["text"]
    refused = start(client, me, ack=False)
    assert refused.status_code == 409
    assert refused.json()["code"] == "live-notice-required"

    stale = client.post(
        "/api/live/notice", json={"version": "1999-01-01"},
        headers={"x-csrf-token": me["csrf_token"]},
    )  # fmt: skip
    assert stale.status_code == 422
    assert acknowledge(client, me).json()["acknowledged"] is True
    assert acknowledge(client, me).status_code == 200  # once per wording, idempotently
    assert client.get("/api/live/notice").json()["acknowledged"] is True
    assert start(client, me, ack=False).status_code == 202

    exported = client.get("/api/account/export").json()["live_notice_acknowledgements"]
    assert [a["version"] for a in exported] == [live_runs.LIVE_NOTICE_VERSION]
    assert exported[0]["acknowledged_at"]


def test_two_acknowledgements_racing_do_not_fail(client, factory, monkeypatch):
    me = sign_up(client)
    assert acknowledge(client, me).status_code == 200
    # The other tab's insert committed after this one's check would have looked.
    monkeypatch.setattr(live_runs, "notice_acknowledged", lambda *_: False)
    assert acknowledge(client, me).status_code == 200
    with factory() as session:
        assert len(session.scalars(select(LiveNoticeAcknowledgement)).all()) == 1


def test_acknowledging_the_notice_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr("lattice.api.routes.live.NOTICE_ACKNOWLEDGEMENTS_PER_HOUR", 1)
    me = sign_up(client)
    assert acknowledge(client, me).status_code == 200
    assert acknowledge(client, me).status_code == 429


def test_deleting_the_account_deletes_its_live_runs_usage_and_acknowledgements(
    client, factory, catalogue, settings
):
    me = sign_up(client)
    go_pro(factory)
    assert start(client, me).status_code == 202
    run_worker(settings, catalogue, lambda proxy: [proxy(a_call())], FakeProvider())
    deleted = client.post(
        "/api/account/delete", json={"password": "correct horse battery"},
        headers={"x-csrf-token": me["csrf_token"]},
    )  # fmt: skip
    assert deleted.status_code in (200, 204), deleted.text
    with factory() as session:
        assert session.scalars(select(LiveRun)).all() == []
        assert session.scalars(select(LiveCallRow)).all() == []
        assert session.scalars(select(LiveNoticeAcknowledgement)).all() == []


def test_runs_go_after_30_days_and_usage_after_13_months(client, factory):
    me = sign_up(client)
    go_pro(factory)
    run_id = start(client, me).json()["id"]
    now = datetime(2026, 11, 3, 4, 0, tzinfo=UTC)
    with transaction(factory) as session:
        run = session.get(LiveRun, run_id)
        run.status, run.created_at = "finished", now - timedelta(days=31)
    spend(factory, "ada@example.com", 0.1, at=datetime(2025, 10, 2, tzinfo=UTC))  # > 13 months
    spend(factory, "ada@example.com", 0.2, at=datetime(2025, 10, 4, tzinfo=UTC))  # < 13 months
    with transaction(factory) as session:
        live_runs.purge_expired(session, now - timedelta(days=2))  # day 29: nothing of the run
    with factory() as session:
        assert session.get(LiveRun, run_id) is not None
    with transaction(factory) as session:
        summary = live_runs.purge_expired(session, now)
    assert (summary.runs, summary.calls) == (1, 1)
    with factory() as session:
        assert session.get(LiveRun, run_id) is None
        assert [float(c.cost_usd) for c in session.scalars(select(LiveCallRow))] == [0.2]


def test_a_queued_or_running_run_is_never_purged(client, factory):
    me = sign_up(client)
    go_pro(factory)
    run_id = start(client, me).json()["id"]
    with transaction(factory) as session:
        session.get(LiveRun, run_id).created_at = datetime.now(UTC) - timedelta(days=90)
        assert live_runs.purge_expired(session).runs == 0
