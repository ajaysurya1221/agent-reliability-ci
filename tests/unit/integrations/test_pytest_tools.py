"""ADR 0020 B1-B4 on the saved DeepEval and Opik pytest reports."""

import shlex
import sys
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

import pytest

from arci.cli import main
from arci.importers import junit
from arci.outcome_schema import OutcomeDecision
from arci.schema import Verdict

REAL = Path(__file__).with_name("real")
TOOLS = ("deepeval", "opik")


def raw_cases(path: Path) -> dict[str, str]:
    cases: dict[str, str] = {}
    for case in ElementTree.parse(path).iter("testcase"):
        key = case.attrib["classname"] + "::" + case.attrib["name"]
        assert key not in cases
        if case.find("skipped") is not None or case.find("error") is not None:
            outcome = "error"
        elif case.find("failure") is not None:
            outcome = "fail"
        else:
            outcome = "pass"
        cases[key] = outcome
    return cases


def read_report(path: Path) -> list[tuple[str, int, str | None]]:
    report = junit.read(
        path.read_text(), path=str(path), arm="baseline", position=1, tasks=None, seen=set()
    )
    return [(row.task_id, row.round, row.outcome) for row in report.rows]


@pytest.mark.parametrize("tool", TOOLS)
def test_b01_all_junit_rows(tool: str) -> None:
    folder = REAL / tool
    reports = sorted(folder.glob("*.xml"))
    required = {"e2e-discovery", "e2e-r1-baseline", "e2e-r1-candidate", "named-run2", "shapes"}
    if tool == "opik":
        required.add("logging-on")
    assert required <= {p.stem for p in reports}
    for path in reports:
        expected = raw_cases(path)
        assert read_report(path) == [(key, 1, value) for key, value in expected.items()]
        if path.stem == "shapes":
            assert expected["test_shapes::test_body_raises"] == "fail"
            assert expected["test_shapes::test_skipped_setup"] == "error"


@pytest.mark.parametrize("tool", TOOLS)
def test_b02_explicit_ids_repeat(tool: str) -> None:
    folder = REAL / tool
    baseline = {key for key, _, _ in read_report(folder / "e2e-r1-baseline.xml")}
    assert baseline == {key for key, _, _ in read_report(folder / "named-run2.xml")}
    assert baseline == {f"test_agent::test_agent[task-w{n:02d}]" for n in range(1, 21)}


def test_b02_positional_ids() -> None:
    keys = [key for key, _, _ in read_report(REAL / "deepeval/shapes.xml") if "positional" in key]
    assert keys == [f"test_shapes::test_positional[golden{n}]" for n in range(3)]


def test_b03_distinct_suite_timestamps() -> None:
    seen: set[datetime] = set()
    for tool in TOOLS:
        for path in sorted((REAL / tool).glob("*.xml")):
            suites = list(ElementTree.parse(path).iter("testsuite"))
            assert suites
            times = {datetime.fromisoformat(s.attrib["timestamp"]) for s in suites}
            assert seen.isdisjoint(times), path
            seen.update(times)


@pytest.mark.parametrize("tool", TOOLS)
def test_b04_check_change_and_hand_replay(tmp_path: Path, tool: str) -> None:
    source = REAL / tool
    fake = tmp_path / "copy_report.py"
    fake.write_text(
        """import os, shutil, sys
from pathlib import Path
arm = os.environ["ARCI_CHANGE_ARM"]
round_number = int(os.environ["ARCI_CHANGE_ROUND"])
assert round_number in (0, 1)
stem = "discovery" if round_number == 0 else f"r1-{arm}"
shutil.copyfile(Path(sys.argv[1]) / f"e2e-{stem}.xml", sys.argv[2])
sys.exit(int(arm == "candidate"))
"""
    )
    template = shlex.join([sys.executable, str(fake), str(source), "{out}"])
    root = tmp_path / "comparison"
    assert (
        main(
            [
                "check-change",
                "--format",
                "junit",
                "--baseline",
                template,
                "--candidate",
                template,
                "--out-dir",
                str(root),
            ]
        )
        == 1
    )
    look = root / "round-001"
    baseline = look / "baseline.snapshot.xml"
    candidate = look / "candidate.snapshot.xml"
    assert (root / "discovery/baseline.snapshot.xml").read_bytes() == (
        source / "e2e-discovery.xml"
    ).read_bytes()
    for path, arm in [(baseline, "baseline"), (candidate, "candidate")]:
        assert path.read_bytes() == (source / f"e2e-r1-{arm}.xml").read_bytes()
    target = tmp_path / "manual.json"
    assert (
        main(
            [
                "verdict",
                str(root / "rule.yaml"),
                "--baseline",
                str(baseline),
                "--candidate",
                str(candidate),
                "--json",
                str(target),
            ]
        )
        == 1
    )
    manual = OutcomeDecision.model_validate_json(target.read_bytes())
    campaign = OutcomeDecision.model_validate_json((look / "decision.json").read_bytes())
    assert manual.validate_seal() and campaign.validate_seal()
    assert manual.verdict == campaign.verdict == Verdict.BLOCK
    assert manual.stopped_at_round == campaign.stopped_at_round == 1
    assert manual.tasks == campaign.tasks
    assert manual.history == campaign.history
    old = raw_cases(source / "e2e-r1-baseline.xml")
    new = raw_cases(source / "e2e-r1-candidate.xml")
    losses = sum(value == "pass" and new[key] == "fail" for key, value in old.items())
    assert manual.history[0].counts.minus == losses == 20
    assert not (root / "round-002").exists()
