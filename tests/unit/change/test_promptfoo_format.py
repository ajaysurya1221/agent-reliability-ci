"""ADR 0020 A7-A12 through the CLI, serving saved promptfoo exports offline."""

from __future__ import annotations

import hashlib
import io
import json
import shlex
import sys
from pathlib import Path
from typing import Any

import pytest

from arci import change
from arci.cli import main
from arci.hashing import hash_bytes
from arci.outcome_schema import OutcomeDecision
from tests.unit.change.test_cli import run as run_legacy
from tests.unit.integrations.test_promptfoo_reader import raw_rows

REAL = Path(__file__).resolve().parents[1] / "integrations/real/promptfoo"

# Overrides are prepared by the test. The child copies the selected file verbatim.
COPY = """\
import os, shutil, sys
from pathlib import Path
real, fixtures, out = map(Path, sys.argv[1:4])
arm = os.environ["ARCI_CHANGE_ARM"]
number = int(os.environ["ARCI_CHANGE_ROUND"])
print(os.environ["PROMPTFOO_FAILED_TEST_EXIT_CODE"])
with (fixtures / "launches").open("a") as log:
    print(number, arm, file=log)
assert out.suffix == ".json"
name = "discovery" if number == 0 else f"r{number}-{arm}"
source = fixtures / (name + ".json")
if not source.exists():
    source = real / f"e2e-{name}.json"
shutil.copyfile(source, out)
if number and sys.argv[4]:
    earlier = out.parent.parent / sys.argv[4]
    with earlier.open("ab") as stream:
        stream.write(b" ")
if not number and sys.argv[5] == "index":
    for n in ["099", "100", "101", "1000"]:
        folder = out.parent.parent / ("round-" + n)
        folder.mkdir()
        (folder / "marker").touch()
sys.exit(int(sys.argv[5]) if number and sys.argv[5].isdigit() else 100 if arm == "candidate" else 0)
"""


def campaign(work: Path, *args: str, tamper: str = "", status: str = "") -> int:
    command = shlex.join(
        [sys.executable, "-c", COPY, str(REAL), str(work), "{out}", tamper, status]
    )
    return main(
        [
            "check-change",
            "--format",
            "promptfoo",
            "--baseline",
            command,
            "--candidate",
            command,
            "--out-dir",
            str(work / "run"),
            *args,
        ]
    )


def document(name: str) -> dict[str, Any]:
    return json.loads((REAL / f"{name}.json").read_bytes())


