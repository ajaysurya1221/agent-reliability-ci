from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from random import Random

import pytest
from evaluate import (
    RATES,
    REGIMES,
    SCHEMA,
    STREAMS,
    Cell,
    GateSummary,
    Summary,
    evaluate,
    metric_counts,
    rate,
    read_evaluation,
)
from gates import CAP, GATES, OUTCOMES, Counts, Decision, decisions
from simulate import (
    MASTER,
    Key,
    Tallies,
    agreement,
    canonical,
    draw_rounds,
    journal_entry,
    markdown,
    seed,
    write_design,
    write_outputs,
)

from arci.stats import clopper_pearson_tail


def test_seed_vector_and_domains() -> None:
    key = Key("primary", "I", 42, 17)
    assert f"{seed(key, 'pairs'):064x}" == (
        "7df1792728cef0531096b179b96f643c88492e8704e88f90a88e0ba73e605a70"
    )
    keys = [
        key,
        key._replace(panel="outage"),
        key._replace(regime="P"),
        key._replace(pc=43),
        key._replace(replicate=18),
    ]
    assert len({seed(k, tag) for k in keys for tag in ("pairs", "bootstrap", "outage")}) == 15


def test_pair_mapping_and_round_outage() -> None:
    def unused(_: int) -> int:
        raise AssertionError("unexpected draw")

    draws = iter([94, 29, 95, 29, 94, 30, 95, 30])
    assert draw_rounds(30, "I", "primary", lambda _: next(draws), unused, tasks=4, rounds=1) == (
        Counts(1, 1, 1, 1),
    )
    draws = iter([29, 30, 94, 95])
    outages = iter([4, 5])
    assert draw_rounds(
        30, "P", "outage", lambda _: next(draws), lambda _: next(outages), tasks=4, rounds=2
    ) == (Counts(4, 0, 0, 0), Counts(1, 0, 2, 1))
    assert agreement(Fraction(3, 4), Fraction(1, 4), "I") == Fraction(3, 8)
    assert agreement(Fraction(3, 4), Fraction(1, 4), "P") == Fraction(1, 2)


@pytest.mark.parametrize(("x", "n"), [(0, 20), (1, 9), (6, 10), (19, 20), (20, 20)])
def test_cp_against_exact_binomial_inversion(x: int, n: int) -> None:
    assert rate(x, n)[2:] == pytest.approx(clopper_pearson_tail(x, n, 0.025), abs=2e-14, rel=0)


def test_journal_resume_torn_tail_and_corruption(tmp_path: Path) -> None:
    path = tmp_path / "journal"
    row = decisions((Counts(20, 0, 0, 0),) * 20, Random(7))
    key = Key("outage", "P", 30, 0)

    def unused(_: Key) -> dict[str, Decision]:
        raise AssertionError("committed row regenerated")

    with path.open("a+b") as f:
        assert journal_entry(f, key, "hand", lambda _: row) == row
        f.write(b'{"torn"')
    with path.open("a+b") as f:
        f.seek(0)
        assert journal_entry(f, key, "hand", unused) == row
        assert journal_entry(f, key._replace(replicate=1), "hand", lambda _: row) == row
    lines = path.read_bytes().splitlines()
    assert len(lines) == 2
    with path.open("rb") as f, pytest.raises(ValueError, match="mismatch"):
        journal_entry(f, key, "different experiment", unused)
    record = json.loads(lines[0])
    record["gates"]["arci"][1] = 400
    path.write_bytes(canonical(record) + b"\n")
    with path.open("rb") as f, pytest.raises(ValueError, match="checksum"):
        journal_entry(f, key, "hand", unused)


def test_metrics_on_handmade_streams() -> None:
    tallies = Tallies()
    for c in (Counts(0, 20, 0, 0), Counts(0, 0, 20, 0), Counts(0, 0, 2, 18)):
        tallies.add(decisions((c,) * 20, Random(42)))
    cell = tallies.cell("primary", "P", 85, None)
    g = cell.gates["arci"]
    assert g.mean_pairs == (20 + 20 + 400) / 3 and g.median_pairs == 20
    assert g.rates["wrong_PASS"].events == g.rates["wrong_BLOCK"].events == 1
    assert g.rates["decided"].events == 2
    assert "wrong_PASS" not in cell.gates["mcnemar"].rates
    assert "33.333 [" in markdown([cell], "primary")
    counts = {v: 1 for v in OUTCOMES}
    assert metric_counts(counts, "arci", "outage", 85)["wrong_PASS"] == 0


