"""Offline HTML contracts: evidence, escaping, determinism and CLI compatibility."""

from __future__ import annotations

import json
import random
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest

from arci.cli import main
from arci.gate import decide
from arci.html_report import LOW_BASELINE, PER_ROUND_VERBATIM, render_html, render_suite_html
from arci.schema import Manifest, TrialEnvelope, Verdict
from arci.storage import ExperimentStore
from arci.suite_gate import decide_suite
from arci.suite_report import guarantee, render_suite_json
from tests.acceptance.helpers import manifest, synthetic_trials
from tests.unit.suite_report.test_reports import evidence, store_at

GOLDENS = Path(__file__).parent / "golden"


class Document(HTMLParser):
    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.text: list[str] = []
        self.rows: list[list[str]] = []
        self.cell: list[str] | None = None
        self.feed(source)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        assert tag in {
            "html",
            "head",
            "meta",
            "title",
            "style",
            "body",
            "main",
            "h1",
            "h2",
            "p",
            "div",
            "table",
            "caption",
            "thead",
            "tr",
            "th",
            "tbody",
            "td",
            "footer",
            "svg",
            "desc",
            "path",
            "polyline",
            "text",
            "pre",
        }
        for name, value in attrs:
            assert not name.startswith("on")
            assert name in {
                "lang",
                "charset",
                "name",
                "content",
                "class",
                "tabindex",
                "role",
                "aria-label",
                "scope",
                "viewbox",
                "aria-labelledby",
                "id",
                "d",
                "fill",
                "stroke",
                "stroke-dasharray",
                "points",
                "stroke-width",
                "x",
                "y",
            }
            if tag == "meta":
                assert dict(attrs).get("name", "viewport") == "viewport"
            assert value is None or not re.search(r"https?:|//", value, re.I)
        if tag == "tr":
            self.rows.append([])
        if tag in {"td", "th"}:
            self.cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.cell is not None:
            self.rows[-1].append("".join(self.cell))
            self.cell = None

    def handle_data(self, data: str) -> None:
        if self.tags and self.tags[-1] == "style":
            assert "\\" not in data
            assert not re.search(r"url\s*\(|@import|image-set\s*\(|expression\s*\(", data, re.I)
        self.text.append(data)
        if self.cell is not None:
            self.cell.append(data)


def v1_evidence() -> tuple[Manifest, list[TrialEnvelope]]:
    m = manifest(n_per_arm=12, prior_runs=("exp-earlier",))
    return m, synthetic_trials(
        m, condition_id="fetch_timeout", baseline_successes=12, candidate_successes=0
    )