def write_export(work: Path, name: str, doc: dict[str, Any]) -> None:
    (work / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")


def decision(path: Path) -> OutcomeDecision:
    result = OutcomeDecision.model_validate_json(path.read_bytes())
    assert result.validate_seal()
    return result


def launches(work: Path) -> list[str]:
    return (work / "launches").read_text().splitlines()


def test_a07_round_two_replay_with_predecessor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PROMPTFOO_FAILED_TEST_EXIT_CODE", "7")
    for number in (1, 2):
        for arm in ("baseline", "candidate"):
            source_arm = "candidate" if (number, arm) == (2, "candidate") else "baseline"
            doc = document(f"e2e-r1-{source_arm}")
            doc["evalId"] = f"{number}-{arm}"
            # Different arms may share a time; file position assigns the round.
            doc["results"]["timestamp"] = f"2026-11-28T12:00:0{number}Z"
            write_export(tmp_path, f"r{number}-{arm}", doc)
    assert campaign(tmp_path) == 1
    root = tmp_path / "run"
    prior = root / "round-001/decision.json"
    final = decision(root / "round-002/decision.json")
    assert final.previous_sha256 == decision(prior).record_sha256
    assert [look.counts.zero for look in final.history] == [20, 20]
    assert [look.counts.minus for look in final.history] == [0, 20]
    args = ["verdict", str(root / "rule.yaml")]
    for arm in ("baseline", "candidate"):
        paths = [root / f"round-{r:03}/{arm}.snapshot.jsonl" for r in (1, 2)]
        assert {i.path for i in final.inputs if i.arm == arm} == set(map(str, paths))
        args.extend([f"--{arm}", *map(str, paths)])
    for i in final.inputs:
        assert (
            i.format == "jsonl"
            and i.sha256 == hashlib.sha256(Path(i.path).read_bytes()).hexdigest()
        )
    for extra in ([], ["--previous", str(prior)]):
        target = tmp_path / ("replay-with-prior.json" if extra else "replay.json")
        assert main([*args, *extra, "--json", str(target)]) == final.exit_code == 1
        replay = decision(target)
        assert replay.tasks == final.tasks and replay.history == final.history
        assert replay.stopped_at_round == final.stopped_at_round == 2
        if extra:
            assert replay == final
    assert [p.read_text() for p in root.glob("*/*.stdout")] == ["100\n"] * 5


def test_a07_numeric_round_index(tmp_path: Path) -> None:
    assert campaign(tmp_path, "--plan-only", status="index") == 0
    lines = (tmp_path / "run/verdict.txt").read_text().splitlines()
    assert [s.strip() for s in lines if s.endswith("/marker")] == [
        f"round-{n}/marker" for n in ("099", "100", "101", "1000")
    ]


def test_a08_convert_reproduces_every_capture(tmp_path: Path) -> None:
    assert campaign(tmp_path) == 1
    root = tmp_path / "run"
    for folder, arm, real in (
        ("discovery", "baseline", "discovery"),
        ("round-001", "baseline", "r1-baseline"),
        ("round-001", "candidate", "r1-candidate"),
    ):
        original = root / folder / f"{arm}.json"
        raw = original.read_bytes()
        assert raw == (REAL / f"e2e-{real}.json").read_bytes()
        converted = tmp_path / f"{real}.jsonl"
        assert main(["convert", "--from", "promptfoo", str(original), "--out", str(converted)]) == 0
        snapshot = original.with_suffix(".snapshot.jsonl").read_bytes()
        assert converted.read_bytes() == snapshot
        rows = [json.loads(line) for line in snapshot.splitlines()]
        assert len(rows) == 20 and all("round" not in row for row in rows)
        assert {row["source_sha256"] for row in rows} == {hashlib.sha256(raw).hexdigest()}


@pytest.mark.parametrize("fmt", ["junit", "csv", "jsonl", "promptfoo"])
def test_a09_plan_keys(tmp_path: Path, fmt: str) -> None:
    root = tmp_path / "run"
    keys = {
        "baseline",
        "candidate",
        "format",
        "margin",
        "max_rounds",
        "timeout_seconds",
        "tasks",
        "rule_sha256",
        "arm_order",
    }
    if fmt == "promptfoo":
        assert campaign(tmp_path, "--plan-only") == 0
    else:
        assert run_legacy(root, "pass", "pass", "--plan-only", fmt=fmt) == 0
    plan = json.loads((root / "plan.json").read_bytes())
    assert plan["format"] == fmt
    if fmt == "promptfoo":
        assert plan.pop("reader") == "promptfoo/1"
        assert plan.pop("scored_format") == "jsonl"
        assert plan.pop("tool_version") == "0.126.0"
    assert set(plan) == keys


@pytest.mark.parametrize("suffix", ["json", "snapshot.jsonl"])
def test_a10_changed_discovery_stops_before_next_launch(tmp_path: Path, suffix: str) -> None:
    file = f"discovery/baseline.{suffix}"
    assert campaign(tmp_path, tamper=file) == 3
    root = tmp_path / "run"
    assert len(launches(tmp_path)) == 2
    assert (root / file).read_bytes().endswith(b" ")
    assert f"results changed: {root / file}" in (root / "verdict.txt").read_text()
    assert not (root / "round-001/decision.json").exists()


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("reused-id", "repeated promptfoo evalId"),
        ("same-instant", "repeated promptfoo timestamp"),
        ("words-baseline", "repeats"),
        ("cache-warm", "cache use reported"),
        ("two-prompts", "multiple cells"),
        ("changed-version", "tool version differs"),
        ("shapes", "duplicate task id"),
        ("cache-cold", "--no-cache"),
        ("null-cache", "--no-cache"),
        ("absent-cache", "--no-cache"),
        ("empty-id", "evalId"),
        ("absent-id", "evalId"),
        ("empty-time", "results.timestamp"),
        ("absent-time", "results.timestamp"),
        ("empty-version", "tool version"),
        ("absent-version", "tool version"),
        ("http-500", "HTTP error range"),
        ("http-500.0", "HTTP error range"),
        ("exit-1", "exit 1"),
    ],
)
def test_a10_refusal_keeps_evidence_and_stops(tmp_path: Path, case: str, reason: str) -> None:
    # Target the candidate to test cross-arm run-id reuse, the baseline for same-side time.
    arm = "candidate" if case == "reused-id" else "baseline"
    fixture = REAL / f"{case}.json"
    if fixture.is_file():
        raw = fixture.read_bytes()
    else:
        doc = document(f"e2e-r1-{arm}")
        first = document("e2e-discovery")
        if case == "reused-id":
            doc["evalId"] = first["evalId"]
        elif case == "same-instant":
            doc["results"]["timestamp"] = first["results"]["timestamp"].replace("Z", "00+00:00")
        elif case == "changed-version":
            doc["metadata"]["promptfooVersion"] = "0.125.1"
        elif case.startswith("http-"):
            status = json.loads(case.removeprefix("http-"))
            doc["results"]["results"][0]["response"].setdefault("metadata", {})["http"] = {
                "status": status
            }
        elif case != "exit-1":
            action, key = case.split("-")
            container, field = {
                "cache": (doc["runtimeOptions"], "cache"),
                "id": (doc, "evalId"),
                "time": (doc["results"], "timestamp"),
                "version": (doc["metadata"], "promptfooVersion"),
            }[key]
            if action == "absent":
                del container[field]
            else:
                container[field] = None if action == "null" else ""
        raw = json.dumps(doc).encode()
    (tmp_path / f"r1-{arm}.json").write_bytes(raw)
    # An unexpected status ends whichever evaluated launch runs first.
    assert campaign(tmp_path, status="1" if case == "exit-1" else "") == 3
    root = tmp_path / "run"
    arms = json.loads((root / "plan.json").read_bytes())["arm_order"][0]
    if case == "exit-1":
        arm = arms[0]
    assert launches(tmp_path) == ["0 baseline", *[f"1 {a}" for a in arms[: arms.index(arm) + 1]]]
    assert (root / "discovery/baseline.snapshot.jsonl").is_file()
    assert (root / f"round-001/{arm}.json").is_file()
    assert not (root / "round-001/decision.json").exists()
    assert reason in (root / "verdict.txt").read_text()


