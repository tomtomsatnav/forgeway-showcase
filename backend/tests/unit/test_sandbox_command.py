"""The `docker run` command the grader builds: hardening flags, and the optional OCI runtime."""

import re
from pathlib import Path

from lattice.domain.grading.model import SandboxRequest
from lattice.infrastructure.sandbox_docker import (
    DockerSandboxConfig,
    DockerSandboxRunner,
    container_name,
)

HAPROXY = Path(__file__).parents[3] / "deploy" / "vps" / "socket-proxy" / "haproxy.cfg"


def command(config: DockerSandboxConfig, memory_mb: int = 128) -> list[str]:
    request = SandboxRequest(
        runtime="python",
        submission={},
        tests={},
        checks={},
        nonce="n" * 32,
        timeout_s=5,
        memory_mb=memory_mb,
    )
    return DockerSandboxRunner(config)._command("box", "img:tag", request)


def test_the_default_runtime_adds_no_runtime_flag() -> None:
    argv = command(DockerSandboxConfig(images={"python": "img:tag"}))
    assert "--runtime" not in argv
    assert argv[-1] == "img:tag"
    assert {"--read-only", "no-new-privileges"} <= set(argv)
    assert argv[argv.index("--network") + 1] == "none"


def test_the_container_starts_as_root_with_only_the_capabilities_to_switch_user() -> None:
    argv = command(DockerSandboxConfig(images={"python": "img:tag"}))
    assert argv[argv.index("--user") + 1] == "0:0"
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    added = [argv[i + 1] for i, arg in enumerate(argv) if arg == "--cap-add"]
    assert added == ["SETUID", "SETGID", "KILL"]
    assert argv[argv.index("--security-opt") + 1] == "no-new-privileges"


def test_a_configured_runtime_comes_just_before_the_image() -> None:
    argv = command(DockerSandboxConfig(images={"python": "img:tag"}, oci_runtime="runsc"))
    assert argv[-3:] == ["--runtime", "runsc", "img:tag"]


def test_the_nonce_is_never_in_the_environment() -> None:
    argv = command(DockerSandboxConfig(images={"python": "img:tag"}))
    assert "--env" not in argv
    assert not any("n" * 32 in arg for arg in argv)


def test_memory_is_capped_whatever_the_exercise_declares() -> None:
    config = DockerSandboxConfig(images={"python": "img:tag"}, max_memory_mb=768)
    small = command(config, memory_mb=256)
    assert small[small.index("--memory") + 1] == "256m"
    big = command(config, memory_mb=4096)
    assert big[big.index("--memory") + 1] == "768m"
    assert big[big.index("--memory-swap") + 1] == "768m"


def test_the_default_ceiling_is_768_mb() -> None:
    assert DockerSandboxConfig(images={}).max_memory_mb == 768


def test_the_deadline_scales_the_exercise_limit_for_a_slower_runtime() -> None:
    request = SandboxRequest(
        runtime="python",
        submission={},
        tests={},
        checks={},
        nonce="n" * 32,
        timeout_s=20,
        memory_mb=128,
    )
    plain = DockerSandboxRunner(DockerSandboxConfig(images={"python": "img:tag"}))
    scaled = DockerSandboxRunner(
        DockerSandboxConfig(images={"python": "img:tag"}, timeout_factor=3.0)
    )
    assert plain.deadline_s(request) == 20 + 10.0
    assert scaled.deadline_s(request) == 60 + 10.0


def _acl(name: str) -> re.Pattern[str]:
    line = next(
        ln for ln in HAPROXY.read_text().splitlines() if ln.strip().startswith(f"acl {name} ")
    )
    return re.compile(line.split("'")[1].replace("\\\\", "\\"))


def test_the_socket_proxy_lets_the_worker_create_and_kill_its_own_containers_only() -> None:
    name = container_name()
    assert _acl("q_grade_name").match(f"name={name}")
    assert _acl("c_kill").match(f"/v1.54/containers/{name}/kill")
    assert not _acl("c_kill").match("/v1.54/containers/forgeway-api-1/kill")
    assert not _acl("c_kill").match(f"/v1.54/containers/{'a' * 64}/kill")
    # `docker run` attaches, starts and waits by the full id the create returned.
    assert _acl("c_run").match(f"/v1.54/containers/{'0123456789abcdef' * 4}/wait")
    assert not _acl("c_run").match("/v1.54/containers/0123456789ab/attach")
    assert not _acl("c_run").match("/v1.54/containers/forgeway-api-1/attach")