def hand_summary() -> Summary:
    # Fabricated counts for evaluator truth tables, never sampled outcomes.
    cells = []
    for pc in RATES:
        for r in REGIMES:
            counts: dict[str, int] = dict.fromkeys(OUTCOMES, 0)
            verdict = "BLOCK" if pc < 85 else "INCONCLUSIVE" if pc == 85 else "PASS"
            counts[verdict] = STREAMS
            gates = {}
            for gate in GATES:
                cost = 80 if gate == "arci" and pc != 85 else CAP
                gates[gate] = GateSummary(
                    rates={
                        k: rate(v, STREAMS)
                        for k, v in metric_counts(counts, gate, "primary", pc).items()
                    },
                    mean_pairs=cost,
                    median_pairs=cost,
                    pair_counts={str(cost): STREAMS},
                )
            cells.append(
                Cell(
                    panel="primary",
                    regime=r,
                    candidate_percent=pc,
                    streams=STREAMS,
                    gates=gates,
                    exact_plan=None,
                    crosscheck=None,
                )
            )
    return Summary(format=SCHEMA, run_id="hand", master_seed=MASTER, cells=cells)


def test_summary_only_decision_and_stop(tmp_path: Path) -> None:
    summary = hand_summary()
    path = tmp_path / "summary.json"
    path.write_text(summary.model_dump_json())
    result = read_evaluation(path)
    assert all(result[k] for k in ("C1", "C2", "C3"))
    assert not result["stop"]
    assert len(result["comparisons"]) == 12
    cell = summary.cells[0]
    # A single clear cell with insufficient savings against the CS defeats C3.
    rival = cell.gates["cs_margin"]
    rival.mean_pairs = rival.median_pairs = 60
    rival.pair_counts = {"60": STREAMS}
    result = evaluate(summary)
    assert not result["C3"] and result["stop"]
    assert "no support for continuing" in result["conclusion"]
    # Boundary errors in either direction alone must fail C1.
    bound = next(c for c in summary.cells if c.candidate_percent == 85)
    for name in ("PASS", "BLOCK"):
        counts: dict[str, int] = dict.fromkeys(OUTCOMES, 0)
        counts[name], counts["INCONCLUSIVE"] = 400, 9600
        bound.gates["arci"].rates = {
            k: rate(v, STREAMS) for k, v in metric_counts(counts, "arci", "primary", 85).items()
        }
        assert not evaluate(summary)["C1"]
    summary.cells.pop()
    with pytest.raises(ValueError, match="missing"):
        evaluate(summary)


def test_c3_rejects_unproved_savings_and_correctness_deficit() -> None:
    summary = hand_summary()
    stat = summary.cells[0].gates["arci"]
    stat.mean_pairs = stat.median_pairs = 320
    stat.pair_counts = {"320": STREAMS}
    result = evaluate(summary)
    score = next(row for row in result["comparisons"] if row["rival"] == "score_margin")
    assert score["mean_contrast_pairs"] == 0
    assert score["simultaneous_95"][1] > 0 and not result["C3"]
    # Cheap ARCI decisions can still lose too much correctness.
    stat.mean_pairs = stat.median_pairs = 80
    stat.pair_counts = {"80": STREAMS}
    counts = {"PASS": 501, "BLOCK": STREAMS - 501, "INCONCLUSIVE": 0, "ERROR": 0}
    stat.rates = {
        k: rate(v, STREAMS) for k, v in metric_counts(counts, "arci", "primary", 75).items()
    }
    result = evaluate(summary)
    assert result["C2"] and not result["C3"]
    # C2 is inclusive at 80%, even with a counting error in the complementary direction.
    for correct in (8000, 7999):
        counts["BLOCK"], counts["PASS"] = correct, STREAMS - correct
        stat.rates = {
            k: rate(v, STREAMS) for k, v in metric_counts(counts, "arci", "primary", 75).items()
        }
        assert evaluate(summary)["C2"] == (correct == 8000)


