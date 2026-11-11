"""Regenerate reviewed goldens and the real offline demo sample.

Run from the worktree root: .venv/bin/python -m tests.unit.html_report.generate
The sample also has a test that runs the demo and compares its exact report bytes.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from arci.demo.suite import build_manifest
from arci.gate import decide
from arci.html_report import render_html, render_suite_html
from arci.suite_gate import decide_suite
from arci.suite_runner import run_suite
from tests.unit.html_report.test_html_report import GOLDENS, v1_evidence
from tests.unit.suite_report.test_reports import evidence


def generate() -> None:
    GOLDENS.mkdir(exist_ok=True)
    for verdict in ("PASS", "BLOCK", "INCONCLUSIVE", "ERROR"):
        m, trials = evidence(verdict)
        (GOLDENS / f"{verdict.lower()}.html").write_text(
            render_suite_html(m, decide_suite(m, trials), trials), encoding="utf-8"
        )
    m1, trials1 = v1_evidence()
    (GOLDENS / "v1.html").write_text(
        render_html(m1, decide(m1, trials1), trials1), encoding="utf-8"
    )
    with TemporaryDirectory() as temp:
        demo = build_manifest("regression")
        observed = run_suite(demo, temp, workers=4)
        decision = decide_suite(demo, observed)
        assert decision.verdict.value == "BLOCK"
        Path("docs/results/sample-suite-report.html").write_text(
            render_suite_html(demo, decision, observed, stored_status="match"), encoding="utf-8"
        )


if __name__ == "__main__":
    generate()
