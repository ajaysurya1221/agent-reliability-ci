"""ADR 0019, including the evidence left by each real child process."""

from __future__ import annotations

import json
import os
import select
import shlex
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from contextlib import ExitStack
from pathlib import Path
from types import FrameType
from typing import Any

import pytest

from arci import change
from arci.cli import main
from arci.outcome_report import render_terminal
from arci.outcome_schema import OutcomeDecision, OutcomeRule
from arci.outcomes import load_rule, rule_sha256
from arci.suite_schedule import Arm, arm_order

SCRIPT = Path(__file__).with_name("fake_command.py").resolve()


def command(mode: str, n: int = 20, *extra: str) -> str:
    return shlex.join([sys.executable, str(SCRIPT), mode, str(n), "--junitxml={out}", *extra])


def run(
    root: Path, a: str = "pass", b: str = "pass", *extra: str, fmt: str = "csv", n: int = 20
) -> int:
    return main(
        [
            "check-change",
            "--baseline",
            command(a, n),
            "--candidate",
            command(b, n),
            "--out-dir",
            str(root),
            "--format",
            fmt,
            *extra,
        ]
    )


def calls(root: Path) -> list[list[str | int]]:
    return [json.loads(line) for line in (root.parent / "calls.jsonl").read_text().splitlines()]


def look(root: Path, r: int) -> OutcomeDecision:
    decision = OutcomeDecision.model_validate_json(
        (root / f"round-{r:03}/decision.json").read_bytes()
    )
    assert decision.validate_seal()
    return decision