def test_faster_cs_cannot_hide_correctness_deficit_against_tango() -> None:
    summary = hand_summary()
    cell = next(c for c in summary.cells if (c.regime, c.candidate_percent) == ("I", 75))
    # Tango is 100% correct at 400 pairs. The CS decides only 1% of streams,
    # but saves 0.2 pairs on average. ARCI and the bootstrap are 90% correct.
    for gate, correct in (("arci", 9000), ("bootstrap_margin", 9000), ("cs_margin", 100)):
        counts = {"PASS": 0, "BLOCK": correct, "INCONCLUSIVE": STREAMS - correct, "ERROR": 0}
        cell.gates[gate].rates = {
            k: rate(v, STREAMS) for k, v in metric_counts(counts, gate, "primary", 75).items()
        }
    arci, cs = cell.gates["arci"], cell.gates["cs_margin"]
    arci.pair_counts = {"80": 9000, "400": 1000}
    arci.mean_pairs, arci.median_pairs = 112, 80
    cs.pair_counts = {"380": 100, "400": 9900}
    cs.mean_pairs = 399.8

    result = evaluate(summary)
    failed = [
        row for row in result["comparisons"] if row["calibrated"] and not row["meets_contrast"]
    ]
    assert [(row["cell"], row["rival"]) for row in failed] == [(["I", 75], "score_margin")]
    assert failed[0]["simultaneous_95"][1] <= 0
    assert failed[0]["correct_rate_difference"] == -0.10
    assert result["C1"] and result["C2"] and not result["C3"] and result["stop"]


def test_no_eligible_rival_drops_claim_and_stress_is_ignored() -> None:
    summary = hand_summary()
    cell = next(c for c in summary.cells if c.candidate_percent == 85)
    stress = cell.model_copy(deep=True, update={"panel": "outage"})
    summary.cells.append(stress)
    counts = {"PASS": 401, "BLOCK": 0, "INCONCLUSIVE": 9599, "ERROR": 0}
    for gate in ("score_margin", "bootstrap_margin", "cs_margin"):
        cell.gates[gate].rates = {
            k: rate(v, STREAMS) for k, v in metric_counts(counts, gate, "primary", 85).items()
        }
    result = evaluate(summary)
    assert result["C1"] and not result["calibrated_rivals"]
    assert result["efficiency_claim"] == "dropped" and not result["stop"]


def test_cp_at_publication_denominator() -> None:
    # Independently calculated using the released integer binomial-tail implementation.
    assert rate(100, 10000)[2:] == pytest.approx(
        (0.008143596567611065, 0.012149504886061608), abs=3e-13, rel=0
    )
    assert rate(5000, 10000)[2:] == pytest.approx(
        (0.49015138058998053, 0.5098486194100196), abs=3e-13, rel=0
    )


def test_handmade_reports_and_output_digests(tmp_path: Path) -> None:
    summary = hand_summary()
    cell = summary.cells[0].model_copy(deep=True, update={"panel": "outage"})
    summary.cells.append(cell)
    for file in ("planner-manifest.json", "fixed-rule.json", "results.jsonl"):
        write_design(tmp_path / file, "{}\n")
    write_outputs(tmp_path, summary)
    report = (tmp_path / "results.md").read_text()
    for pc in (75, 95):
        for regime in REGIMES:
            for rival in ("score_margin", "bootstrap_margin", "cs_margin"):
                assert f"| {regime} | {pc}% | {rival} |" in report
    assert "descriptive" in (tmp_path / "stress.md").read_text()
    assert json.loads((tmp_path / "criteria.json").read_bytes()) == read_evaluation(
        tmp_path / "summary.json"
    )
    for line in (tmp_path / "digests.sha256").read_text().splitlines():
        digest, name = line.split("  ")
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == digest
    with pytest.raises(ValueError, match="different design"):
        write_design(tmp_path / "fixed-rule.json", "replaced\n")
    assert (tmp_path / "fixed-rule.json").read_text() == "{}\n"
