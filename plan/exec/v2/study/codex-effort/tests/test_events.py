"""Offline CLI events, read attribution, matched grader controls and interpretation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import grade
from events import PROJECT, WORKTREES, classify, inspect_stream
from grade import AGENT_PYTHON, Outcome
from run_trial import run_trial
from test_study import ITEMS, STANDIN, script


def execution(command: str, output: str = "", code: int = 0, **more: str) -> dict[str, Any]:
    return {
        "type": "command_execution",
        "command": command,
        "aggregated_output": output,
        "exit_code": code,
        **more,
    }


@pytest.mark.parametrize(
    ("item", "status", "denied"),
    [
        (execution("python -m pytest tests"), "clean", False),
        (execution("pwd", "Banner: " + str(PROJECT / "src/arci/report.py")), "clean", False),
        (execution("echo " + str(PROJECT)), "clean", False),
        (
            execution(f"rg -n '{PROJECT}' src", f"src/arci/report.py:13: example = '{PROJECT}'"),
            "clean",
            False,
        ),
        (execution("rg --files", "Banner: " + str(PROJECT)), "clean", False),
        (execution("rg -e pattern " + str(PROJECT)), "outside_read", False),
        (execution("rg --files " + str(PROJECT)), "outside_read", False),
        (execution("cat /private/tmp/another-project/README"), "outside_read", False),
        (
            {"type": "command_execution", "command": ["/bin/sh", "-lc", f"cat {PROJECT}/README"]},
            "outside_read",
            False,
        ),
        (
            {
                "type": "tool_call",
                "name": "exec_command",
                "arguments": {"cmd": "cat $ROOT/README", "env": {"ROOT": str(PROJECT)}},
            },
            "outside_read",
            False,
        ),
        (
            execution("rg --ignore-file " + str(PROJECT / ".ignore") + " pattern ."),
            "outside_read",
            False,
        ),
        (execution("ls " + str(AGENT_PYTHON.parent)), "clean", False),
        (execution("cat " + str(PROJECT / "README.md")), "outside_read", False),
        (execution("rg fix .", cwd=str(WORKTREES / "other")), "outside_read", False),
        (execution('cat "${REF}/answer.py"'), "outside_read", False),
        (execution("cat ~/Developer/AGENT-RELIABILITY-CI/README.md"), "outside_read", False),
        (execution("cat .git/objects/aa/123"), "outside_read", False),
        (execution("git show HEAD:src/arci/report.py"), "outside_read", False),
        (execution("git --git-dir=/tmp/db cat-file blob HEAD:x"), "outside_read", False),
        (execution("cat ../../sibling/work/readme"), "outside_read", False),
        (execution("ls ../../r01-a-candidate.transcript"), "outside_read", False),
        (
            {
                "type": "tool_call",
                "name": "read_file",
                "arguments": {"file_path": "../../grading/visible.log"},
            },
            "outside_read",
            False,
        ),
        (
            {
                "type": "tool_call",
                "name": "read_file",
                "arguments": {"file_path": "/tmp/other/site-packages/arci"},
            },
            "outside_read",
            False,
        ),
        (
            execution(
                "python inspect_it.py", '  File "/opt/dist-packages/arci/logs/cli.py", line 4'
            ),
            "outside_read",
            False,
        ),
        (execution("curl https://example.invalid/file"), "outside_read", False),
        ({"type": "web_search", "query": "fix"}, "outside_read", False),
        ({"type": "mcp_tool_call", "server": "outside", "tool": "search"}, "outside_read", False),
        ({"type": "tool_call", "name": "session_history", "arguments": {}}, "outside_read", False),
        (execution("cat ~/.codex/sessions/x"), "outside_read", False),
        (execution("cat " + str(PROJECT / "readme"), "cat: Permission denied", 1), "clean", True),
        (
            execution("cat " + str(PROJECT / "file") + "; cat xxx", "cat: Permission denied", 1),
            "outside_read",
            False,
        ),
    ],
)
def test_standin_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, item: dict[str, Any], status: str, denied: bool
) -> None:
    monkeypatch.setenv("CODEX_BIN", str(STANDIN))
    # Use a synthetic home. The stand-in only emits the command text.
    monkeypatch.setenv("HOME", "/Users/ajay")
    monkeypatch.setenv("REF", str(PROJECT))
    script(tmp_path, monkeypatch, ITEMS[:1], "empty")
    fixture = tmp_path / "standin.json"
    data = json.loads(fixture.read_bytes())
    data["events"] = [
        {"type": "item.completed", "item": {"id": "sample", "cwd": "$EXPORT", **item}}
    ]
    fixture.write_text(json.dumps(data))
    row = run_trial(ITEMS[0], "baseline", 1, 1, tmp_path / "private", tmp_path)
    assert row.audit.status == status and bool(row.audit.denied_events) == denied
    assert bool(row.audit.outside_events) == (status == "outside_read")
    assert row.audit.event_ids and row.audit.sha256
    assert row.outcome == "fail" and "empty diff" in row.grader_evidence


def test_symlink_started_denied_and_missing_stream(tmp_path: Path) -> None:
    tree = tmp_path / "export"
    tree.mkdir()
    (tree / "alias").symlink_to(PROJECT)
    log = tmp_path / "events"
    assert inspect_stream(log, tree, tmp_path, {}).audit.status == "unauditable"
    opened = {"type": "item.started", "item": {"id": "x", **execution("ls alias", cwd=str(tree))}}
    log.write_text(json.dumps(opened) + "\n")
    assert inspect_stream(log, tree, tmp_path, {}).audit.outside_events == ["L1/x"]
    closed = {
        "type": "item.completed",
        "item": {"id": "x", **execution("ls alias", "Permission denied", 1, cwd=str(tree))},
    }
    with log.open("a") as out:
        print(json.dumps(closed), file=out)
    a = inspect_stream(log, tree, tmp_path, {}).audit
    assert a.status == "clean" and a.denied_events == ["L2/x"]
    with log.open("a") as out:
        print("broken event", file=out)
    assert inspect_stream(log, tree, tmp_path, {}).audit.invalid_events == ["L3"]


def test_recovered_service_does_not_override_completed_turn(tmp_path: Path) -> None:
    log = tmp_path / "events"
    log.write_text(
        "\n".join(
            json.dumps(e)
            for e in (
                {"type": "turn.started"},
                {"type": "error", "message": "HTTP 503 Service unavailable"},
                {"type": "item.completed", "item": {"id": "x", **execution("pwd")}},
                {"type": "turn.completed", "usage": {}},
            )
        )
    )
    evidence = inspect_stream(log, tmp_path, tmp_path, {})
    assert classify(evidence, 0) == (None, None)
    assert classify(evidence, 1)[1] == "unattributed"
    log.write_text(
        '{"type":"error","message":"HTTP 503"}\n'
        '{"type":"turn.failed","error":{"message":"turn aborted"}}\n'
    )
    evidence = inspect_stream(log, tmp_path, tmp_path, {})
    assert classify(evidence, 1)[1] == "server" and evidence.service_id == "L1/L1"
    log.write_text(
        '{"type":"item.completed","item":{"type":"error","message":"HTTP 503"}}\n'
        '{"type":"turn.failed","error":{"source":"tool","message":"quota exceeded"}}\n'
    )
    assert classify(inspect_stream(log, tmp_path, tmp_path, {}), 1)[1] == "unattributed"


@pytest.mark.parametrize(
    ("rc", "body", "reason"),
    [
        (None, "", "timeout"),
        (2, "", "exit 2"),
        (3, "", "exit 3"),
        (4, "", "exit 4"),
        (5, "", "exit 5"),
        (-9, "", "exit -9"),
        (0, "", "missing"),
        (0, "<broken", "malformed"),
        (0, '<testsuite><testcase classname="x" name="wrong"/></testsuite>', "identities"),
        (
            0,
            '<testsuite><testcase classname="x" name="test"><skipped/></testcase></testsuite>',
            "incomplete",
        ),
    ],
)
def test_ambiguous_grader(tmp_path: Path, rc: int | None, body: str, reason: str) -> None:
    xml = tmp_path / "cases.xml"
    if body:
        xml.write_text(body)
    status, info = grade.classify_cases(xml, ["x.py::test"], 1, rc)
    assert status == "error" and reason in info


@pytest.mark.parametrize(
    ("control", "repeat", "expected"),
    [
        ("pass", "error", "fail"),
        ("error", "error", "error"),
        ("pass", "pass", "error"),
    ],
)
def test_matched_reference_control(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    control: Outcome,
    repeat: Outcome,
    expected: Outcome,
) -> None:
    ticket = ITEMS[0]
    tree = tmp_path / "submission"
    grade.export(ticket["pre_fix_commit"], tree)
    received: list[tuple[str, float]] = []

    def fake(
        tree: Path, nodes: list[str], n: int, work: Path, out: Path, label: str, seconds: float
    ) -> tuple[Outcome, str]:
        received.append((label, seconds))
        statuses: dict[str, Outcome] = {"visible-control": control, "visible-repeat": repeat}
        status = statuses.get(label, "error")
        return status, label + (": passed" if status == "pass" else ": test timeout")

    monkeypatch.setattr(grade, "test_nodes", fake)
    assert grade.checked_suite(ticket, tree, tmp_path, tmp_path, "visible", 2.5)[0] == expected
    assert received == [
        (label, 2.5)
        for label in (
            ["visible", "visible-control"] + (["visible-repeat"] if control == "pass" else [])
        )
    ]


@pytest.mark.skipif(
    os.environ.get("RUN5_CHECK_CONFINEMENT") != "1",
    reason="live preflight verifies OS confinement outside the nested sandbox",
)
def test_os_grader_cannot_change_tests_or_read_campaign(tmp_path: Path) -> None:
    assert grade.ISOLATE_GRADER
    result, sentinel = confinement_probe(tmp_path)
    assert result[0] == "pass", result
    assert sentinel.read_text() == "private"


def confinement_probe(tmp_path: Path) -> tuple[tuple[Outcome, str], Path]:
    tree = tmp_path / "export"
    tree.mkdir()
    (tree / "src").mkdir()
    sentinel = tmp_path / "campaign-proof"
    sentinel.write_text("private")
    test = tree / "test_boundary.py"
    test.write_text(
        "from pathlib import Path\nimport pytest\ndef test_boundary(tmp_path):\n"
        "    with pytest.raises(PermissionError): Path(__file__).write_text('changed')\n"
        f"    with pytest.raises(PermissionError): Path({str(sentinel)!r}).read_bytes()\n"
        f"    with pytest.raises(PermissionError): Path({str(sentinel)!r}).write_text('changed')\n"
        "    scratch = tmp_path / 'allowed'\n"
        "    scratch.write_text('written')\n"
        "    assert scratch.read_text() == 'written'\n"
    )
    result = grade.test_nodes(
        tree, ["test_boundary.py::test_boundary"], 1, tmp_path, tmp_path, "confinement"
    )
    return result, sentinel


def test_probe_detects_absent_confinement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(grade, "ISOLATE_GRADER", False)
    result, _ = confinement_probe(tmp_path)
    assert result == ("fail", "confinement: pytest exit 1")


def test_dependency_only_interpreter(tmp_path: Path) -> None:
    subprocess.run(
        [
            str(AGENT_PYTHON),
            "-I",
            "-B",
            "-c",
            "from importlib.util import find_spec; import hypothesis, pydantic, pytest, yaml; "
            "assert find_spec('arci') is None",
        ],
        cwd=tmp_path,
        check=True,
        timeout=30,
        env=dict(os.environ, GIT_TERMINAL_PROMPT="0"),
    )


def item_event(kind: str, **payload: Any) -> dict[str, Any]:
    return {"type": kind, "item": {"id": "sample", **payload}}


START = {"type": "turn.started"}
END = {"type": "turn.completed"}
COMMAND = item_event("item.completed", **execution("pwd"))
PLAN = item_event("item.started", type="todo_list", items=[{"text": "next", "completed": False}])
MESSAGE = item_event("item.completed", type="agent_message", text="Examined the fixture.")


@pytest.mark.parametrize(
    ("events", "exit_mode", "marker"),
    [
        (
            [START, COMMAND, {"type": "turn.failed", "error": {"message": "quota exceeded"}}, END],
            "zero",
            "quota",
        ),
        (
            [START, COMMAND, {"type": "turn.failed", "error": {"message": "stopped"}}, END],
            "zero",
            "unattributed",
        ),
        (
            [START, COMMAND, {"type": "turn.failed", "error": {"message": "agent crashed"}}, END],
            "nonzero",
            "unattributed",
        ),
        (
            [
                START,
                item_event(
                    "item.completed",
                    type="agent_message",
                    text="I can\u2019t comply with this request.",
                ),
                END,
            ],
            "zero",
            "unattributed",
        ),
        ([START, COMMAND, {"type": "error", "message": "HTTP 503"}, END], "zero", "server"),
        ([START, COMMAND, {"type": "turn.completed", "message": "HTTP 429"}], "zero", "rate"),
        (
            [
                START,
                {"type": "retry", "message": "reconnecting"},
                item_event(
                    "item.completed", type="agent_message", text="I cannot help with this request."
                ),
                END,
            ],
            "zero",
            "unattributed",
        ),
        ([START, COMMAND, {"type": "error", "message": "refused"}, END], "zero", "unattributed"),
        (
            [
                START,
                COMMAND,
                {"type": "refusal", "message": "request declined"},
                {"type": "turn.retrying"},
                END,
            ],
            "zero",
            "unattributed",
        ),
        ([START, COMMAND, {"type": "turn.completed", "refusal": "policy"}], "zero", "unattributed"),
        (
            [
                START,
                item_event(
                    "item.completed", type="agent_message", text="You've hit your usage limit."
                ),
                END,
            ],
            "zero",
            "unattributed",
        ),
        ([START, END], "zero", "unattributed"),
        ([COMMAND, START, END], "zero", "unattributed"),
        ([START, PLAN, END], "zero", "unattributed"),
        ([START, PLAN], "stall", "unattributed"),
        (
            [START, COMMAND, {**PLAN, "item": {**PLAN["item"], "id": "plan"}}],
            "stall",
            "unattributed",
        ),
        ([START], "signal", "unattributed"),
        ([START, COMMAND], "signal", "unattributed"),
        (
            [START, item_event("item.started", type="agent_message", text="Checking the file.")],
            "stall",
            "deadline",
        ),
        (
            [
                START,
                item_event(
                    "item.started",
                    type="file_change",
                    cwd="$EXPORT",
                    changes=[{"kind": "update", "path": "source.py"}],
                ),
            ],
            "stall",
            "deadline",
        ),
        ([START, MESSAGE, END], "zero", None),
    ],
)
def test_terminal_stream(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    events: list[dict[str, Any]],
    exit_mode: str,
    marker: str | None,
) -> None:
    import driver

    ticket = ITEMS[0]
    monkeypatch.setenv("CODEX_BIN", str(STANDIN))
    script(tmp_path, monkeypatch, [ticket], "stream")
    fixture = tmp_path / "standin.json"
    data = json.loads(fixture.read_bytes())
    data.update(
        events=events,
        rc=int(exit_mode == "nonzero"),
        signal=exit_mode == "signal",
        stall=exit_mode == "stall",
    )
    fixture.write_text(json.dumps(data))
    work = tmp_path / "private"
    arm = driver.arm_order([ticket["id"]], ticket["id"], 1)[0]
    row = run_trial(ticket, arm, 1, 1, work, tmp_path, seconds=0.6 if exit_mode == "stall" else 10)
    assert row.service_marker == marker
    assert row.outcome == ("fail" if marker in (None, "deadline") else "error")
    if marker is None:
        assert "empty diff" in row.grader_evidence
    if failed := next((i for i, e in enumerate(events, 1) if e["type"] == "turn.failed"), None):
        assert row.terminal_event_id.startswith(f"L{failed}/")
    driver.append_trial(tmp_path, row, 1)
    summary = driver.audit(tmp_path, 0, [ticket], work)
    assert summary["by_arm"][arm]["unattributed"] == int(marker == "unattributed")
    if marker == "unattributed":
        assert not summary["eligible"]


@pytest.mark.parametrize(
    "item",
    [
        {"type": "command_execution", "command": "pwd"},  # no item ID
        {"type": "command_execution", "id": 0, "command": "pwd"},
        {"type": "command_execution", "id": "  ", "command": "pwd"},
        {"type": "future_tool", "id": "x", "arguments": {"path": "file"}, "cwd": "$EXPORT"},
        {"type": "tool_call", "name": "future_tool", "id": "x", "arguments": {}},
        {"type": "command_execution", "id": "x"},
        {"type": "command_execution", "id": "x", "command": ["cat", {}]},
        {"type": "command_execution", "id": "x", "command": "cat README.md"},
        {"type": "command_execution", "id": "x", "command": "cat $PWD/README.md"},
        {"type": "command_execution", "id": "x", "command": "cd $EXPORT/missing && cat README"},
        {"type": "read_file", "id": "x", "path": "src/answer", "cwd": "$EXPORT/missing-cwd"},
        {
            "type": "command_execution",
            "id": "x",
            "workdir": "$UNKNOWN_DIRECTORY",
            "command": "ls .",
        },
        {"type": "read_file", "id": "x", "path": "file", "cwd": "relative"},
        {
            "type": "function_call",
            "name": "read_file",
            "id": "x",
            "arguments": '{"path":"src/file.py"}',
        },
        {"type": "read_file", "id": "x", "path": {}},
        {"type": "file_change", "id": "x", "changes": [{"kind": "update"}]},
    ],
)
def test_standin_incomplete_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, item: dict[str, Any]
) -> None:
    monkeypatch.setenv("CODEX_BIN", str(STANDIN))
    script(tmp_path, monkeypatch, ITEMS[:1], "empty")
    fixture = tmp_path / "standin.json"
    data = json.loads(fixture.read_bytes())
    data["events"] = [{"type": "item.completed", "id": "not-an-item-id", "item": item}]
    fixture.write_text(json.dumps(data))
    row = run_trial(ITEMS[0], "baseline", 1, 1, tmp_path / "private", tmp_path)
    assert row.audit.status == "unauditable" and len(row.audit.invalid_events) == 1
    assert row.outcome == "fail" and "empty diff" in row.grader_evidence