def test_item_01_discovery_excluded_and_supplies_inventory(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert run(root) == 0
    assert calls(root).count([0, "baseline"]) == 1
    decision = look(root, 4)
    assert decision.rule is not None
    assert set(decision.rule.tasks) == {f"task-{n}" for n in range(20)}
    assert all(t.baseline_successes == t.candidate_successes == 4 for t in decision.tasks)
    assert (root / "discovery/baseline.exit").read_text() == "1\n"
    assert all(Path(i.path).parent.name != "discovery" for i in decision.inputs)


def test_item_02_registration_complete_before_evaluation(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert run(root, "snapshot", "snapshot") == 0
    assert json.loads((root / "discovery/baseline.stdout").read_text()) == {}
    rule = load_rule(root / "rule.yaml")
    digest = rule_sha256(rule)
    assert rule.fixed_before_runs
    order = [list(arm_order(digest, 0, r)) for r in range(1, 21)]
    for arm in ("baseline", "candidate"):
        snapshot = json.loads((root / f"round-001/{arm}.stdout").read_text())
        assert snapshot == {
            k: (root / k).read_text() for k in ("rule.yaml", "rule.sha256", "plan.json")
        }
        assert snapshot["rule.sha256"].strip() == digest
        assert json.loads(snapshot["plan.json"]) == {
            "baseline": command("snapshot"),
            "candidate": command("snapshot"),
            "format": "csv",
            "margin": "1/10",
            "max_rounds": 20,
            "timeout_seconds": 600,
            "tasks": list(rule.tasks),
            "rule_sha256": digest,
            "arm_order": order,
        }


def test_item_03_every_pair_in_registered_order(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert run(root, "lose2", "lose2", "--max-rounds", "5") == 2
    plan = json.loads((root / "plan.json").read_text())
    expected = [list(arm_order(plan["rule_sha256"], 0, r)) for r in range(1, 6)]
    assert plan["arm_order"] == expected
    assert calls(root)[1:] == [[r, arm] for r, arms in enumerate(expected, 1) for arm in arms]
    for r in range(2, 6):
        assert look(root, r).previous_sha256 == look(root, r - 1).record_sha256


def test_item_04_placeholder_spaces_no_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "results with spaces"
    # Leave shell metacharacters unquoted in the template.
    cmd = command("pass") + " ; touch UNEXPECTED $(touch SECOND) {out}"
    assert (
        main(
            [
                "check-change",
                "--baseline",
                cmd,
                "--candidate",
                cmd,
                "--out-dir",
                str(root),
                "--plan-only",
            ]
        )
        == 0
    )
    path = str(root / "discovery/baseline.xml")
    assert json.loads((root / "discovery/baseline.stdout").read_text()) == [
        str(Path.cwd()),
        path,
        ";",
        "touch",
        "UNEXPECTED",
        "$(touch",
        "SECOND)",
        path,
    ]
    assert not (tmp_path / "UNEXPECTED").exists() and not (tmp_path / "SECOND").exists()


def test_item_05_no_launch_after_decisive_round(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert run(root) == 0
    assert look(root, 4).stopped_at_round == 4
    assert len(calls(root)) == 9
    assert not (root / "round-005").exists()


@pytest.mark.parametrize(("fmt", "suffix"), [("csv", "csv"), ("jsonl", "jsonl"), ("junit", "xml")])
def test_item_06_manual_verdict_matches(tmp_path: Path, fmt: str, suffix: str) -> None:
    root = tmp_path / "run"
    code = run(root, "lose2", "lose2", "--max-rounds", "4", fmt=fmt)
    target = tmp_path / "manual.json"
    assert (
        main(
            [
                "verdict",
                str(root / "rule.yaml"),
                "--baseline",
                *map(str, sorted(root.glob(f"round-*/baseline.snapshot.{suffix}"))),
                "--candidate",
                *map(str, sorted(root.glob(f"round-*/candidate.snapshot.{suffix}"))),
                "--json",
                str(target),
            ]
        )
        == code
        == 2
    )
    manual = OutcomeDecision.model_validate_json(target.read_bytes())
    final = look(root, 4)
    assert manual.tasks == final.tasks and manual.history == final.history
    assert manual.stopped_at_round == final.stopped_at_round == 4
    assert render_terminal(manual) in (root / "verdict.txt").read_text()
    assert final == change.decide_outcomes(
        root / "rule.yaml",
        sorted(root.glob(f"round-*/baseline.snapshot.{suffix}")),
        sorted(root.glob(f"round-*/candidate.snapshot.{suffix}")),
        previous=root / "round-003/decision.json",
    )


def test_item_07_all_losses_block(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert run(root, "pass", "fail") == 1
    assert look(root, 1).history[-1].counts.minus == 20
    assert len(calls(root)) == 3


def test_item_08_two_losses_inconclusive_at_cap(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert run(root, "pass", "lose2") == 2
    final = look(root, 20)
    assert final.history[-1].counts.minus == 40
    assert final.stopped_at_round == final.rounds_registered == 20


@pytest.mark.parametrize(("mode", "passes"), [("pass", 80), ("fail", 0)])
def test_item_09_all_ties_warn_and_show_absolute_passes(
    tmp_path: Path, mode: str, passes: int, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "run"
    assert run(root, mode, mode) == 0
    report = (root / "verdict.txt").read_text()
    assert report == capsys.readouterr().out
    assert "Warning: identical outcomes" in report
    assert f"Absolute passes: baseline {passes}, candidate {passes}." in report
    for file in root.rglob("*"):
        if file.is_file():
            assert f"  {file.relative_to(root)}\n" in report


@pytest.mark.parametrize(
    ("mode", "reason"),
    [
        ("timeout", "timeout"),
        ("signal", "exit -"),
        ("exit7", "exit 7"),
        ("missing", "missing"),
        ("empty", "invalid header"),
        ("unreadable", "decode"),
        ("duplicate", "duplicate outcome"),
        ("unknown", "unknown task id"),
        ("badround", "contradicts"),
        ("preexisting", "existed before launch"),
        ("timestamp", "repeated JUnit timestamp"),
    ],
)
def test_item_10_structural_error_stops_immediately(tmp_path: Path, mode: str, reason: str) -> None:
    root = tmp_path / "run"
    options = ["--timeout-seconds", "0.6"] if mode == "timeout" else []
    assert run(root, mode, mode, *options, fmt="junit" if mode == "timestamp" else "csv") == 3
    assert len(calls(root)) == 4 and calls(root)[-1][0] == 2
    assert look(root, 1).exit_code == 2 and not (root / "round-002/decision.json").exists()
    report = (root / "verdict.txt").read_text()
    assert "VERDICT: ERROR (exit 3)" in report and reason in report
    assert "VERDICT: INCONCLUSIVE" not in report
    assert (root / "discovery/baseline.stdout").is_file()
    assert len(list((root / "round-002").glob("*.exit"))) == 1


def test_item_10_program_cannot_start(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert (
        main(
            [
                "check-change",
                "--baseline",
                command("pass"),
                "--candidate",
                f"{tmp_path}/absent {{out}}",
                "--out-dir",
                str(root),
            ]
        )
        == 3
    )
    assert (root / "round-001/candidate.exit").read_text() == "could not start\n"
    assert (root / "rule.yaml").is_file() and not (root / "round-002").exists()


@pytest.mark.parametrize(("errors", "code"), [(1, 2), (2, 3)])
def test_item_11_error_tolerance(tmp_path: Path, errors: int, code: int) -> None:
    root = tmp_path / "run"
    assert run(root, "pass", f"errors{errors}", "--max-rounds", "4") == code
    d = look(root, 1)
    assert d.rule and d.rule.max_errored_pairs == 1
    assert d.history[-1].counts.errored == errors and d.exit_code == code


@pytest.mark.parametrize("mode", ["preexisting", "timestamp"])
def test_item_12_visible_reuse_refused(tmp_path: Path, mode: str) -> None:
    root = tmp_path / "run"
    assert run(root, mode, mode, fmt="junit") == 3
    assert len(calls(root)) == 4
    if mode == "preexisting":
        assert any(p.read_text() == "already here" for p in root.glob("round-002/*.xml"))


def test_item_13_plan_only_and_unique_default_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    for _ in range(2):
        assert (
            main(
                [
                    "check-change",
                    "--baseline",
                    command("pass"),
                    "--candidate",
                    command("fail"),
                    "--plan-only",
                ]
            )
            == 0
        )
    roots = [p for p in (tmp_path / "arci-changes").iterdir() if p.is_dir()]
    assert len(roots) == 2 and calls(roots[0]) == [[0, "baseline"], [0, "baseline"]]
    for root in roots:
        assert not list(root.glob("round-*"))
        assert all((root / k).is_file() for k in ["rule.yaml", "rule.sha256", "plan.json"])
    text = capsys.readouterr().out
    assert "20 tasks, 20 rounds, at most 41 launches" in text
    assert "PASS with all ties: round 4" in text and "extremes, not estimates" in text


def test_item_13_tight_margin_raises_default_cap(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert run(root, "pass", "pass", "--plan-only", "--margin", "1/100") == 0
    rule = load_rule(root / "rule.yaml")
    cap = rule.max_rounds
    assert cap > 20
    assert (
        run(
            tmp_path / "short",
            "pass",
            "pass",
            "--plan-only",
            "--margin",
            "1/100",
            "--max-rounds",
            str(cap - 1),
        )
        == 3
    )


def test_item_14_existing_dir_refused_before_discovery(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    assert run(root) == 3
    assert not list(root.iterdir()) and not (tmp_path / "calls.jsonl").exists()


def test_item_15_repeated_losses_named_with_counts(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert run(root, "pass", "lose2", "--max-rounds", "4") == 2
    text = (root / "verdict.txt").read_text()
    assert "  task-0: 4 losses\n" in text and "  task-1: 4 losses\n" in text
    assert "  task-2:" not in text


def test_item_15_pass_still_lists_every_repeated_loss_beyond_terminal_table(tmp_path: Path) -> None:
    root = tmp_path / "run"
    # With 11 persistent losses over 150 tasks the default cap is too short for PASS.
    assert run(root, "pass", "lose11", "--max-rounds", "30", n=150) == 0
    report = (root / "verdict.txt").read_text()
    r = len(list(root.glob("round-*")))
    assert r >= 2 and look(root, r).history[-1].counts.minus == 11 * r
    for i in range(11):
        assert f"  task-{i}: {r} losses\n" in report


@pytest.mark.parametrize("mode", ["linked-result", "linked-directory", "fifo"])
def test_item_19_regular_file_and_real_directory_required(tmp_path: Path, mode: str) -> None:
    root = tmp_path / "run"
    (tmp_path / "fixture.csv").write_text("task_id,outcome\ntask-0,pass\n")
    assert run(root, mode, mode) == 3
    assert len(calls(root)) == (2 if mode == "linked-directory" else 1)
    assert "VERDICT: ERROR (exit 3)" in (root / "verdict.txt").read_text()


@pytest.mark.parametrize(
    ("mode", "code"),
    [("tree-error", 3), ("tree-timeout", 3), ("tree-signal", 3), ("tree-success", 0)],
)
def test_item_20_group_stopped_before_return(tmp_path: Path, mode: str, code: int) -> None:
    root = tmp_path / "run"
    assert run(root, mode, mode, "--plan-only", "--timeout-seconds", "1") == code
    pids = (tmp_path / "worker.pid").read_text().split()
    for pid in pids:
        assert_stopped(int(pid))


def test_item_20_large_output_is_captured(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert run(root, "verbose", "verbose", "--plan-only", "--timeout-seconds", "5") == 0
    for name in ("stdout", "stderr"):
        assert (root / f"discovery/baseline.{name}").read_bytes().count(b"x") >= 3 * 1024 * 1024


@pytest.mark.parametrize("action", ["delete", "change"])
@pytest.mark.parametrize("name", ["plan.json", "rule.yaml", "rule.sha256"])
def test_item_21_registration_checked_after_each_launch(
    tmp_path: Path, name: str, action: str
) -> None:
    root = tmp_path / "run"
    mode = f"registration-{action}-{name}"
    assert run(root, mode, mode) == 3
    assert len(calls(root)) == 2
    assert not (root / "round-001/decision.json").exists()
    report = (root / "verdict.txt").read_text()
    assert name in report and "VERDICT: ERROR (exit 3)" in report


@pytest.mark.parametrize("replaced", [2, 3])
def test_item_22_prior_decisions_checked_after_each_launch(tmp_path: Path, replaced: int) -> None:
    root = tmp_path / "run"
    mode = f"decision-{replaced}"
    assert run(root, mode, mode) == 3
    assert len(calls(root)) == 8
    assert not (root / "round-004/decision.json").exists()
    report = (root / "verdict.txt").read_text()
    assert f"round-{replaced:03d}/decision.json" in report and "VERDICT: ERROR (exit 3)" in report


def test_item_23_timestamp_spellings_compare_as_instants(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert run(root, "same-instant", "same-instant", fmt="junit") == 3
    assert len(calls(root)) == 4
    assert "repeated JUnit timestamp" in (root / "verdict.txt").read_text()


def test_item_23_distinct_submicrosecond_instants_are_fresh(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert run(root, "nanoseconds", "nanoseconds", fmt="junit") == 0
    assert look(root, 4).stopped_at_round == 4


@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("--max-rounds", "0"),
        ("--max-rounds", "100001"),
        ("--margin", "1/1"),
        ("--margin", "1/0"),
        ("--margin", "2/20"),
    ],
)
def test_item_24_invalid_settings_spend_no_launch(tmp_path: Path, flag: str, value: str) -> None:
    assert run(tmp_path / "run", "pass", "pass", flag, value) == 3
    assert not (tmp_path / "calls.jsonl").exists()


def test_item_25_one_loss_has_neither_warning_nor_repeated_loss_list(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert run(root, "pass", "single") == 0
    report = (root / "verdict.txt").read_text()
    assert look(root, len(list(root.glob("round-*")))).history[-1].counts.minus == 1
    assert "Warning: identical outcomes" not in report
    assert "Tasks lost in two or more rounds" not in report
    assert "Matching outcomes alone cannot show a cache" in report


def test_item_26_overflow_followed_by_full_table_path(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert run(root, "pass", "lose11") == 1
    final = look(root, len(list(root.glob("round-*"))))
    block = render_terminal(final)
    assert "--markdown PATH or --json PATH" in block
    assert (
        block + f"Full task table: round-{final.stopped_at_round:03d}/decision.json\n"
        in (root / "verdict.txt").read_text()
    )


def test_item_10_reader_exception_keeps_error_transcript(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert run(root, "reader-error", "reader-error", fmt="jsonl") == 3
    assert len(calls(root)) == 4
    report = (root / "verdict.txt").read_text()
    assert all(s in report for s in ("VERDICT: ERROR (exit 3)", "Launch record", "Files in"))
    assert "round-001/decision.json" in report and not (root / "round-002/decision.json").exists()


@pytest.mark.parametrize("wrong_inventory", [False, True])
def test_item_01_registration_uses_captured_discovery_and_checks_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wrong_inventory: bool
) -> None:
    root = tmp_path / "run"
    discover = change.discover_rule

    def discover_after_capture(paths: Sequence[Path], **options: Any) -> OutcomeRule:
        # Simulate the public file changing between capture and registration.
        assert paths == [root / "discovery/baseline.snapshot.csv"]
        if not wrong_inventory:
            (root / "discovery/baseline.csv").write_text("task_id,outcome\nreplacement,pass\n")
        registered = discover(paths, **options)
        if wrong_inventory:
            return registered.model_copy(update={"tasks": ("replacement",)})
        return registered

    monkeypatch.setattr(change, "discover_rule", discover_after_capture)
    assert run(root, "pass", "pass", "--plan-only") == 3
    assert not (root / "plan.json").exists()
    reason = "registered tasks differ" if wrong_inventory else "results changed"
    assert reason in (root / "verdict.txt").read_text()


@pytest.mark.parametrize("snapshot", [False, True])
def test_item_28_assessment_receives_stable_snapshots_and_detects_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, snapshot: bool
) -> None:
    root = tmp_path / "run"
    decide = change.decide_outcomes

    def assess_after_capture(
        rule: Path, a: list[Path], b: list[Path], **options: Any
    ) -> OutcomeDecision:
        assert a == [root / "round-001/baseline.snapshot.csv"]
        assert b == [root / "round-001/candidate.snapshot.csv"]
        result = decide(rule, a, b, **options)
        (b[0] if snapshot else root / "round-001/candidate.csv").write_bytes(b"no rows")
        return result

    monkeypatch.setattr(change, "decide_outcomes", assess_after_capture)
    assert run(root, "pass", "fail") == 3
    assert not (root / "round-001/decision.json").exists()
    assert "results changed" in (root / "verdict.txt").read_text()


@pytest.mark.parametrize("field", ["previous_sha256", "last_round_evaluated"])
def test_item_22_returned_decision_must_extend_one_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    root = tmp_path / "run"
    decide = change.decide_outcomes

    def inconsistent(*args: Any, **options: Any) -> OutcomeDecision:
        decision = decide(*args, **options)
        if decision.rounds_supplied == 2:
            fields = decision.model_dump(exclude={"record_sha256"})
            fields[field] = None if field == "previous_sha256" else 1
            return OutcomeDecision.create(**fields)
        return decision

    monkeypatch.setattr(change, "decide_outcomes", inconsistent)
    assert run(root) == 3
    assert len(calls(root)) == 5 and not (root / "round-002/decision.json").exists()
    assert "VERDICT: ERROR (exit 3)" in (root / "verdict.txt").read_text()


@pytest.mark.parametrize("name", ["plan.json", "round-001/decision.json"])
def test_item_21_evidence_checked_before_printing_final_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    root = tmp_path / "run"
    rounds = change.run_rounds

    def completed(*args: Any, **kwargs: Any) -> tuple[OutcomeDecision, bool]:
        result = rounds(*args, **kwargs)
        with (root / name).open("ab") as stream:
            stream.write(b" ")
        return result

    monkeypatch.setattr(change, "run_rounds", completed)
    assert run(root, "pass", "fail") == 3
    report = (root / "verdict.txt").read_text()
    assert "VERDICT: BLOCK" not in report and "VERDICT: ERROR (exit 3)" in report


def test_item_26_flags_in_task_name_are_not_an_overflow(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert run(root, "flag-name", "flag-name") == 0
    report = (root / "verdict.txt").read_text()
    assert "--markdown PATH or --json PATH" in report
    assert "Full task table:" not in report


@pytest.mark.parametrize(
    ("old", "new", "options", "code", "meaning", "counts"),
    [
        (
            "pass",
            "pass",
            [],
            0,
            "PASS: on these 20 tasks the new version is not worse than the old one by more than "
            "the allowed loss of 1/10, 10 points. It does not say the new version is better.",
            "Old version passed 80 of 80 task runs. New version passed 80 of 80.",
        ),
        (
            "pass",
            "fail",
            ["--margin", "1/9"],
            1,
            "BLOCK: on these 20 tasks the new version is worse than the old one by more than "
            "the allowed loss of 1/9.",
            "Old version passed 20 of 20 task runs. New version passed 0 of 20.",
        ),
        (
            "pass",
            "lose2",
            ["--max-rounds", "4"],
            2,
            "INCONCLUSIVE: after 4 rounds the runs do not decide either way. That is an answer, "
            "not a failure: there is not enough evidence yet.",
            "Old version passed 80 of 80 task runs. New version passed 72 of 80.",
        ),
        (
            "pass",
            "errors2",
            ["--max-rounds", "4"],
            3,
            "ERROR: the campaign could not be completed, so there is no verdict.",
            "Old version passed 20 of 20 task runs. New version passed 18 of 20.",
        ),
        (
            "exit7",
            "exit7",
            [],
            3,
            "ERROR: the campaign could not be completed, so there is no verdict.",
            "Old version passed 20 of 20 task runs. New version passed 20 of 20.",
        ),
        (
            "missing-discovery",
            "pass",
            [],
            3,
            "ERROR: the campaign could not be completed, so there is no verdict.",
            None,
        ),
    ],
)
def test_item_27_plain_sentences_and_launch_status(
    tmp_path: Path,
    old: str,
    new: str,
    options: list[str],
    code: int,
    meaning: str,
    counts: str | None,
) -> None:
    root = tmp_path / "run"
    assert run(root, old, new, *options) == code
    lines = (root / "verdict.txt").read_text().splitlines()
    i = lines.index("arci check-change verdict")
    assert lines[i + 1] == meaning
    if counts is None:
        assert not any(s.startswith("Old version passed") for s in lines)
    else:
        assert lines[i + 2] == counts
    start = lines.index("Launch record (discovery excluded from scoring):") + 1
    entries = lines[start : start + len(calls(root))]
    assert len(entries) == len(calls(root))
    for line, (r, arm) in zip(entries, calls(root), strict=True):
        folder = f"round-{r:03d}" if isinstance(r, int) and r else "discovery"
        status = (root / folder / f"{arm}.exit").read_text().strip()
        expected = {"0": "success", "1": "test failure", "7": "unexpected exit"}[status]
        assert expected in line and f"exit {status}" in line


@pytest.mark.parametrize("snapshot", [False, True])
def test_item_28_captured_files_checked_before_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, snapshot: bool
) -> None:
    root = tmp_path / "run"
    rounds = change.run_rounds

    def late_change(*args: Any, **kwargs: Any) -> tuple[OutcomeDecision, bool]:
        result = rounds(*args, **kwargs)
        path = root / "round-001" / ("candidate.snapshot.csv" if snapshot else "candidate.csv")
        if path.is_file():
            path.write_bytes(b"changed")
        return result

    monkeypatch.setattr(change, "run_rounds", late_change)
    assert run(root, "pass", "fail") == 3
    assert "results changed" in (root / "verdict.txt").read_text()


@pytest.mark.parametrize("target", ["plan.json", "round-001/decision.json"])
def test_item_29_changed_evidence_prevents_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    root = tmp_path / "run"
    run_rounds = change.run_rounds

    def interpose(order: Any, launch: Any, *args: Any) -> tuple[OutcomeDecision, bool]:
        def between(arm: Arm, number: int) -> change.LaunchResult:
            if number == 2:
                (root / target).write_bytes(b"changed between launches")
            return launch(arm, number)

        return run_rounds(order, between, *args)

    monkeypatch.setattr(change, "run_rounds", interpose)
    assert run(root, "pass", "pass") == 3
    assert len(calls(root)) == 3
    assert not list((root / "round-002").glob("*.exit"))


def test_item_30_signal_while_leader_reserved_and_record_its_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "run"
    killpg = os.killpg
    reserved: list[bool] = []
    reaped: set[int] = set()
    wait = subprocess.Popen.wait

    def reap(child: subprocess.Popen[bytes], timeout: float | None = None) -> int:
        code = wait(child, timeout)
        reaped.add(child.pid)
        return code

    def observe(pid: int, sig: int) -> None:
        reserved.append(pid not in reaped)
        if hasattr(os, "waitid") and reserved[-1]:
            os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        killpg(pid, sig)

    monkeypatch.setattr(subprocess.Popen, "wait", reap)
    monkeypatch.setattr(os, "killpg", observe)
    assert run(root, "tree-success", "tree-success", "--plan-only") == 0
    assert reserved and all(reserved)
    assert (root / "discovery/baseline.exit").read_text() == "1\n"
    for pid in (tmp_path / "worker.pid").read_text().split():
        assert_stopped(int(pid))


def assert_stopped(pid: int) -> None:
    if sys.platform.startswith("linux"):
        try:
            state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        except FileNotFoundError:
            return
        assert state in {"Z", "X"}
    else:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


def test_item_31_globally_unreachable_margin_spends_no_launch(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert run(root, "pass", "pass", "--margin", "1/20000") == 3
    assert not (tmp_path / "calls.jsonl").exists()
    assert "100000" in (root / "verdict.txt").read_text()


def test_item_28_snapshots_reused_and_indexed_files_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "run"
    stamps: dict[Path, tuple[int, int]] = {}
    decide = change.decide_outcomes

    def inspect(rule: Path, a: list[Path], b: list[Path], **options: Any) -> OutcomeDecision:
        for path in [*a, *b]:
            assert path.is_relative_to(root) and path.name.endswith(".snapshot.csv")
            info = path.stat()
            stamp = info.st_ino, info.st_mtime_ns
            assert stamps.setdefault(path, stamp) == stamp
        return decide(rule, a, b, **options)

    monkeypatch.setattr(change, "decide_outcomes", inspect)
    assert run(root, "pass", "lose2", "--max-rounds", "4") == 2
    decision = look(root, 4)
    index = (root / "verdict.txt").read_text().splitlines()
    assert len(stamps) == 8
    for snapshot in (True, False):
        paths: dict[Arm, list[str]] = {"baseline": [], "candidate": []}
        for item in decision.inputs:
            path = Path(item.path)
            if not snapshot:
                path = path.with_name(f"{item.arm}.csv")
            assert f"  {path.relative_to(root)}" in index
            paths[item.arm].append(str(path))
        target = tmp_path / "manual.json"
        assert (
            main(
                [
                    "verdict",
                    str(root / "rule.yaml"),
                    "--baseline",
                    *paths["baseline"],
                    "--candidate",
                    *paths["candidate"],
                    "--json",
                    str(target),
                ]
            )
            == decision.exit_code
        )
        manual = OutcomeDecision.model_validate_json(target.read_bytes())
        assert (manual.history, manual.tasks, manual.stopped_at_round) == (
            decision.history,
            decision.tasks,
            decision.stopped_at_round,
        )
        target.unlink()


def test_item_28_absence_checked_on_pinned_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "run"
    stat = os.stat
    directory_ids: list[int] = []

    def observe(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        if path == "baseline.csv" and kwargs.get("follow_symlinks") is False:
            directory_ids.append(os.fstat(kwargs["dir_fd"]).st_ino)
        return stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", observe)
    assert run(root, "pass", "pass", "--plan-only") == 0
    assert directory_ids == [(root / "discovery").stat().st_ino]


def test_item_30_unreaped_zombie_has_no_effect_on_leader_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Model a Linux init that keeps an orphan zombie. Use a real leader and same-group
    # helper for the signal; the simulated /proc entry outlives them both.
    root = tmp_path / "run"
    member = tmp_path / "123"
    member.mkdir()
    linux_stat = member / "stat"
    getpriority = os.getpriority
    iterdir = Path.iterdir

    def orphan(which: int, group: int) -> int:
        if which == os.PRIO_PGRP:
            linux_stat.write_bytes(f"123 (helper) Z 1 {group} {group}".encode())
            return 0
        return getpriority(which, group)

    def processes(path: Path):
        return iter([member]) if path == Path("/proc") else iterdir(path)

    monkeypatch.setattr(os, "getpriority", orphan)
    monkeypatch.setattr(Path, "iterdir", processes)
    monkeypatch.setattr(sys, "platform", "linux")
    assert run(root, "tree-success", "tree-success", "--plan-only") == 0
    assert (root / "discovery/baseline.exit").read_text() == "1\n"
    assert linux_stat.exists()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS process-exit notification")
def test_item_30_macos_without_python_waitid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delattr(os, "waitid", raising=False)
    root = tmp_path / "run"
    assert run(root, "tree-success", "tree-success", "--plan-only") == 0
    assert (root / "discovery/baseline.exit").read_text() == "1\n"
    for pid in (tmp_path / "worker.pid").read_text().split():
        assert_stopped(int(pid))


@pytest.mark.parametrize(
    ("sig", "mode"),
    [
        (signal.SIGINT, "cancel"),
        (signal.SIGTERM, "cancel"),
        (signal.SIGTERM, "cancel-changed-plan"),
    ],
)
def test_item_32_cancel_live_launch(tmp_path: Path, sig: signal.Signals, mode: str) -> None:
    root = tmp_path / "run"
    ready = tmp_path / "launch.pid"
    args = [
        sys.executable,
        "-m",
        "arci",
        "check-change",
        "--baseline",
        command(mode),
        "--candidate",
        command(mode),
        "--out-dir",
        str(root),
    ]
    with subprocess.Popen(args, start_new_session=True) as controller:
        try:
            deadline = time.monotonic() + 10
            while not ready.exists():
                assert controller.poll() is None and time.monotonic() < deadline
                time.sleep(0.01)
            leader, helper = map(int, ready.read_text().split())
            assert os.getpgid(helper) == leader
            controller.send_signal(sig)
            code = controller.wait(timeout=10)
        finally:
            if controller.poll() is None:
                controller.kill()
    assert_stopped(leader)
    assert_stopped(helper)
    assert code == 128 + sig
    lines = (root / "verdict.txt").read_text().splitlines()
    assert "ERROR: the campaign was cancelled, so there is no verdict." in lines
    assert not any(line.startswith("VERDICT:") for line in lines)
    launches = calls(root)
    assert launches[0] == [0, "baseline"]
    if mode == "cancel-changed-plan":
        assert len(launches) == 2 and launches[-1][0] == 1
        assert any("registration changed" in line for line in lines)
    else:
        assert len(launches) == 1
    assert not list(root.rglob("decision.json"))


def test_item_32_cancel_reaps_leader_and_restores_handlers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    leaders: list[int] = []

    def interrupt_wait(pid: int, timeout: float, *args: object) -> bool:
        leaders.append(pid)
        signal.raise_signal(signal.SIGTERM)
        return False

    def previous_handler(sig: int, frame: FrameType | None) -> None:
        pytest.fail("cancellation reached the caller's handler")

    monkeypatch.setattr(change, "_exited", interrupt_wait)
    with ExitStack() as restore:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous = signal.signal(sig, previous_handler)
            restore.callback(signal.signal, sig, previous)
        assert run(tmp_path / "run") == 143
        assert all(
            signal.getsignal(sig) is previous_handler for sig in (signal.SIGINT, signal.SIGTERM)
        )
    (leader,) = leaders
    with pytest.raises(ChildProcessError):
        os.waitpid(leader, os.WNOHANG)


def test_item_33_replay_sealed_snapshots_after_original_changes(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assert run(root, "pass", "fail") == 1
    folder = root / "round-001"
    (folder / "candidate.csv").write_bytes((folder / "baseline.csv").read_bytes())
    decision = look(root, 1)
    index = (root / "verdict.txt").read_text().split(f"Files in {root}:\n")[1].splitlines()
    args = ["verdict", str(root / "rule.yaml")]
    for item in decision.inputs:
        snapshot = folder / f"{item.arm}.snapshot.csv"
        assert Path(item.path) == snapshot
        assert f"  {snapshot.relative_to(root)}" in index
        args.extend([f"--{item.arm}", item.path])
    replay = tmp_path / "manual.json"
    assert main([*args, "--json", str(replay)]) == decision.exit_code
    assert OutcomeDecision.model_validate_json(replay.read_bytes()) == decision


@pytest.mark.parametrize("name", ["baseline.csv", "baseline.snapshot.csv"])
def test_item_34_prior_capture_checked_before_second_launch(tmp_path: Path, name: str) -> None:
    root = tmp_path / "run"
    mode = f"overwrite-{name}"
    assert run(root, mode, mode) == 3
    assert "results changed" in (root / "verdict.txt").read_text()
    arms = json.loads((root / "plan.json").read_text())["arm_order"][1]
    assert [entry for entry in calls(root) if entry[0] == 2] == [[2, arms[0]]]
    assert not (root / "round-002/decision.json").exists()


def test_item_35_wrong_returned_digest_with_intact_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "run"
    decide = change.decide_outcomes
    scored = b""

    def wrong_digest(*args: Any, **kwargs: Any) -> OutcomeDecision:
        nonlocal scored
        decision = decide(*args, **kwargs)
        first, *rest = decision.inputs
        scored = Path(first.path).read_bytes()
        incorrect = first.model_copy(update={"sha256": "0" * 64})
        return OutcomeDecision.create(
            **decision.model_dump(exclude={"inputs", "record_sha256"}), inputs=(incorrect, *rest)
        )

    monkeypatch.setattr(change, "decide_outcomes", wrong_digest)
    assert run(root, "pass", "fail") == 3
    assert "scored bytes differ" in (root / "verdict.txt").read_text()
    assert scored == (root / "round-001/baseline.csv").read_bytes()
    assert scored == (root / "round-001/baseline.snapshot.csv").read_bytes()
    assert not (root / "round-001/decision.json").exists()


def test_unsupported_platform_refused_before_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delattr(os, "waitid", raising=False)
    monkeypatch.delattr(select, "kqueue", raising=False)

    def refuse_spawn(*args: object, **kwargs: object) -> None:
        pytest.fail("started a launch")

    monkeypatch.setattr(subprocess, "Popen", refuse_spawn)
    root = tmp_path / "run"
    assert run(root) == 3
    assert "unsupported platform" in (root / "verdict.txt").read_text()
