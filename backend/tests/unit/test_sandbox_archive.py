import io
import json
import tarfile

from lattice.domain.grading import SandboxRequest
from lattice.infrastructure.sandbox_docker import build_archive


def manifest(**overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "runtime": "python",
        "submission": {"a.py": ""},
        "tests": {"test_a.py": ""},
        "checks": {"c": "test_a.py::test_a"},
        "nonce": "n",
        "timeout_s": 5,
        "memory_mb": 128,
        **overrides,
    }
    archive = build_archive(SandboxRequest(**fields))  # type: ignore[arg-type]
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        member = tar.extractfile("manifest.json")
        assert member is not None
        return json.loads(member.read())


def test_in_process_grading_leaves_the_manifest_as_it_was():
    assert manifest() == {"checks": [{"id": "c", "test": "test_a.py::test_a"}]}


def test_process_isolation_reaches_the_harness_in_the_manifest():
    assert manifest(isolation="process")["isolation"] == "process"
