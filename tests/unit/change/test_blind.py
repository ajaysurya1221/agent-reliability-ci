"""ADR 0019 acceptance tests. The only ARCI entry points are real CLI invocations."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict, cast

import pytest
import yaml

FAKE = Path(__file__).with_name("blind_fake.py").absolute()
REGISTRATION = ("rule.yaml", "rule.sha256", "plan.json")
ARMS = ("baseline", "candidate")


class Launch(TypedDict):
    arm: str
    number: int
    out: str
    args: list[str]
    files: dict[str, tuple[int, str]]


def template(*extra: str, executable: str = sys.executable) -> str:
    return shlex.join([executable, str(FAKE), "--junitxml={out}", *extra])


def read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_bytes()))


@dataclass
class Campaign:
    root: Path
    cli: subprocess.CompletedProcess[str]
    launches: list[Launch]

    @property
    def plan(self) -> dict[str, Any]:
        return read_json(self.root / "plan.json")

    def code(self, expected: int) -> None:
        assert self.cli.returncode == expected, (self.cli.stdout, self.cli.stderr)

    def sequence(self) -> list[tuple[int, str]]:
        return [(event["number"], event["arm"]) for event in self.launches]

    def scheduled(self, rounds: int) -> list[tuple[int, str]]:
        order = cast(list[list[str]], self.plan["arm_order"])
        return [(0, "baseline"), *((r, arm) for r in range(1, rounds + 1) for arm in order[r - 1])]

    def decision(self, number: int) -> dict[str, Any]:
        return read_json(self.root / f"round-{number:03}/decision.json")


def run(
    cwd: Path,
    *,
    case: str = "ties",
    tasks: int = 20,
    fmt: str = "junit",
    fault: str = "",
    rounds: int | None = 4,
    timeout: int = 9,
    plan_only: bool = False,
    baseline: str | None = None,
    candidate: str | None = None,
    target: str = "candidate",
) -> Campaign:
    (cwd / "settings.json").write_text(
        json.dumps(dict(case=case, tasks=tasks, fmt=fmt, fault=fault, target=target))
    )
    # Both templates carry a distinct literal so a mix-up is observable.
    args = [
        "--baseline",
        baseline if baseline is not None else template("old"),
        "--candidate",
        candidate if candidate is not None else template("new"),
        "--out-dir",
        "campaign with spaces",
        "--format",
        fmt,
        "--timeout-seconds",
        str(timeout),
    ]
    if rounds is not None:
        args.extend(["--max-rounds", str(rounds)])
    if plan_only:
        args.append("--plan-only")
    cli = subprocess.run(
        [sys.executable, "-m", "arci", "check-change", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=45,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    log = cwd / "launches.jsonl"
    events = (
        [cast(Launch, json.loads(line)) for line in log.read_text().splitlines()]
        if log.exists()
        else []
    )
    return Campaign(cwd / "campaign with spaces", cli, events)


def task_ids() -> set[str]:
    return {"suite::café au lait", *(f"suite::task-{index:02}" for index in range(1, 20))}


def assert_preserved(result: Campaign, files: dict[str, tuple[int, str]]) -> None:
    for name, (size, digest) in files.items():
        data = (result.root / name).read_bytes()
        if name == "verdict.txt":
            # The transcript grows. Verify its entire final text and every original byte.
            assert data.decode() == result.cli.stdout
            data = data[:size]
        assert hashlib.sha256(data).hexdigest() == digest, name


def assert_round_one_evidence(result: Campaign) -> None:
    for directory, arms in [("discovery", ("baseline",)), ("round-001", ARMS)]:
        for arm in arms:
            folder = result.root / directory
            assert (
                folder / f"{arm}.stdout"
            ).read_text().strip() == f"stdout {arm} {int(directory != 'discovery')}"
            assert (
                folder / f"{arm}.stderr"
            ).read_text().strip() == f"stderr {arm} {int(directory != 'discovery')}"
            assert (folder / f"{arm}.exit").read_text().strip() in ("0", "1")
    for event in result.launches:
        if event["number"] < 2:
            assert Path(event["out"]).stat().st_size > 0
    assert result.decision(1)["verdict"] == "INCONCLUSIVE"
    for path in REGISTRATION:
        assert (result.root / path).stat().st_size > 0


def assert_round_two_error(result: Campaign, arm: str) -> None:
    result.code(3)
    ordered = result.scheduled(2)
    assert result.sequence() == ordered[: ordered.index((2, arm)) + 1]
    assert_round_one_evidence(result)
    assert_preserved(result, result.launches[-1]["files"])
    assert not re.search(r"^VERDICT: (PASS|BLOCK|INCONCLUSIVE)", result.cli.stdout, re.M)


def test_blind_item_01_discovery_is_unscored(tmp_path: Path) -> None:
    """Task ids are opaque; spaces and non-ASCII letters survive registration and scoring."""
    result = run(tmp_path)
    result.code(0)
    assert result.sequence() == result.scheduled(4)
    rule = cast(dict[str, Any], yaml.safe_load((result.root / "rule.yaml").read_bytes()))
    assert set(rule["tasks"]) == task_ids()
    # Discovery fails everything. The first evaluated baseline and candidate both pass.
    first = result.decision(1)
    assert first["history"][0]["counts"] == dict(minus=0, zero=20, plus=0, errored=0)
    assert all(
        task["baseline_successes"] == task["candidate_successes"] == 1 for task in first["tasks"]
    )


def test_blind_item_02_complete_registration_before_launch(tmp_path: Path) -> None:
    result = run(tmp_path, case="loss")
    result.code(1)
    first = result.launches[1]
    assert first["number"] == 1
    assert set(REGISTRATION) <= first["files"].keys()
    assert_preserved(result, {name: first["files"][name] for name in REGISTRATION})
    plan = result.plan
    assert [
        plan[key]
        for key in ("baseline", "candidate", "format", "margin", "max_rounds", "timeout_seconds")
    ] == [
        template("old"),
        template("new"),
        "junit",
        "1/10",
        4,
        9,
    ]
    assert set(plan["tasks"]) == task_ids()
    assert len(plan["arm_order"]) == 4
    assert all(sorted(pair) == sorted(ARMS) for pair in plan["arm_order"])
    rule = cast(dict[str, Any], yaml.safe_load((result.root / "rule.yaml").read_bytes()))
    assert rule["fixed_before_runs"] is True and set(rule["tasks"]) == task_ids()
    digest = (result.root / "rule.sha256").read_text().strip()
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert result.decision(1)["rule_sha256"] == digest


def test_blind_item_03_registered_arm_order(tmp_path: Path) -> None:
    """The published interface exposes the schedule, but gives no independent arm_order vectors."""
    schedules: list[tuple[str, list[list[str]]]] = []
    for index in range(2):
        cwd = tmp_path / str(index)
        cwd.mkdir()
        result = run(cwd, case="two-losses")
        result.code(2)
        order = result.plan["arm_order"]
        assert len(order) == 4 and all(sorted(pair) == sorted(ARMS) for pair in order)
        assert result.sequence() == result.scheduled(4)
        for event in result.launches:
            assert event["args"] == (["old"] if event["arm"] == "baseline" else ["new"])
        schedules.append(((result.root / "rule.sha256").read_text(), order))
    assert schedules[0] == schedules[1]


def test_blind_item_04_arguments_and_relative_out_dir(tmp_path: Path) -> None:
    """contract silent on explicit relative directory resolution; resolve from the caller's cwd."""
    # Leave shell operators unquoted in the template so a shell would actually run touch.
    attack = template("argument with spaces", "copy={out}|{out}") + " ; touch SECOND $(touch SUB)"
    result = run(tmp_path, baseline=attack, plan_only=True)
    assert not (tmp_path / "SECOND").exists() and not (tmp_path / "SUB").exists()
    result.code(0)
    assert result.sequence() == [(0, "baseline")]
    event = result.launches[0]
    path = Path(event["out"])
    assert path.is_absolute() and path.parent == result.root / "discovery" and path.is_file()
    assert event["args"] == [
        "argument with spaces",
        f"copy={path}|{path}",
        ";",
        "touch",
        "SECOND",
        "$(touch",
        "SUB)",
    ]


