from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from arci.gate import decide
from arci.report import render_junit, render_markdown
from arci.schema import Manifest
from tests.acceptance.helpers import manifest, synthetic_trials


def test_markdown_matches_golden_and_is_order_independent() -> None:
    experiment = manifest(n_per_arm=12, prior_runs=("exp-earlier",))
    trials = synthetic_trials(
        experiment,
        condition_id="fetch_timeout",
        baseline_successes=12,
        candidate_successes=0,
    )
    decision = decide(experiment, trials)
    expected = Path(__file__).with_name("block_report.md").read_text(encoding="utf-8")

    assert render_markdown(experiment, decision, trials) == expected
    assert render_markdown(experiment, decision, tuple(reversed(trials))) == expected
    assert expected.rstrip().splitlines()[-1] == "VERDICT: BLOCK (exit 1)"


def test_junit_has_candidate_cases_and_a_failing_gate_case() -> None:
    experiment = manifest(n_per_arm=2)
    trials = synthetic_trials(
        experiment,
        condition_id="fetch_timeout",
        baseline_successes=2,
        candidate_successes=0,
        candidate_errors=1,
    )
    decision = decide(experiment, trials)

    root = ET.fromstring(render_junit(experiment, decision, trials))
    suite = root.find("testsuite")
    assert suite is not None
    assert suite.attrib == {
        "name": "fetch_timeout",
        "tests": "3",
        "failures": "2",
        "errors": "1",
    }
    assert len(suite.findall("testcase")) == 3
    assert len(suite.findall("testcase/failure")) == 2
    assert len(suite.findall("testcase/error")) == 1


def test_markdown_reports_sequential_looks_and_stopping_look() -> None:
    data = manifest(n_per_arm=48).model_dump(exclude={"record_sha256"})
    experiment = Manifest.create(**{**data, "looks": (12, 24, 48)})
    trials = synthetic_trials(
        experiment,
        condition_id="fetch_timeout",
        baseline_successes=12,
        candidate_successes=0,
        n=12,
    )

    report = render_markdown(experiment, decide(experiment, trials), trials)

    assert "## Looks" in report
    assert "Stopped at look 1 of 3." in report
    assert "| 1 | 12 | **BLOCK** |" in report