@pytest.mark.parametrize("verdict", ["PASS", "BLOCK", "INCONCLUSIVE", "ERROR"])
def test_suite_golden_and_every_numeric_table_field_matches_json(
    verdict: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    m, trials = evidence(verdict)
    d = decide_suite(m, trials)
    html = render_suite_html(m, d, trials)
    assert html == (GOLDENS / f"{verdict.lower()}.html").read_text()
    assert html == render_suite_html(m, d, trials)
    store = store_at(tmp_path, verdict)
    assert main(["report", str(store.run_dir), "--format", "html"]) == d.exit_code
    assert capsys.readouterr().out == html
    shuffled = list(trials)
    random.Random(7).shuffle(shuffled)
    assert html == render_suite_html(m, decide_suite(m, shuffled), shuffled)
    document = Document(html)
    report: dict[str, Any] = json.loads(render_suite_json(m, d, trials))
    decision = report["decision"]
    # Each complete HTML table row is reconstructed independently from the JSON report.
    for row in decision["history"]:
        c = row["counts"]
        assert [
            str(row["round"]),
            str(row["pairs"]),
            str(c["minus"]),
            str(c["zero"]),
            str(c["plus"]),
            f"{c['errored']} / {decision['max_errored_pairs']}",
            str(row["candidate_hard_violations"]),
            row["pass_wealth"],
            row["block_wealth"],
            decision["threshold"],
            str(row["pass_crossed"]).lower(),
            str(row["block_crossed"]).lower(),
            row["verdict"],
        ] in document.rows
    for cell in decision["cells"]:
        c = cell["counts"]
        assert [
            cell["task_id"],
            cell["condition_id"],
            str(cell["pairs"]),
            str(cell["baseline_successes"]),
            str(cell["candidate_successes"]),
            str(c["minus"]),
            str(c["zero"]),
            str(c["plus"]),
            str(c["errored"]),
            str(cell["candidate_hard_violations"]),
        ] in document.rows
    for row in report["fault_accounting"]:
        assert [
            row["condition_id"],
            row["fault"],
            row["arm"],
            str(row["trials"]),
            str(row["injections"]),
            str(row["trials_fired"]),
            row["status"],
        ] in document.rows
    text = " ".join(document.text)
    for key in ("alpha", "delta", "threshold", "n_cells", "max_rounds", "stopped_at_round"):
        assert str(decision[key]) in text
    for arm in ("baseline", "candidate"):
        successes = sum(cell[f"{arm}_successes"] for cell in decision["cells"])
        assert [arm, str(successes), str(report["observed_trials"] // 2)] in document.rows
    for key in (
        "guarantee",
        "assumptions",
        "cell_warning",
        "wealth_display",
        "integrity_limitation",
    ):
        assert report[key] in text
    assert "declared, never fired" in text
    assert "http:" not in html and "https:" not in html and "//" not in html
    assert "svg" in document.tags


def test_v1_golden_and_escaped_failure_detail() -> None:
    m, trials = v1_evidence()
    html = render_html(m, decide(m, trials), trials)
    assert html == (GOLDENS / "v1.html").read_text()
    assert html == render_html(m, decide(m, trials), list(reversed(trials)))
    Document(html)
    attack = '<script>alert("x")</script><img src="//example.test/x">'
    trials[-1] = TrialEnvelope.create(
        **(trials[-1].model_dump(exclude={"record_sha256"}) | {"failure_detail": attack})
    )
    html = render_html(m, decide(m, trials), trials)
    parsed = Document(html)
    assert attack in " ".join(parsed.text)
    assert attack not in html
    assert "&lt;script&gt;" in html


def test_suite_escapes_task_failure_and_prior_run() -> None:
    m, trials = evidence("BLOCK")
    attack = '<script>alert("x")</script>'
    d = decide_suite(m, trials)
    d = d.model_copy(
        update={
            "cells": (d.cells[0].model_copy(update={"task_id": attack}), *d.cells[1:]),
            "prior_runs": (attack,),
        }
    )
    trials = (trials[0].model_copy(update={"failure_detail": attack}), *trials[1:])
    html = render_suite_html(m, d, trials)
    assert "&lt;script&gt;" in html and attack not in html
    assert attack in " ".join(Document(html).text)


@pytest.mark.parametrize("mode", ["fixed", "per_round"])
def test_low_baseline_warning_seed_guarantee_and_invalid_history(mode: str) -> None:
    m, trials = evidence("BLOCK")
    m = m.model_copy(update={"scenario_seeds": mode})
    # An invalid manifest produces no validated history; observed counts remain descriptive.
    trials = tuple(t.model_copy(update={"outcome": "FAIL"}) for t in trials)
    html = render_suite_html(m, decide_suite(m, trials), trials)
    text = " ".join(Document(html).text)
    assert LOW_BASELINE in text
    assert guarantee(mode) in text
    if mode == "per_round":
        assert PER_ROUND_VERBATIM in text
        statistics = " ".join(
            Path("docs/STATISTICS_SUITE.md").read_text().replace("**", "").split()
        )
        assert PER_ROUND_VERBATIM in statistics
    assert "No validated complete-round history" in text
    assert "VERDICT: ERROR (exit 3)" in text


@pytest.mark.parametrize("status", ["absent", "match", "mismatch", "malformed"])
def test_cli_html_out_and_shuffled_store(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], status: str
) -> None:
    store = store_at(tmp_path, "BLOCK")
    m, trials = evidence("BLOCK")
    path = store.run_dir / "decision.json"
    if status == "match":
        store.write_decision(decide_suite(m, trials))
    elif status == "mismatch":
        store.write_decision(decide_suite(*evidence("PASS")))
    elif status == "malformed":
        path.write_text("broken")
    before = {p.name: p.read_bytes() for p in store.run_dir.iterdir()}
    code = 3 if status in {"mismatch", "malformed"} else 1
    assert main(["report", str(store.run_dir), "--format", "html"]) == code
    html = capsys.readouterr().out
    parsed = Document(html)
    assert f"VERDICT: {'ERROR' if code == 3 else 'BLOCK'} (exit {code})" in " ".join(parsed.text)
    out = tmp_path / "out.html"
    assert main(["report", str(store.run_dir), "--format", "html", "--out", str(out)]) == code
    assert out.read_text() == html and capsys.readouterr().out == ""
    assert {p.name: p.read_bytes() for p in store.run_dir.iterdir()} == before
    lines = (store.run_dir / "trials.jsonl").read_text().splitlines()
    random.Random(12).shuffle(lines)
    (store.run_dir / "trials.jsonl").write_text("\n".join(lines) + "\n")
    assert main(["report", str(store.run_dir), "--format", "html"]) == code
    assert capsys.readouterr().out == html


def test_v1_cli_and_reject_non_html_out(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    m, trials = v1_evidence()
    store = ExperimentStore(tmp_path, m)
    for trial in trials:
        store.append_trial(trial)
    before = {p.name: p.read_bytes() for p in store.run_dir.iterdir()}
    assert main(["report", str(store.run_dir), "--format", "html"]) == 0
    assert capsys.readouterr().out == render_html(m, decide(m, trials), trials)
    assert {p.name: p.read_bytes() for p in store.run_dir.iterdir()} == before
    shuffled = list(trials)
    random.Random(8).shuffle(shuffled)
    (store.run_dir / "trials.jsonl").write_text(
        "\n".join(t.model_dump_json() for t in shuffled) + "\n"
    )
    html_file = tmp_path / "v1.html"
    assert main(["report", str(store.run_dir), "--format", "html", "--out", str(html_file)]) == 0
    assert html_file.read_text() == render_html(m, decide(m, trials), trials)
    assert capsys.readouterr().out == ""
    out = tmp_path / "bad.md"
    assert main(["report", str(store.run_dir), "--out", str(out)]) == 3
    assert not out.exists()
    assert main(["report", str(store.run_dir), "--format", "html", "--pass-k", "2"]) == 3


def test_demo_sample_is_current(tmp_path: Path) -> None:
    from arci.demo.suite import build_manifest
    from arci.suite_runner import run_suite

    m = build_manifest("regression")
    trials = run_suite(m, tmp_path, workers=4)
    d = decide_suite(m, trials)
    assert d.verdict is Verdict.BLOCK
    actual = render_suite_html(m, d, trials, stored_status="match")
    assert actual == Path("docs/results/sample-suite-report.html").read_text()
    Document(actual)
