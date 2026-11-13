"""Suite-only presentation agrees across formats and treats tool names as data."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arci.cli import main
from arci.html_report import render_suite_html
from arci.schema import Outcome, TrialEnvelope
from arci.suite_gate import decide_suite
from arci.suite_report import render_suite_json, render_suite_markdown
from arci.suite_storage import SuiteStore
from tests.unit.html_report.test_html_report import Document
from tests.unit.suite_report.test_reports import evidence
from tests.unit.suite_report.test_tool_outcomes import INTRO, trial


def test_formats_agree_and_old_store_renders_without_mutation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    m, original = evidence("BLOCK")
    baseline = next(t for t in original if t.arm == "baseline")
    candidate = next(t for t in original if t.arm == "candidate")
    baseline = TrialEnvelope.create(
        **(
            baseline.model_dump(exclude={"record_sha256"})
            | {
                "outcome": Outcome.PASS,
                "events": trial(
                    [
                        ("tool_start", {"tool": "lookup"}),
                        ("tool_finish", {"tool": "lookup", "ok": False}),
                        ("tool_start", {"tool": "lookup"}),
                        ("tool_finish", {"tool": "lookup", "ok": False}),
                    ]
                ).events,
            }
        )
    )
    candidate = TrialEnvelope.create(
        **(
            candidate.model_dump(exclude={"record_sha256"})
            | {
                "outcome": Outcome.ERROR,
                "events": trial([("tool_finish", {"tool": "lookup", "ok": False})]).events,
            }
        )
    )
    trials = (baseline, candidate)
    d = decide_suite(m, trials)
    report = json.loads(render_suite_json(m, d, trials))
    md = render_suite_markdown(m, d, trials)
    html = render_suite_html(m, d, trials)
    document = Document(html)
    expected = [
        ["baseline", "1", "1", "1", "0"],
        ["candidate", "1", "1", "0", "1"],
        ["lookup", "baseline", "1", "1", "0", "2", "2", "1"],
        ["lookup", "candidate", "1", "0", "1", "0", "1", "1"],
    ]
    arm_keys = (
        "arm",
        "trials",
        "uninjected_failure_trials",
        "uninjected_then_passed",
        "uninjected_then_not_passed",
    )
    tool_keys = (
        "tool",
        "arm",
        "trials",
        "trials_started",
        "trials_not_started",
        "starts",
        "uninjected_failures",
        "uninjected_failure_trials",
    )
    actual = [[str(row[k]) for k in arm_keys] for row in report["tool_outcomes"]["arms"]]
    actual += [[str(row[k]) for k in tool_keys] for row in report["tool_outcomes"]["tools"]]
    assert actual == expected
    for row in expected:
        assert row in document.rows
        cells = row.copy()
        if cells[0] == "lookup":
            cells[0] = "`lookup`"
        assert "| " + " | ".join(cells) + " |" in md
    assert INTRO in document.text
    assert (
        html.index("<h2>Fault accounting")
        < html.index("<h2>Tool outcomes")
        < html.index("<h2>Failure details")
    )
    # Existing schema and store APIs: no migration or extra stored fields.
    store = SuiteStore(tmp_path, m)
    for t in trials:
        store.append_trial(t)
    before = {p.name: p.read_bytes() for p in store.run_dir.iterdir()}
    for fmt, expected_output in (
        ("json", render_suite_json(m, d, trials)),
        ("md", md),
        ("html", html),
    ):
        assert main(["report", str(store.run_dir), "--format", fmt]) == 3
        assert capsys.readouterr().out == expected_output
    assert {p.name: p.read_bytes() for p in store.run_dir.iterdir()} == before


def test_html_tool_name_is_escaped_and_only_in_cells() -> None:
    m, _ = evidence("BLOCK")
    attack = '<script>alert("x")</script>'
    trials = [trial([("tool_start", {"tool": attack})])]
    html = render_suite_html(m, decide_suite(m, trials), trials)
    document = Document(html)
    assert attack not in html
    assert "&lt;script&gt;" in html
    assert "script" not in document.tags
    assert sum(attack in row for row in document.rows) == 2
    assert html.count("&lt;script&gt;") == 2


def test_empty_html_retains_arm_table() -> None:
    m, _ = evidence("BLOCK")
    html = render_suite_html(m, decide_suite(m, []), [])
    document = Document(html)
    for arm in ("baseline", "candidate"):
        assert [arm, "0", "0", "0", "0"] in document.rows
    assert "No tool starts recorded." in document.text