@pytest.mark.parametrize("arm", ARMS)
def test_blind_item_04_missing_placeholder(tmp_path: Path, arm: str) -> None:
    """contract silent on validation timing; validate both templates before spending a launch."""
    overrides = {arm: template().replace("{out}", "unregistered.xml")}
    result = run(tmp_path, baseline=overrides.get("baseline"), candidate=overrides.get("candidate"))
    result.code(3)
    assert not result.launches


@pytest.mark.parametrize(("case", "code", "stop"), [("loss", 1, 1), ("ties", 0, 4)])
def test_blind_item_05_nothing_after_stop(tmp_path: Path, case: str, code: int, stop: int) -> None:
    result = run(tmp_path, case=case, rounds=7)
    result.code(code)
    assert result.sequence() == result.scheduled(stop)
    assert result.decision(stop)["stopped_at_round"] == stop


@pytest.mark.parametrize("fmt", ["junit", "csv", "jsonl"])
def test_blind_item_06_manual_verdict(tmp_path: Path, fmt: str) -> None:
    result = run(tmp_path, case="two-losses", fmt=fmt)
    result.code(2)
    files = {
        arm: [e["out"] for e in result.launches if e["arm"] == arm and e["number"] > 0]
        for arm in ARMS
    }
    manual = subprocess.run(
        [
            sys.executable,
            "-m",
            "arci",
            "verdict",
            str(result.root / "rule.yaml"),
            "--baseline",
            *files["baseline"],
            "--candidate",
            *files["candidate"],
            "--json",
            "manual.json",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert manual.returncode == result.cli.returncode, manual.stderr
    reference = read_json(tmp_path / "manual.json")
    decision = result.decision(4)
    for key in ("last_round_evaluated", "stopped_at_round", "history", "tasks"):
        assert decision[key] == reference[key], key
    assert manual.stdout.strip() in result.cli.stdout


def test_blind_item_07_all_losses_block(tmp_path: Path) -> None:
    result = run(tmp_path, case="loss")
    result.code(1)
    assert result.sequence() == result.scheduled(1)
    assert "VERDICT: BLOCK (exit 1)" in result.cli.stdout
    assert result.decision(1)["history"][0]["counts"] == dict(minus=20, zero=0, plus=0, errored=0)


def test_blind_item_08_two_losses_at_cap(tmp_path: Path) -> None:
    result = run(tmp_path, case="two-losses")
    result.code(2)
    assert result.sequence() == result.scheduled(4)
    assert "VERDICT: INCONCLUSIVE (exit 2)" in result.cli.stdout
    assert result.decision(4)["history"][-1]["counts"] == dict(minus=8, zero=72, plus=0, errored=0)


@pytest.mark.parametrize(("case", "passes"), [("ties", 80), ("both-fail", 0)])
def test_blind_item_09_identical_outcomes(tmp_path: Path, case: str, passes: int) -> None:
    result = run(tmp_path, case=case)
    result.code(0)
    report = result.cli.stdout.lower()
    assert "verdict: pass (exit 0)" in report
    assert re.search(r"identical|deterministic", report)
    assert re.search(
        rf"baseline\D{{1,20}}{passes}\b\D{{1,30}}candidate\D{{1,20}}{passes}\b", report
    )


@pytest.mark.parametrize(
    "fault",
    [
        "status",
        "signal",
        "timeout",
        "elsewhere",
        "empty",
        "invalid",
        "unreadable",
        "unknown",
        "duplicate",
    ],
)
def test_blind_item_10_structural_failure(tmp_path: Path, fault: str) -> None:
    result = run(tmp_path, fault=fault, timeout=1 if fault == "timeout" else 9)
    assert_round_two_error(result, "candidate")
    if fault == "elsewhere":
        assert (tmp_path / "misplaced.xml").stat().st_size > 0
        assert not Path(result.launches[-1]["out"]).exists()
    if fault == "timeout":
        assert not (tmp_path / "finished-sleep").exists()


@pytest.mark.parametrize("fault", ["unknown", "duplicate"])
def test_blind_item_10_invalid_first_arm_stops_immediately(tmp_path: Path, fault: str) -> None:
    result = run(tmp_path, fault=fault, target="first")
    assert_round_two_error(result, result.plan["arm_order"][1][0])


@pytest.mark.parametrize("fmt", ["csv", "jsonl"])
def test_blind_item_10_contradictory_round(tmp_path: Path, fmt: str) -> None:
    result = run(tmp_path, fmt=fmt, fault="label", target="first")
    assert_round_two_error(result, result.plan["arm_order"][1][0])


@pytest.mark.parametrize("fmt", ["csv", "jsonl"])
def test_blind_item_10_discovery_claims_round_two(tmp_path: Path, fmt: str) -> None:
    """contract silent on a discovery exemption; apply the round-label rule to launch zero."""
    result = run(tmp_path, fmt=fmt, fault="discovery-label", plan_only=True)
    result.code(3)
    assert result.sequence() == [(0, "baseline")]
    assert Path(result.launches[0]["out"]).stat().st_size > 0


@pytest.mark.parametrize("fmt", ["csv", "jsonl"])
def test_blind_item_01_discovery_label_from_environment(tmp_path: Path, fmt: str) -> None:
    """contract silent on encoding discovery as round 0 in a file; accept the assigned label."""
    result = run(tmp_path, fmt=fmt, fault="discovery-zero", plan_only=True)
    result.code(0)
    assert result.sequence() == [(0, "baseline")]
    assert set(result.plan["tasks"]) == {name.removeprefix("suite::") for name in task_ids()}


def test_blind_item_10_cannot_start(tmp_path: Path) -> None:
    # Remove this temporary interpreter alias after both round-one launches have run.
    alias = tmp_path / "candidate-python"
    alias.symlink_to(sys.executable)
    result = run(
        tmp_path,
        baseline=template(executable=str(alias)),
        candidate=template(executable=str(alias)),
        fault="cannot-start",
    )
    result.code(3)
    assert not alias.exists()
    assert result.sequence() == result.scheduled(1)
    assert_round_one_evidence(result)


@pytest.mark.parametrize(
    ("tasks", "fault"), [(0, ""), (20, "discovery-status")], ids=["no-tasks", "status-2"]
)
def test_blind_item_10_discovery_refused(tmp_path: Path, tasks: int, fault: str) -> None:
    result = run(tmp_path, tasks=tasks, fault=fault)
    result.code(3)
    assert result.sequence() == [(0, "baseline")]
    directory = result.root / "discovery"
    assert (directory / "baseline.stdout").is_file()
    assert (directory / "baseline.stderr").is_file()
    assert (directory / "baseline.exit").read_text().strip() == ("2" if fault else "0")
    assert Path(result.launches[0]["out"]).is_file()


@pytest.mark.parametrize("fault", ["one-error", "two-errors", "missing"])
def test_blind_item_11_error_tolerance(tmp_path: Path, fault: str) -> None:
    # 20 tasks x 4 rounds registers 80 pairs, so the tolerance is exactly one.
    result = run(tmp_path, fault=fault)
    if fault == "two-errors":
        result.code(3)
        assert result.sequence() == result.scheduled(2)
        assert_round_one_evidence(result)
        assert_preserved(result, result.launches[-1]["files"])
    else:
        result.code(2)
        assert result.sequence() == result.scheduled(4)
        assert result.decision(2)["history"][-1]["counts"] == dict(
            minus=0, zero=39, plus=0, errored=1
        )
        assert result.decision(4)["history"][-1]["counts"]["errored"] == 1


def test_blind_item_12_preexisting_result(tmp_path: Path) -> None:
    result = run(tmp_path, fault="preexisting")
    result.code(3)
    assert result.sequence() == result.scheduled(2)[:-1]
    assert_round_one_evidence(result)
    assert_preserved(result, result.launches[-1]["files"])
    arm = result.plan["arm_order"][1][1]
    assert (result.root / "round-002" / f"{arm}.xml").read_text() == "preexisting evidence"


def test_blind_item_12_repeated_junit_timestamp(tmp_path: Path) -> None:
    result = run(tmp_path, fault="timestamp")
    assert_round_two_error(result, "candidate")


def test_blind_item_13_plan_only(tmp_path: Path) -> None:
    result = run(tmp_path, rounds=None, plan_only=True)
    result.code(0)
    assert result.sequence() == [(0, "baseline")]
    assert all((result.root / name).stat().st_size for name in REGISTRATION)
    assert result.plan["max_rounds"] == 20 and len(result.plan["arm_order"]) == 20
    report = result.cli.stdout.lower()
    for pattern in (
        r"20 tasks",
        r"20 rounds",
        r"41 launches",
        r"pass[^\n]*\b1\b",
        r"block[^\n]*\b1\b",
        r"(?:tie[^\n]*\b4\b|\b4\b[^\n]*tie)",
        r"extremes",
        r"estimates",
    ):
        assert re.search(pattern, report), pattern


def test_blind_item_13_one_round_too_small(tmp_path: Path) -> None:
    result = run(tmp_path, rounds=1, tasks=3)
    result.code(3)
    assert result.sequence() == [(0, "baseline")]
    assert Path(result.launches[0]["out"]).stat().st_size > 0


def test_blind_item_14_existing_out_dir(tmp_path: Path) -> None:
    folder = tmp_path / "campaign with spaces"
    folder.mkdir()
    marker = folder / "keep"
    marker.write_bytes(b"already here")
    result = run(tmp_path)
    result.code(3)
    assert not result.launches
    assert list(folder.iterdir()) == [marker] and marker.read_bytes() == b"already here"


def test_blind_item_15_repeated_losses_named_and_counted(tmp_path: Path) -> None:
    result = run(tmp_path, case="two-losses")
    result.code(2)
    for name in ("suite::café au lait", "suite::task-01"):
        assert re.search(rf"{re.escape(name)}[^\n]*\b4\s+loss", result.cli.stdout, re.I)
