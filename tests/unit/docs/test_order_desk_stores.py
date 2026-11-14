"""The committed order-desk study stores re-derive their published decisions.

Loads each committed suite store through the same public functions the CLI
uses (`load_suite_run`, `decide_suite`), and checks the re-derived decision
against the committed `decision.json` byte for byte (as sealed records), plus
the headline counts and wealth figures quoted in
`docs/results/order-desk-study.md`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from arci.suite_gate import decide_suite
from arci.suite_schema import SuiteDecision
from arci.suite_storage import load_suite_run

REPO = Path(__file__).resolve().parents[3]
STUDY_DOC = REPO / "docs" / "results" / "order-desk-study.md"
STORES_DIR = REPO / "docs" / "results" / "order-desk-study"


def _store_dir(run_label: str, prefix: str) -> Path:
    """The one subdirectory under run-N that starts with the suite's own name."""
    (run_dir,) = sorted((STORES_DIR / run_label).glob(f"{prefix}*"))
    return run_dir


RUN_1 = _store_dir("run-1", "order-desk-gemma4-12b-vs-qwen3.5-4b@")
RUN_2 = _store_dir("run-2", "order-desk-gemma4-12b-vs-qwen3.5-4b-recoverable@")

# (store, expected verdict, stopped_at_round, baseline successes, candidate successes)
CASES = (
    (RUN_1, "BLOCK", 1, 96, 96, 70),
    (RUN_2, "INCONCLUSIVE", 5, 480, 480, 428),
)


def _stored_decision(store: Path) -> SuiteDecision:
    return SuiteDecision.model_validate_json((store / "decision.json").read_text(encoding="utf-8"))


def _rederived_decision(store: Path) -> SuiteDecision:
    manifest, trials = load_suite_run(store)
    return decide_suite(manifest, trials)


@pytest.mark.parametrize(
    ("store", "verdict", "stopped_at_round", "pairs", "baseline_ok", "candidate_ok"),
    CASES,
    ids=("run-1", "run-2"),
)
def test_rederived_decision_matches_store(
    store: Path,
    verdict: str,
    stopped_at_round: int,
    pairs: int,
    baseline_ok: int,
    candidate_ok: int,
) -> None:
    stored = _stored_decision(store)
    rederived = _rederived_decision(store)

    # Full equality of the sealed decision: covers verdict, stopping round,
    # per-round and per-cell counts, and the sealed hash in one assertion.
    assert rederived == stored
    assert rederived.validate_seal()
    assert rederived.record_sha256 == stored.record_sha256

    assert rederived.verdict.value == verdict
    assert rederived.stopped_at_round == stopped_at_round

    baseline_successes = sum(cell.baseline_successes for cell in rederived.cells)
    candidate_successes = sum(cell.candidate_successes for cell in rederived.cells)
    total_pairs = sum(cell.pairs for cell in rederived.cells)
    assert total_pairs == pairs
    assert baseline_successes == baseline_ok
    assert candidate_successes == candidate_ok


def test_tampering_with_trials_breaks_the_match(tmp_path: Path) -> None:
    """A one-byte edit to a committed trials.jsonl must flip the re-derived verdict."""
    copy_dir = tmp_path / RUN_1.name
    copy_dir.mkdir()
    for name in ("manifest.json", "trials.jsonl", "events.jsonl", "decision.json"):
        (copy_dir / name).write_bytes((RUN_1 / name).read_bytes())

    stored = _stored_decision(copy_dir)
    rederived = _rederived_decision(copy_dir)
    assert rederived == stored  # sanity: the untouched copy matches

    trials_path = copy_dir / "trials.jsonl"
    lines = trials_path.read_text(encoding="utf-8").splitlines(keepends=True)
    first_trial = json.loads(lines[0])
    assert first_trial["arm"] == "baseline"
    # Flip one trial's recorded outcome; its record_sha256 no longer matches
    # its own content, so the seal check must fail the whole trial set.
    first_trial["outcome"] = "FAIL" if first_trial["outcome"] != "FAIL" else "PASS"
    lines[0] = json.dumps(first_trial) + "\n"
    trials_path.write_text("".join(lines), encoding="utf-8")

    # load_suite_run itself raises on an invalid trial seal.
    with pytest.raises(ValueError, match="trial seal is invalid"):
        load_suite_run(copy_dir)


_WEALTH_ROW = re.compile(
    r"\|\s*BLOCK wealth, PASS wealth \(threshold 40\)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|"
)


def _doc_wealth_cells() -> tuple[str, str]:
    text = STUDY_DOC.read_text(encoding="utf-8")
    match = _WEALTH_ROW.search(text)
    assert match is not None, "expected a 'BLOCK wealth, PASS wealth' row in order-desk-study.md"
    return match.group(1), match.group(2)


def _matches_displayed(value: float, displayed: str) -> None:
    places = len(displayed.split(".")[1]) if "." in displayed else 0
    assert round(value, places) == round(float(displayed), places), (value, displayed)


@pytest.mark.parametrize(
    ("store", "doc_cell_index"),
    ((RUN_1, 0), (RUN_2, 1)),
    ids=("run-1", "run-2"),
)
def test_wealth_figures_match_doc(store: Path, doc_cell_index: int) -> None:
    decision = _rederived_decision(store)
    last_round = decision.history[-1]
    block_wealth = float(last_round.block_wealth)
    pass_wealth = float(last_round.pass_wealth)

    cell_text = _doc_wealth_cells()[doc_cell_index]
    block_text, pass_text = (part.strip() for part in cell_text.split(","))
    _matches_displayed(block_wealth, block_text)
    _matches_displayed(pass_wealth, pass_text)