def test_a11_real_exports_block_and_accept_100(tmp_path: Path) -> None:
    assert campaign(tmp_path) == 1
    root = tmp_path / "run"
    result = decision(root / "round-001/decision.json")
    assert result.verdict == "BLOCK" and result.stopped_at_round == 1
    assert result.history[0].counts.minus == 20
    assert (root / "round-001/candidate.exit").read_text() == "100\n"
    report = (root / "verdict.txt").read_text()
    assert "round-001/candidate: test failure (exit 100)" in report
    assert (
        "Results from promptfoo 0.126.0, read by promptfoo/1. To check one: "
        "arci convert --from promptfoo round-001/baseline.json --out check.jsonl"
        in report.splitlines()
    )
    assert "was not tested" not in report
    assert len(launches(tmp_path)) == 3


def test_a11_same_export_twice(tmp_path: Path) -> None:
    for arm in ("baseline", "candidate"):
        (tmp_path / f"r1-{arm}.json").write_bytes((REAL / "e2e-discovery.json").read_bytes())
    assert campaign(tmp_path) == 3
    assert len(launches(tmp_path)) == 2
    assert "repeated promptfoo evalId" in (tmp_path / "run/verdict.txt").read_text()


def test_a11_untested_version_notice_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("discovery", "r1-baseline", "r1-candidate"):
        doc = document("e2e-" + name)
        doc["metadata"]["promptfooVersion"] = "other\né"
        write_export(tmp_path, name, doc)
    notice = r"Notice: promptfoo/1 was not tested with promptfoo version other\x0a"
    with io.TextIOWrapper(io.BytesIO(), encoding="ascii") as stdout, monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", stdout)
        assert campaign(tmp_path) == 1
        stdout.seek(0)
        assert stdout.read().splitlines().count(notice + r"\xe9.") == 1
    lines = (tmp_path / "run/verdict.txt").read_text().splitlines()
    assert lines.count(notice + "é.") == 1


