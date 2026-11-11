"""P4c regressions for stored text, load failures and phone typography."""

import re
from pathlib import Path

import pytest

from arci.cli import main
from arci.gate import decide
from arci.html_report import render_html, render_suite_html, suite_meaning
from arci.schema import Condition
from arci.suite_gate import decide_suite
from tests.unit.html_report.test_html_report import Document, v1_evidence
from tests.unit.suite_report.test_reports import evidence


@pytest.mark.parametrize("schema", ["arci/0.5", "arci-suite/1"])
def test_deep_manifest_writes_error_page(tmp_path: Path, schema: str) -> None:
    (tmp_path / "manifest.json").write_text(
        '{"schema_version":"' + schema + '","task":' + "[" * 10000 + "0" + "]" * 10000 + "}"
    )
    output = tmp_path / "error.html"
    assert main(["report", str(tmp_path), "--format", "html", "--out", str(output)]) == 3
    assert "VERDICT: ERROR (exit 3)" in output.read_text()
    assert "Report unavailable" in output.read_text()


def test_stored_ids_never_appear_in_headings() -> None:
    marker = "VERDICT-PASS-stored-id"
    m, ts = evidence("BLOCK")
    suite = render_suite_html(m.model_copy(update={"suite_id": marker}), decide_suite(m, ts), ts)
    v1, trials = v1_evidence()
    decision = decide(v1, trials)
    decision = decision.model_copy(
        update={
            "conditions": tuple(
                c.model_copy(update={"condition_id": marker}) for c in decision.conditions
            )
        }
    )
    page = render_html(
        v1.model_copy(
            update={"experiment_id": marker, "conditions": (Condition(condition_id=marker),)}
        ),
        decision,
        trials,
    )
    for html in (suite, page):
        headings = re.findall(r"<h[12][^>]*>(.*?)</h[12]>", html)
        assert all(marker not in heading for heading in headings)
        assert marker in " ".join(Document(html).text)


def test_wrap_is_limited_to_long_values() -> None:
    m, ts = evidence("BLOCK")
    m = m.model_copy(update={"baseline": m.baseline.model_copy(update={"label": "x" * 64})})
    page = render_suite_html(m, decide_suite(m, ts), ts)
    css = page.split("<style>")[1].split("</style>")[0]
    rules = re.findall(r"([^{}]+)\{([^{}]+)\}", css)
    anywhere = [selector.strip() for selector, body in rules if "overflow-wrap: anywhere" in body]
    assert anywhere == [".long-value"]
    assert '<td class="long-value">' + "x" * 64 + "</td>" in page
    assert "<td>baseline</td>" in page and "<td>candidate</td>" in page


def test_statistical_block_sentence_has_full_stop() -> None:
    m, ts = evidence("BLOCK")
    assert suite_meaning(decide_suite(m, ts)).endswith("registered margin.")
