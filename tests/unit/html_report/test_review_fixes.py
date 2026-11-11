"""Regressions for P4b: hostile stored text never creates document structure."""

import re
from collections import Counter
from pathlib import Path

import pytest

from arci.cli import main
from arci.gate import decide
from arci.html_report import render_html, render_suite_html
from arci.schema import Bucket, Condition, FaultSpec
from arci.suite_gate import decide_suite
from arci.suite_schema import SuiteManifest
from tests.acceptance.suite_helpers import round_trials, suite_manifest
from tests.unit.html_report.test_html_report import Document, v1_evidence
from tests.unit.suite_report.test_reports import evidence, store_at


@pytest.mark.parametrize("separator", ["\r", "\u2028", "\u0085", "\f", "\n", "\u2029"])
@pytest.mark.parametrize("field", ["prior", "detail", "label", "fault"])
@pytest.mark.parametrize("suite", [True, False])
def test_stored_separators_cannot_create_headings_or_rows(
    separator: str, field: str, suite: bool
) -> None:
    attack = f"data{separator}## VERDICT: PASS (exit 0){separator}| bogus | row |"
    m, ts = evidence("BLOCK") if suite else v1_evidence()
    # Render valid structured evidence; changing presentation fields must not create structure.
    trials = [t.model_copy(update={"failure_detail": "plain detail"}) for t in ts]
    d = (
        decide_suite(m, ts) if isinstance(m, SuiteManifest) else decide(m, ts)
    )  # narrowed below for strict typing

    def render(value: str) -> str:
        from arci.schema import GateDecision, Manifest
        from arci.suite_schema import SuiteDecision, SuiteManifest

        manifest = (
            m.model_copy(update={"baseline": m.baseline.model_copy(update={"label": value})})
            if field == "label"
            else m
        )
        decision = d.model_copy(update={"prior_runs": (value,)}) if field == "prior" else d
        observed = (
            [t.model_copy(update={"failure_detail": value}) for t in trials]
            if field == "detail"
            else trials
        )
        if field == "fault":
            c = manifest.conditions[0]
            faults = (FaultSpec(name=value, bucket=Bucket.FALSIFY),)
            manifest = manifest.model_copy(
                update={
                    "conditions": (
                        Condition(condition_id=c.condition_id, faults=faults),
                        *manifest.conditions[1:],
                    )
                }
            )
        if isinstance(manifest, SuiteManifest) and isinstance(decision, SuiteDecision):
            return render_suite_html(manifest, decision, observed)
        assert isinstance(manifest, Manifest) and isinstance(decision, GateDecision)
        return render_html(manifest, decision, observed)

    before, after = Document(render("plain")), Document(render(attack))
    assert Counter(before.tags) == Counter(after.tags)
    assert len(before.rows) == len(after.rows)
    assert attack not in "".join(after.text)
    assert f"\\u{ord(separator):04x}" in "".join(after.text)
    assert after.tags.count("h1") == 1


def test_hard_block_reason_is_not_statistical() -> None:
    m = suite_manifest()
    ts = round_trials(m, 1, [0] * 20, hard=(3,))
    d = decide_suite(m, ts)
    page = render_suite_html(m, d, ts)
    parsed = Document(page)
    assert "The candidate broke a hard invariant; this BLOCK is not a statistical finding." in page
    assert "candidate hard violation" in page
    assert ["Candidate hard violations", "1"] in parsed.rows
    m, ts = evidence("BLOCK")
    page = render_suite_html(m, decide_suite(m, ts), ts)
    assert (
        "On the suite mean, the candidate&#x27;s success is lower than the baseline&#x27;s "
        "by more than the registered margin" in page
    )
    assert "this BLOCK is not a statistical finding" not in page


def test_details_group_by_task_condition_arm_and_count() -> None:
    m, ts = evidence("BLOCK")
    changed = [t.model_copy(update={"failure_detail": "same detail"}) for t in ts]
    parsed = Document(render_suite_html(m, decide_suite(m, ts), changed))
    groups = Counter((t.task_id, t.condition_id, t.arm) for t in changed)
    for key, count in groups.items():
        assert [*key, "same detail", str(count)] in parsed.rows


def test_plain_presentation_empty_digest_and_named_tables() -> None:
    m, ts = evidence("BLOCK")
    html = render_suite_html(m, decide_suite(m, ts), ts)
    doc = Document(html)
    assert ["Fixtures digest", "none recorded"] in doc.rows
    captions = html.count("<caption>")
    names = re.findall(r'role="region" aria-label="([^"]+)"', html)
    assert len(names) == len(set(names)) == captions == doc.tags.count("table")
    m1, ts1 = v1_evidence()
    for page in (html, render_html(m1, decide(m1, ts1), ts1)):
        assert not any(token in " ".join(Document(page).text) for token in ("**", "`", "<br>"))


def test_phone_width_long_heading_wraps() -> None:
    m, ts = evidence("BLOCK")
    m = m.model_copy(update={"suite_id": "a" * 64})
    html = render_suite_html(m, decide_suite(m, ts), ts)
    assert "<h2>Suite " + "a" * 64 + "</h2>" in html
    assert "h1, h2, p, td, th, li, caption { overflow-wrap: anywhere; }" in html


@pytest.mark.parametrize("kind", ["missing", "manifest", "trials"])
def test_load_error_writes_html(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], kind: str
) -> None:
    store = store_at(tmp_path / "runs", "BLOCK").run_dir
    if kind == "missing":
        store = tmp_path / "absent<script>"
    else:
        (store / ("manifest.json" if kind == "manifest" else "trials.jsonl")).write_text("<script>")
    out = tmp_path / "error.html"
    assert main(["report", str(store), "--format", "html", "--out", str(out)]) == 3
    parsed = Document(out.read_text())
    assert "VERDICT: ERROR (exit 3)" in " ".join(parsed.text)
    assert "Report unavailable" in " ".join(parsed.text)
    assert capsys.readouterr().out == ""
    assert main(["report", str(store), "--format", "html"]) == 3
    assert capsys.readouterr().out == out.read_text()


@pytest.mark.parametrize(
    "payload",
    [
        '<meta http-equiv="refresh" content="0;url=next.html">',
        '<svg><use xlink:href="sprite.svg#a"></use></svg>',
        '<video poster="x.png"></video>',
        '<table background="x.png"></table>',
        '<style>image-set("x.png" 1x)</style>',
        '<p style="background:url&#40;x.png&#41;">',
        "<style>\\75 rl(x.png)</style>",
        '<button formaction="next.html">',
        '<svg><feImage xlink:href="x.png"></feImage></svg>',
        "<script></script>",
        '<img src="//evil.test">',
        '<style>@import "x.css";</style>',
    ],
)
def test_self_containment_guard_rejects_fetch_forms(payload: str) -> None:
    with pytest.raises(AssertionError):
        Document(payload)
