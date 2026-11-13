"""Suite-renderer wiring: JSON key placement, Markdown/HTML section placement.

From the "Wiring" section of R1-tool-outcomes.md. Fixtures use the acceptance suite
helpers (tests/acceptance/suite_helpers.py), the same pattern tests/unit/suite_report/
test_reports.py and tests/unit/html_report/test_html_report.py use; src/arci/report.py,
src/arci/suite_report.py and src/arci/html_report.py themselves are not read, only
imported and called.
"""

from __future__ import annotations

import json
import re

from arci.html_report import render_suite_html
from arci.report import tool_outcomes
from arci.suite_gate import decide_suite
from arci.suite_report import render_suite_markdown
from tests.acceptance.suite_helpers import round_trials, suite_manifest

# Pre-existing (v1) heading text, which the contract requires to be unchanged by this
# feature ("v1 output must not change at all"). Confirmed structurally, not pinned on
# numbers, by locating it as the heading that immediately follows the prior-runs section
# header in a suite report produced before this feature existed.
FAULT_HEADING = "## Fault accounting"
TOOL_HEADING = "## Tool outcomes (descriptive)"


def _evidence():
    manifest = suite_manifest(max_rounds=4, max_errored_pairs=0, prior_runs=("earlier-run",))
    trials = round_trials(manifest, 1, [0] * 20)
    decision = decide_suite(manifest, trials)
    return manifest, decision, trials


def test_json_top_level_key_equals_tool_outcomes_and_is_outside_decision() -> None:
    from arci.suite_report import render_suite_json

    manifest, decision, trials = _evidence()
    document = json.loads(render_suite_json(manifest, decision, trials))
    assert "tool_outcomes" in document
    assert document["tool_outcomes"] == tool_outcomes(trials)
    assert isinstance(document["decision"], dict)
    assert "tool_outcomes" not in document["decision"]


def test_markdown_heading_sits_between_fault_accounting_and_prior_runs() -> None:
    manifest, decision, trials = _evidence()
    report = render_suite_markdown(manifest, decision, trials)
    headings = re.findall(r"^(## .+)$", report, flags=re.MULTILINE)
    fault_idx = headings.index(FAULT_HEADING)
    assert headings[fault_idx + 1] == TOOL_HEADING
    prior_heading = headings[fault_idx + 2]
    assert prior_heading.startswith("## Prior runs")


def test_markdown_section_numbers_match_tool_outcomes() -> None:
    manifest, decision, trials = _evidence()
    report = render_suite_markdown(manifest, decision, trials)
    computed = tool_outcomes(trials)
    base = computed["arms"][0]
    assert (
        f"| baseline | {base['trials']} | {base['uninjected_failure_trials']} "
        f"| {base['uninjected_then_passed']} | {base['uninjected_then_not_passed']} |"
    ) in report


def test_html_contains_tool_outcomes_heading_between_fault_accounting_and_details() -> None:
    manifest, decision, trials = _evidence()
    html = render_suite_html(manifest, decision, trials)
    h2s = re.findall(r"<h2[^>]*>(.*?)</h2>", html)
    fault_idx = h2s.index("Fault accounting")
    assert h2s[fault_idx + 1] == "Tool outcomes (descriptive)"
    assert "Tool outcomes" not in h2s[fault_idx + 1].replace("Tool outcomes (descriptive)", "")
    # The section after it must not itself be headed with a tool name (no tool name in a
    # heading, only in table cells).
    following = h2s[fault_idx + 2]
    assert "<" not in following and ">" not in following


def test_html_numbers_match_tool_outcomes_for_a_distinctive_fixture() -> None:
    manifest, decision, trials = _evidence()
    html = render_suite_html(manifest, decision, trials)
    computed = tool_outcomes(trials)
    start = html.index("Tool outcomes (descriptive)")
    end = html.index("<h2", start + 1) if "<h2" in html[start + 1 :] else len(html)
    section = html[start:end]
    base = computed["arms"][0]
    cand = computed["arms"][1]
    assert str(base["trials"]) in section
    assert str(cand["trials"]) in section


def test_html_escapes_a_tool_name_with_a_script_tag() -> None:
    from arci.schema import Outcome, Termination, TrialEnvelope
    from tests.unit.tool_outcomes_blind.helpers import start as start_event

    manifest, _decision, trials = _evidence()
    poisoned_name = "<script>alert(1)</script>"
    extra = TrialEnvelope.create(
        spec_sha256="0" * 64,
        experiment_id=manifest.experiment_id,
        trial_id="poison-1",
        pair_id="poison-1",
        arm="baseline",
        variant="v",
        task_id=trials[0].task_id,
        condition_id=trials[0].condition_id,
        seed=0,
        outcome=Outcome.PASS,
        termination=Termination.COMPLETED,
        events=(start_event("poison-1", 0, poisoned_name),),
    )
    poisoned_trials = (*trials, extra)
    poisoned_decision = decide_suite(manifest, poisoned_trials)
    html = render_suite_html(manifest, poisoned_decision, poisoned_trials)
    assert poisoned_name not in html
    assert "Tool outcomes (descriptive)" in html
