"""Worker heartbeats and the ops status probe the host's health check reads."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lattice.application import ops
from lattice.infrastructure.db.engine import transaction
from lattice.infrastructure.db.models import WorkerHeartbeat
from tests.integration.test_api import client, sign_up  # noqa: F401 - fixture
from tests.integration.test_learning_flow import CORRECT, run_worker_once

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def test_no_worker_and_an_empty_queue(factory):
    with factory() as session:
        current = ops.status(session, NOW)
    assert (current.worker_last_seen_at, current.worker_age_s) == (None, None)
    assert (current.queued, current.running, current.oldest_queued_age_s) == (0, 0, None)


def test_a_heartbeat_updates_one_row_per_worker_and_forgets_silent_ones(factory):
    with transaction(factory) as session:
        ops.record_heartbeat(session, "gone", NOW - timedelta(days=2))
        ops.record_heartbeat(session, "w1", NOW - timedelta(minutes=10))
    with transaction(factory) as session:
        ops.record_heartbeat(session, "w1", NOW - timedelta(seconds=30))
        ops.record_heartbeat(session, "w2", NOW - timedelta(minutes=7))
    with factory() as session:
        rows = {r.worker_id: r for r in session.query(WorkerHeartbeat)}
        current = ops.status(session, NOW)
    assert set(rows) == {"w1", "w2"}
    assert rows["w1"].started_at == NOW - timedelta(minutes=10)
    assert current.worker_age_s == 30.0
    assert current.workers_seen_last_5m == 1


def test_the_status_endpoint_reports_queue_depth_and_age(client):  # noqa: F811
    csrf = {"x-csrf-token": sign_up(client)["csrf_token"]}
    assert (
        client.post(
            "/api/exercises/starter.one/attempts", json={"files": CORRECT}, headers=csrf
        ).status_code
        == 202
    )

    body = client.get("/api/ops/status").json()
    assert body["worker"] == {"last_seen_at": None, "age_s": None, "seen_last_5m": 0}
    assert body["queue"]["queued"] == 1 and body["queue"]["running"] == 0
    assert body["queue"]["oldest_queued_age_s"] >= 0


def test_the_status_endpoint_sees_a_live_worker_and_a_drained_queue(client, factory, catalogue):  # noqa: F811
    csrf = {"x-csrf-token": sign_up(client)["csrf_token"]}
    client.post("/api/exercises/starter.one/attempts", json={"files": CORRECT}, headers=csrf)
    run_worker_once(factory, catalogue)
    with transaction(factory) as session:
        ops.record_heartbeat(session, "worker-test")

    body = client.get("/api/ops/status").json()
    assert body["worker"]["seen_last_5m"] == 1 and body["worker"]["age_s"] < 60
    assert body["queue"] == {"queued": 0, "running": 0, "oldest_queued_age_s": None}
