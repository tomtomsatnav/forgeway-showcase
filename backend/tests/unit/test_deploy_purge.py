"""The daily purge the privacy policy relies on: `deploy/vps/purge.sh` and its systemd units.

The script runs against a stub `docker` that records its arguments, so nothing touches a real
stack.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

VPS = Path(__file__).parents[3] / "deploy" / "vps"
PURGE = VPS / "purge.sh"

needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")


def _run(tmp_path: Path, docker_exit: int) -> tuple[subprocess.CompletedProcess[str], str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls"
    stub = bin_dir / "docker"
    stub.write_text(f'#!/usr/bin/env bash\necho "$*" >> "{calls}"\nexit {docker_exit}\n')
    stub.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FORGEWAY_OPS_CONFIG": os.devnull,
        "FORGEWAY_DIR": str(tmp_path),
        "FORGEWAY_ENV_FILE": str(tmp_path / ".env.production"),
    }
    done = subprocess.run(
        ["bash", str(PURGE)], env=env, capture_output=True, text=True, check=False
    )
    return done, calls.read_text() if calls.exists() else ""


@needs_bash
def test_the_purge_runs_the_cli_in_the_api_container(tmp_path: Path) -> None:
    done, calls = _run(tmp_path, docker_exit=0)
    assert done.returncode == 0, done.stderr
    assert calls.count("\n") == 1
    assert "compose -p forgeway" in calls
    assert calls.rstrip().endswith("exec -T api forgeway accounts purge-unverified")


@needs_bash
def test_a_failed_purge_fails_the_unit(tmp_path: Path) -> None:
    done, _ = _run(tmp_path, docker_exit=1)
    assert done.returncode != 0


def _lines(name: str) -> list[str]:
    return [ln.strip() for ln in (VPS / "systemd" / name).read_text().splitlines()]


def test_the_purge_service_alerts_on_failure_like_the_other_units() -> None:
    service = _lines("forgeway-purge.service")
    assert "ExecStart=/srv/forgeway/deploy/vps/purge.sh" in service
    assert "OnFailure=forgeway-alert@%n.service" in service
    assert "Type=oneshot" in service
    assert "User=forgeway" in service


def test_the_purge_timer_runs_daily_and_catches_up() -> None:
    timer = _lines("forgeway-purge.timer")
    assert any(ln.startswith("OnCalendar=*-*-* ") for ln in timer)
    assert "Persistent=true" in timer
    assert "WantedBy=timers.target" in timer


def test_the_readme_installs_the_purge_timer() -> None:
    readme = (VPS / "README.md").read_text().replace("\\\n", " ")
    enable = next(ln for ln in readme.splitlines() if "systemctl enable --now" in ln)
    assert "forgeway-purge.timer" in enable
    assert "forgeway-backup.timer" in enable
