import json
import subprocess
import sys

from lattice_grader.project_research_reference import read_log, tap_argv, tool_calls

ECHO = (
    "import json, sys\n"
    "for line in sys.stdin:\n"
    "    message = json.loads(line)\n"
    "    print(json.dumps({'jsonrpc': '2.0', 'id': message.get('id'), 'result': {}}), flush=True)\n"
    "sys.exit(3)\n"
)


def test_tap_relays_both_ways_and_logs_every_line(tmp_path):
    log = tmp_path / "tap.log"
    argv = tap_argv(log, [sys.executable, "-c", ECHO])
    call = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "fetch", "arguments": {"id": "d-1"}, "_meta": {"k": "v"}},
    }
    ping = {"jsonrpc": "2.0", "id": "two", "method": "ping"}
    done = subprocess.run(
        argv,
        input=json.dumps(call) + "\n" + json.dumps(ping) + "\n",
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    replies = [json.loads(line) for line in done.stdout.splitlines()]
    assert [r["id"] for r in replies] == [1, "two"]
    assert done.returncode == 3  # the child's status
    entries = read_log(log)
    assert [e["dir"] for e in entries] == ["in", "in", "out", "out"] or [
        e["dir"] for e in entries
    ] == ["in", "out", "in", "out"]
    assert [e["message"] for e in entries if e["dir"] == "in"] == [call, ping]
    assert tool_calls(log) == [{"name": "fetch", "arguments": {"id": "d-1"}, "meta": {"k": "v"}}]


def test_reading_a_missing_or_odd_log(tmp_path):
    assert read_log(tmp_path / "absent.log") == []
    log = tmp_path / "odd.log"
    log.write_text(
        json.dumps({"dir": "in", "line": "not json"})
        + "\n"
        + json.dumps({"dir": "in", "line": "[1, 2]"})
        + "\n",
        encoding="utf-8",
    )
    assert [e["message"] for e in read_log(log)] == [None, None]
    assert tool_calls(log) == []


def test_usage_errors_exit_with_status_two(tmp_path):
    argv = tap_argv(tmp_path / "x.log", [])
    done = subprocess.run(argv, capture_output=True, text=True, timeout=20, check=False)
    assert done.returncode == 2