@pytest.mark.parametrize("fmt", ["junit", "csv", "jsonl"])
def test_a12_legacy_launch_environment_and_exit_100(
    fmt: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PROMPTFOO_FAILED_TEST_EXIT_CODE", "17")
    script = 'import os, sys; print(os.environ["PROMPTFOO_FAILED_TEST_EXIT_CODE"]); sys.exit(100)'
    cmd = shlex.join([sys.executable, "-c", script, "{out}"])
    root = tmp_path / "run"
    assert (
        main(
            [
                "check-change",
                "--format",
                fmt,
                "--baseline",
                cmd,
                "--candidate",
                cmd,
                "--out-dir",
                str(root),
            ]
        )
        == 3
    )
    assert (root / "discovery/baseline.stdout").read_text() == "17\n"
    assert (root / "discovery/baseline.exit").read_text() == "100\n"
    assert "unexpected exit 100" in (root / "verdict.txt").read_text()


def test_discovery_and_counts_use_verified_snapshot_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_path = Path.open

    def reopen(path: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        # Capture verification uses its own file descriptor. Give path-based
        # parser rereads different rows without changing the evidence on disk.
        if path.name.endswith(".snapshot.jsonl") and mode in {"r", "rb"}:
            with open_path(path, "rb") as stream:
                raw = stream.read()
            if path.parent.name == "discovery":
                raw += b'{"task_id":"unexpected","outcome":"pass"}\n'
            elif mode == "r":
                raw = raw.replace(b'"outcome":"pass"', b'"outcome":"fail"')
            return io.BytesIO(raw) if mode == "rb" else io.StringIO(raw.decode())
        return open_path(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", reopen)
    assert campaign(tmp_path) == 1
    root = tmp_path / "run"
    expected = sorted(task for _, task, _ in raw_rows(document("e2e-discovery")))
    assert json.loads((root / "plan.json").read_bytes())["tasks"] == expected
    assert (
        "Old version passed 20 of 20 task runs. New version passed 0 of 20."
        in (root / "verdict.txt").read_text()
    )


def test_wrong_returned_promptfoo_digest_with_intact_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    decide = change.decide_outcomes
    root = tmp_path / "run"
    folder = root / "round-001"
    scored: dict[str, str] = {}

    def wrong_digest(*args: Any, **kwargs: Any) -> OutcomeDecision:
        actual = decide(*args, **kwargs)
        first, *rest = actual.inputs
        scored.update((item.path, item.sha256) for item in actual.inputs)
        incorrect = first.model_copy(update={"sha256": "0" * 64})
        altered = OutcomeDecision.create(
            **actual.model_dump(exclude={"inputs", "record_sha256"}), inputs=(incorrect, *rest)
        )
        assert altered.validate_seal()
        return altered

    monkeypatch.setattr(change, "decide_outcomes", wrong_digest)
    assert campaign(tmp_path) == 3
    for arm in ("baseline", "candidate"):
        assert (folder / f"{arm}.json").read_bytes() == (REAL / f"e2e-r1-{arm}.json").read_bytes()
        path = folder / f"{arm}.snapshot.jsonl"
        assert hash_bytes(path.read_bytes()) == scored[str(path)]
    assert "scored bytes differ" in (root / "verdict.txt").read_text()
    assert not (folder / "decision.json").exists()
