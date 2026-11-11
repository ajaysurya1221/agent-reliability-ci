"""The suite gate: round verdicts, errored pairs, store checks, sealed decisions. FROZEN.

Every expectation is derived here from contract section 5 (`plan/exec/v2/tasks/P1-CONTRACT.md`):
wealth from `reference_wealth` (exact Fractions), digests from `arci.hashing.hash_record`, the
display text from the section 4 formula by integer arithmetic. Numeric literals were checked
with an independent Fraction computation and are named where they appear.
"""

from __future__ import annotations

import random
import time
import warnings
from collections.abc import Collection, Sequence
from fractions import Fraction
from functools import cache
from typing import Any

import pytest

from arci.hashing import hash_record
from arci.schema import (
    EXIT_CODES,
    ContractResult,
    Outcome,
    TrialEnvelope,
    TrialSpec,
    Verdict,
    Violation,
    digest_payload,
)
from arci.suite_gate import decide_suite, evaluate_rounds, replay_suite_decision
from arci.suite_schedule import build_suite_round
from arci.suite_schema import (
    SuiteCellStats,
    SuiteDecision,
    SuiteManifest,
    SuiteRoundDecision,
    SuiteTask,
)
from tests.acceptance.helpers import reseal
from tests.acceptance.suite_helpers import (
    CONDITIONS,
    HARD,
    cell_keys,
    envelope,
    reference_wealth,
    round_trials,
    suite_manifest,
)

pytestmark = [
    pytest.mark.acceptance,
    # Records built with model_copy hold wrong-typed values on purpose; dumping them warns.
    pytest.mark.filterwarnings("ignore:Pydantic serializer warnings:UserWarning"),
]

ALPHA = Fraction(1, 20)
DELTA = Fraction(1, 10)
STAKES = (Fraction(1, 4), Fraction(1, 2))
THRESHOLD = 2 / ALPHA
N = 20  # cells of the default suite_manifest: 5 tasks x 4 conditions
ZEROS = (0,) * N
PLUS = (1,) * N
MINUS = (-1,) * N
ALTERNATING = (1, -1) * (N // 2)
SOFT = Violation(invariant="max_tool_calls", severity="soft", detail="many calls")

REASON_ERRORED = "errored pairs exceed max_errored_pairs"
REASON_HARD = "candidate hard violation"
REASON_PASS = "non-inferiority established"
REASON_BLOCK = "regression established"
REASON_NONE = "no test crossed"
MANIFEST_INVALID = "manifest values invalid"
MANIFEST_SEAL = "manifest seal invalid"
RULE_DIGEST = "suite rule digest mismatch"
PLAN_INVALID = "suite plan invalid"
TRIAL_INVALID = "trial values invalid"
SCHEDULE = "trial schedule mismatch"
TRIAL_SEAL = "trial seal invalid"
WHOLE_ROUNDS = "trial set is not a whole number of rounds"
AFTER_STOP = "trials stored after the stopping round"
NO_DECISION = "stopped without a decision"

# One round's plan: (differences per cell, cells whose candidate is ERROR, cells with a hard
# violation on the candidate), with the meaning of suite_helpers.round_trials.
Row = tuple[tuple[int, ...], frozenset[int], frozenset[int]]


def _row(diffs: Sequence[int], errored: Collection[int] = (), hard: Collection[int] = ()) -> Row:
    return tuple(diffs), frozenset(errored), frozenset(hard)


# --- independent oracles ---------------------------------------------------------------------


def _digest(trials: Sequence[TrialEnvelope]) -> str:
    """Contract 2/5: hash_record({"trials": sorted record_sha256})."""
    return hash_record({"trials": sorted(t.record_sha256 for t in trials)})


def _round_of(trial: TrialEnvelope) -> int:
    """Contract 3, ids: trial_id = f"r{round:06d}:{task}:{condition}:{arm}"."""
    return int(trial.trial_id[1:7])


def _wealth_text(value: Fraction) -> str:
    """Contract 4, wealth_text: truncated six significant digits, integer arithmetic."""
    assert value > 0
    e = 0
    while Fraction(10) ** (e + 1) <= value:
        e += 1
    while Fraction(10) ** e > value:
        e -= 1
    m = (value / Fraction(10) ** (e - 5)).__floor__()
    return f"{m // 100000}.{m % 100000:05d}e{e:+03d}"


def _scored(minus: int, zero: int, plus: int, errored: int) -> tuple[Fraction, Fraction]:
    """Contract 4, scored_wealth: errored is -1 for PASS wealth, +1 for BLOCK wealth."""
    pass_wealth = reference_wealth(minus + errored, zero, plus, ALPHA, DELTA, STAKES)[0]
    block_wealth = reference_wealth(minus, zero, plus + errored, ALPHA, DELTA, STAKES)[1]
    return pass_wealth, block_wealth


def _expected_verdict(
    counts: tuple[int, int, int, int], hard: int, max_errored: int
) -> tuple[Verdict, tuple[str, ...], bool, bool]:
    """Contract 5, round verdict, rules 1 to 6 in order, at the default rule."""
    pass_wealth, block_wealth = _scored(*counts)
    pass_crossed = pass_wealth >= THRESHOLD
    block_crossed = block_wealth >= THRESHOLD
    if counts[3] > max_errored:
        return Verdict.ERROR, (REASON_ERRORED,), pass_crossed, block_crossed
    if hard > 0:
        return Verdict.BLOCK, (REASON_HARD,), pass_crossed, block_crossed
    if pass_crossed and block_crossed:
        return Verdict.ERROR, ("both tests crossed",), pass_crossed, block_crossed
    if pass_crossed:
        return Verdict.PASS, (REASON_PASS,), pass_crossed, block_crossed
    if block_crossed:
        return Verdict.BLOCK, (REASON_BLOCK,), pass_crossed, block_crossed
    return Verdict.INCONCLUSIVE, (REASON_NONE,), pass_crossed, block_crossed


def _cumulative(rows: Sequence[Row], through: int) -> tuple[tuple[int, int, int, int], int]:
    """(minus, zero, plus, errored) and candidate hard violations over rounds 1..through."""
    minus = zero = plus = errored = hard = 0
    for diffs, err, hrd in rows[:through]:
        for i, d in enumerate(diffs):
            if i in err:
                errored += 1
            elif d == -1:
                minus += 1
            elif d == 0:
                zero += 1
            else:
                plus += 1
        hard += len(hrd)
    return (minus, zero, plus, errored), hard


def _check_round(
    rd: SuiteRoundDecision,
    r: int,
    counts: tuple[int, int, int, int],
    hard: int,
    max_errored: int,
    trials: Sequence[TrialEnvelope],
    n_cells: int = N,
) -> None:
    """Every field of one SuiteRoundDecision against the oracles (contract 2 and 5)."""
    verdict, reasons, pass_crossed, block_crossed = _expected_verdict(counts, hard, max_errored)
    pass_wealth, block_wealth = _scored(*counts)
    assert rd.round == r
    assert rd.pairs == r * n_cells
    assert (rd.counts.minus, rd.counts.zero, rd.counts.plus, rd.counts.errored) == counts
    assert rd.candidate_hard_violations == hard
    # Contract 8 item 3: the round digest covers the trials of that round only.
    assert rd.trials_sha256 == _digest([t for t in trials if _round_of(t) == r])
    assert rd.pass_wealth == _wealth_text(pass_wealth)
    assert rd.block_wealth == _wealth_text(block_wealth)
    assert rd.pass_crossed is pass_crossed
    assert rd.block_crossed is block_crossed
    assert rd.verdict is verdict
    assert rd.reasons == reasons


def _check_history(
    history: Sequence[SuiteRoundDecision],
    rows: Sequence[Row],
    max_errored: int,
    trials: Sequence[TrialEnvelope],
) -> None:
    for r, rd in enumerate(history, start=1):
        counts, hard = _cumulative(rows, r)
        _check_round(rd, r, counts, hard, max_errored, trials)


def _expected_cells(m: SuiteManifest, rows: Sequence[Row]) -> list[tuple[object, ...]]:
    """Contract 2, SuiteCellStats, from the row plan and round_trials' outcome rules."""
    out: list[tuple[object, ...]] = []
    for i, (task_id, condition_id) in enumerate(cell_keys(m)):
        base = cand = minus = zero = plus = errored = hard = 0
        for diffs, err, hrd in rows:
            d = diffs[i]
            base += d != 1  # the baseline PASSes unless d = +1, even when its partner errored
            if i in err:
                errored += 1
            else:
                cand += d != -1
                minus += d == -1
                zero += d == 0
                plus += d == 1
            hard += i in hrd
        out.append(
            (task_id, condition_id, len(rows), base, cand, (minus, zero, plus, errored), hard)
        )
    return out


def _cells(decision: SuiteDecision) -> list[tuple[object, ...]]:
    return [
        (
            c.task_id,
            c.condition_id,
            c.pairs,
            c.baseline_successes,
            c.candidate_successes,
            (c.counts.minus, c.counts.zero, c.counts.plus, c.counts.errored),
            c.candidate_hard_violations,
        )
        for c in decision.cells
    ]


def _rational(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


# --- builders --------------------------------------------------------------------------------


def _store(m: SuiteManifest, rows: Sequence[Row]) -> tuple[TrialEnvelope, ...]:
    out: list[TrialEnvelope] = []
    for r, (diffs, err, hrd) in enumerate(rows, start=1):
        out.extend(round_trials(m, r, diffs, errored=err, hard=hrd))
    return tuple(out)


@cache
def _m20() -> SuiteManifest:
    """20 cells, max_rounds 20, max_errored_pairs 4."""
    return suite_manifest()


@cache
def _m4(max_errored: int = 4) -> SuiteManifest:
    """20 cells, max_rounds 4 (the smallest valid budget, contract 4 facts)."""
    return suite_manifest(max_rounds=4, max_errored_pairs=max_errored)


@cache
def _m_err1() -> SuiteManifest:
    """20 cells, max_rounds 20, max_errored_pairs 1."""
    return suite_manifest(max_errored_pairs=1)


ZERO_ROWS = (_row(ZEROS),) * 4


@cache
def _zero_store() -> tuple[TrialEnvelope, ...]:
    """Four rounds of all-zero differences for _m20(): PASS at round 4."""
    return _store(_m20(), ZERO_ROWS)


def _decide(m: SuiteManifest, trials: Sequence[TrialEnvelope]) -> SuiteDecision:
    """decide_suite plus the invariants every decision carries (contract 5)."""
    d = decide_suite(m, trials)
    assert isinstance(d, SuiteDecision)
    assert d.validate_seal()
    assert d.exit_code == EXIT_CODES[d.verdict]
    if d.verdict is Verdict.ERROR:
        assert d.stopped_at_round == 0
        assert d.exit_code == 3
    else:
        assert d.stopped_at_round == len(d.history) >= 1
        assert d.history[-1].verdict is d.verdict
        assert d.reasons == d.history[-1].reasons
    return d


def _assert_check_error(d: SuiteDecision, reasons: tuple[str, ...]) -> None:
    """Contract 5: a failed check gives ERROR with history () and cells ()."""
    assert d.verdict is Verdict.ERROR
    assert d.reasons == reasons
    assert d.history == ()
    assert d.cells == ()


def _assert_mirrors(d: SuiteDecision, m: SuiteManifest) -> None:
    """Contract 5, fields of every decision when check 1 passed."""
    assert d.experiment_id == m.experiment_id
    assert d.manifest_sha256 == m.record_sha256
    assert d.alpha == m.alpha
    assert d.delta == m.delta
    assert d.stakes == tuple(m.stakes)
    assert d.scenario_seeds == m.scenario_seeds
    assert d.max_rounds == m.max_rounds
    assert d.max_errored_pairs == m.max_errored_pairs
    assert d.prior_runs == tuple(m.prior_runs)
    assert d.n_cells == len(m.tasks) * len(m.conditions)
    assert d.threshold == _rational(2 / Fraction(m.alpha))


def _assert_template(d: SuiteDecision) -> None:
    """Contract 5: the fixed template when check 1 failed."""
    assert d.experiment_id == ""
    assert d.manifest_sha256 == ""
    assert d.alpha == ""
    assert d.delta == ""
    assert d.stakes == ()
    assert d.scenario_seeds == ""
    assert d.max_rounds == 0
    assert d.max_errored_pairs == 0
    assert d.prior_runs == ()
    assert d.n_cells == 0
    assert d.threshold == ""
    assert d.stopped_at_round == 0
    assert d.exit_code == 3


def test_oracle_self_check() -> None:
    """Contract 4, wealth_text verified example: 80 pairs of 0 at the defaults is 4.22732e+01."""
    assert _wealth_text(reference_wealth(0, 80, 0, ALPHA, DELTA, STAKES)[0]) == "4.22732e+01"
    assert _rational(THRESHOLD) == "40/1"


# --- round verdict, rules 1 to 6 ----------------------------------------------------------------


def test_rule_6_no_crossing_is_inconclusive() -> None:
    """Contract 5, round verdict rule 6: one round of zeros crosses nothing."""
    m, rows = _m20(), [_row(ZEROS)]
    trials = _store(m, rows)
    history = evaluate_rounds(m, trials)
    assert len(history) == 1
    _check_history(history, rows, 4, trials)
    assert history[0].verdict is Verdict.INCONCLUSIVE
    assert history[0].reasons == (REASON_NONE,)


def test_rule_4_pass_crossing_passes() -> None:
    """Contract 5, rule 4; contract 4 facts: all +1 crosses PASS at 9 pairs, so round 1 of 20."""
    m, rows = _m20(), [_row(PLUS)]
    trials = _store(m, rows)
    history = evaluate_rounds(m, trials)
    _check_history(history, rows, 4, trials)
    assert history[0].verdict is Verdict.PASS and history[0].pass_crossed
    d = _decide(m, trials)
    assert (d.verdict, d.reasons, d.stopped_at_round, d.exit_code) == (
        Verdict.PASS,
        (REASON_PASS,),
        1,
        0,
    )


def test_rule_5_block_crossing_blocks() -> None:
    """Contract 5, rule 5; contract 4 facts: all -1 crosses BLOCK at 13 pairs, so round 1."""
    m, rows = _m20(), [_row(MINUS)]
    trials = _store(m, rows)
    history = evaluate_rounds(m, trials)
    _check_history(history, rows, 4, trials)
    assert history[0].verdict is Verdict.BLOCK
    assert history[0].reasons == (REASON_BLOCK,)
    assert history[0].block_crossed and not history[0].pass_crossed


def test_rule_2_hard_violation_outranks_a_pass_crossing() -> None:
    """Contract 5, rule 2 before rule 4; pass_crossed stays the true crossing."""
    m, rows = _m20(), [_row(PLUS, hard={3})]
    trials = _store(m, rows)
    history = evaluate_rounds(m, trials)
    _check_history(history, rows, 4, trials)
    rd = history[0]
    assert rd.verdict is Verdict.BLOCK and rd.reasons == (REASON_HARD,)
    assert rd.pass_crossed is True and rd.block_crossed is False
    assert rd.candidate_hard_violations == 1
    d = _decide(m, trials)
    assert (d.verdict, d.reasons, d.stopped_at_round, d.exit_code) == (
        Verdict.BLOCK,
        (REASON_HARD,),
        1,
        1,
    )


def test_rule_1_errored_above_the_limit_outranks_everything() -> None:
    """Contract 5, rule 1 before rules 2 and 4: 2 errored > 1, a hard violation, PASS crossed."""
    m, rows = _m_err1(), [_row(PLUS, errored={0, 1}, hard={2})]
    trials = _store(m, rows)
    history = evaluate_rounds(m, trials)
    _check_history(history, rows, 1, trials)
    rd = history[0]
    assert rd.verdict is Verdict.ERROR and rd.reasons == (REASON_ERRORED,)
    # Scored PASS wealth of 2 minus and 18 plus is about 702.8 (independent Fraction check).
    assert rd.pass_crossed is True and rd.block_crossed is False
    assert rd.candidate_hard_violations == 1
    d = _decide(m, trials)
    # Situation table: k == r, round verdict ERROR -> ERROR with that round's reasons.
    assert d.verdict is Verdict.ERROR and d.reasons == (REASON_ERRORED,)
    assert d.history == history
    assert _cells(d) == _expected_cells(m, rows)


def test_rule_2_verdict_keeps_the_true_block_crossing() -> None:
    """Contract 5: pass_crossed and block_crossed are always the true crossings, whatever the
    verdict; rule 2 (hard violation) here, with the BLOCK wealth crossed and PASS not."""
    m, rows = _m20(), [_row(MINUS, hard={3})]
    trials = _store(m, rows)
    history = evaluate_rounds(m, trials)
    assert len(history) == 1
    _check_history(history, rows, 4, trials)
    rd = history[0]
    assert rd.verdict is Verdict.BLOCK and rd.reasons == (REASON_HARD,)
    assert rd.pass_crossed is False and rd.block_crossed is True


def test_rule_1_verdict_keeps_the_true_block_crossing() -> None:
    """Contract 5: pass_crossed and block_crossed are always the true crossings, whatever the
    verdict; rule 1 (2 errored > 1) here, scored BLOCK wealth of 18 minus and 2 errored
    (scored +1) crossed: 6.79683e+01 (independent Fraction computation)."""
    m, rows = _m_err1(), [_row(MINUS, errored={0, 1})]
    trials = _store(m, rows)
    history = evaluate_rounds(m, trials)
    assert len(history) == 1
    _check_history(history, rows, 1, trials)
    rd = history[0]
    assert rd.verdict is Verdict.ERROR and rd.reasons == (REASON_ERRORED,)
    assert rd.pass_crossed is False and rd.block_crossed is True
    assert rd.block_wealth == "6.79683e+01"


def test_errored_pairs_at_the_limit_are_not_rule_1() -> None:
    """Contract 5, rule 1 is strict (`>`): 2 errored with max_errored_pairs 2 still PASSes."""
    m, rows = suite_manifest(max_errored_pairs=2), [_row(PLUS, errored={0, 1})]
    trials = _store(m, rows)
    history = evaluate_rounds(m, trials)
    _check_history(history, rows, 2, trials)
    assert history[0].verdict is Verdict.PASS
    assert history[0].counts.errored == 2
    assert _decide(m, trials).verdict is Verdict.PASS


def test_hard_violation_on_an_errored_candidate_counts() -> None:
    """Contract 5: hard entries in contract.violations over candidate trials, any outcome."""
    m, rows = _m20(), [_row(PLUS, errored={0}, hard={0})]
    trials = _store(m, rows)
    history = evaluate_rounds(m, trials)
    _check_history(history, rows, 4, trials)
    assert history[0].verdict is Verdict.BLOCK and history[0].reasons == (REASON_HARD,)
    assert history[0].counts.errored == 1 and history[0].candidate_hard_violations == 1


def test_hard_violation_on_a_baseline_trial_does_not_count() -> None:
    """Contract 5: only candidate trials' hard violations count."""
    m = _m20()
    trials = list(_store(m, [_row(PLUS)]))
    base_spec = build_suite_round(m, 1)[0]  # cell 0, baseline (contract 3 order)
    assert trials[0].trial_id == base_spec.trial_id
    trials[0] = envelope(base_spec, Outcome.FAIL, hard_violation=True)
    history = evaluate_rounds(m, trials)
    assert history[0].candidate_hard_violations == 0
    assert history[0].verdict is Verdict.PASS
    d = _decide(m, trials)
    assert d.verdict is Verdict.PASS
    assert all(c.candidate_hard_violations == 0 for c in d.cells)


def test_hard_violations_are_counted_per_hard_entry() -> None:
    """Contract 5: the count is of hard-severity entries; soft entries do not count."""
    m = _m20()
    trials = list(_store(m, [_row(PLUS)]))
    cand_spec = build_suite_round(m, 1)[1]  # cell 0, candidate
    assert trials[1].trial_id == cand_spec.trial_id
    trials[1] = envelope(
        cand_spec,
        Outcome.PASS,
        contract=ContractResult(success=True, violations=(HARD, SOFT, HARD)),
    )
    history = evaluate_rounds(m, trials)
    assert history[0].candidate_hard_violations == 2
    assert history[0].verdict is Verdict.BLOCK
    d = _decide(m, trials)
    assert d.verdict is Verdict.BLOCK and d.reasons == (REASON_HARD,)
    assert d.cells[0].candidate_hard_violations == 2
    assert all(c.candidate_hard_violations == 0 for c in d.cells[1:])


# --- errored-pair scoring ----------------------------------------------------------------------


def test_errored_pair_is_minus_one_for_pass_wealth() -> None:
    """Contract 5 (scored_wealth) and contract 4 facts: 20 cells, 4 rounds, max_errored_pairs 1,
    one errored pair and 79 pairs of 0 is INCONCLUSIVE (PASS wealth about 21.17)."""
    m = _m4(1)
    rows = [_row(ZEROS), _row(ZEROS, errored={5}), _row(ZEROS), _row(ZEROS)]
    trials = _store(m, rows)
    # Scored as 0, or dropped, the same store would PASS.
    assert reference_wealth(0, 80, 0, ALPHA, DELTA, STAKES)[0] >= THRESHOLD
    assert reference_wealth(0, 79, 0, ALPHA, DELTA, STAKES)[0] >= THRESHOLD
    d = _decide(m, trials)
    assert d.verdict is Verdict.INCONCLUSIVE
    assert d.reasons == (REASON_NONE,)
    assert d.stopped_at_round == 4 and d.exit_code == 2
    _check_history(d.history, rows, 1, trials)
    assert d.history[-1].pass_wealth == "2.11702e+01"  # independent Fraction computation
    assert d.history[-1].counts.errored == 1 and d.history[-1].counts.zero == 79


def test_errored_pair_is_plus_one_for_block_wealth() -> None:
    """Contract 5 (scored_wealth): 14 minus, 5 zero, 1 errored in one round does not BLOCK,
    although scoring the errored pair as -1, as 0 or dropping it would."""
    m = _m20()
    rows = [_row((-1,) * 14 + (0,) * 6, errored={19})]
    trials = _store(m, rows)
    assert reference_wealth(15, 5, 0, ALPHA, DELTA, STAKES)[1] >= THRESHOLD
    assert reference_wealth(14, 6, 0, ALPHA, DELTA, STAKES)[1] >= THRESHOLD
    assert reference_wealth(14, 5, 0, ALPHA, DELTA, STAKES)[1] >= THRESHOLD
    history = evaluate_rounds(m, trials)
    _check_history(history, rows, 4, trials)
    assert history[0].verdict is Verdict.INCONCLUSIVE
    assert history[0].block_crossed is False
    d = _decide(m, trials)
    assert d.verdict is Verdict.ERROR and d.reasons == (NO_DECISION,)


def test_baseline_or_both_arms_errored_is_one_errored_pair() -> None:
    """Contract 1, errored pair: either trial ERROR; contract 2, SuiteCellStats: a candidate PASS
    counts even if the partner errored, and each pair is in exactly one of the four counts.
    Round 2: cell 3 has its baseline ERROR (candidate PASS); cell 4 has both arms ERROR."""
    m = _m4()
    trials = list(_store(m, ZERO_ROWS))
    specs = build_suite_round(m, 2)  # contract 3: cell order, baseline then candidate
    offset = 2 * N  # round 2 starts after the 2 * N trials of round 1
    for i in (6, 8, 9):
        assert trials[offset + i].trial_id == specs[i].trial_id
        trials[offset + i] = envelope(specs[i], Outcome.ERROR)
    assert (specs[6].arm, specs[8].arm, specs[9].arm) == ("baseline", "baseline", "candidate")
    d = _decide(m, trials)
    assert d.verdict is Verdict.INCONCLUSIVE
    assert d.reasons == (REASON_NONE,)
    assert d.stopped_at_round == 4
    per_round = [(0, 20, 0, 0), (0, 38, 0, 2), (0, 58, 0, 2), (0, 78, 0, 2)]
    assert len(d.history) == 4
    for r, rd in enumerate(d.history, start=1):
        _check_round(rd, r, per_round[r - 1], 0, 4, trials)
    assert d.history[-1].pass_wealth == _wealth_text(_scored(0, 78, 0, 2)[0])
    assert d.history[-1].pass_wealth == "1.08643e+01"  # independent Fraction computation

    def row(c: SuiteCellStats) -> tuple[object, ...]:
        return (
            c.pairs,
            c.baseline_successes,
            c.candidate_successes,
            (c.counts.minus, c.counts.zero, c.counts.plus, c.counts.errored),
        )

    assert row(d.cells[3]) == (4, 3, 4, (0, 3, 0, 1))
    assert row(d.cells[4]) == (4, 3, 3, (0, 3, 0, 1))
    for i, c in enumerate(d.cells):
        if i not in (3, 4):
            assert row(c) == (4, 4, 4, (0, 4, 0, 0))
    assert sum(c.counts.errored for c in d.cells) == 2


# --- evaluate_rounds -------------------------------------------------------------------------


def test_evaluate_rounds_cumulative_counts_and_digests() -> None:
    """Contract 5, evaluate_rounds; contract 2, SuiteRoundDecision fields (cumulative)."""
    m, trials = _m20(), _zero_store()
    history = evaluate_rounds(m, trials)
    assert [rd.round for rd in history] == [1, 2, 3, 4]
    assert [rd.pairs for rd in history] == [20, 40, 60, 80]
    assert [rd.verdict for rd in history] == [Verdict.INCONCLUSIVE] * 3 + [Verdict.PASS]
    _check_history(history, ZERO_ROWS, 4, trials)
    # Contract 8 item 3: each round digest covers one round, so the last one is not the
    # digest over the whole store (that one is the decision's own trials_sha256).
    assert history[-1].trials_sha256 == _digest([t for t in trials if _round_of(t) == 4])
    assert history[-1].trials_sha256 != _digest(trials)
    assert len({rd.trials_sha256 for rd in history}) == 4


def test_round_digests_cover_one_round_each() -> None:
    """Contract 8 item 3: SuiteRoundDecision.trials_sha256 is hash_record over the sorted
    seals of that round's trials only; the decision's trials_sha256 still covers all of them."""
    m, trials = _m20(), _zero_store()
    d = _decide(m, trials)
    assert len(d.history) == 4
    for r, rd in enumerate(d.history, start=1):
        one_round = [t for t in trials if _round_of(t) == r]
        assert len(one_round) == 2 * N
        assert rd.trials_sha256 == _digest(one_round)
        if r > 1:
            # A cumulative digest would differ, so this pins the one-round reading.
            assert rd.trials_sha256 != _digest([t for t in trials if _round_of(t) <= r])
    assert d.trials_sha256 == _digest(trials)
    assert d.trials_sha256 not in {rd.trials_sha256 for rd in d.history}


def test_evaluate_rounds_stops_after_the_first_decisive_round() -> None:
    """Contract 5, evaluate_rounds: walking stops after the first non-INCONCLUSIVE round."""
    m = _m20()
    rows = [_row(ZEROS), _row(MINUS), _row(ZEROS)]
    trials = _store(m, rows)
    history = evaluate_rounds(m, trials)
    assert len(history) == 2
    _check_history(history, rows, 4, trials)
    assert history[1].verdict is Verdict.BLOCK
    assert history[1].counts.minus == 20 and history[1].counts.zero == 20


def test_evaluate_rounds_ignores_a_trailing_partial_round() -> None:
    """Contract 5, evaluate_rounds: a trailing partial round is no look and no exception,
    even when its pairs alone would be decisive."""
    m = _m20()
    rows = [_row(ZEROS), _row(ZEROS)]
    full = _store(m, rows)
    partial = round_trials(m, 3, MINUS)[:-1]
    history = evaluate_rounds(m, full + partial)
    assert len(history) == 2
    _check_history(history, rows, 4, full)
    assert all(rd.verdict is Verdict.INCONCLUSIVE for rd in history)
    assert evaluate_rounds(m, full + partial) == evaluate_rounds(m, full)


def test_evaluate_rounds_without_a_complete_round_is_empty() -> None:
    """Contract 5, evaluate_rounds: one decision per complete round present."""
    m = _m20()
    assert evaluate_rounds(m, ()) == ()
    assert evaluate_rounds(m, round_trials(m, 1, MINUS)[:-2]) == ()


# --- decide_suite: decisions -------------------------------------------------------------------


def test_never_differing_candidate_passes_at_round_four() -> None:
    """Contract 5 situation k == r PASS; contract 4 facts: all-zero crosses at 79 pairs."""
    m, trials = _m20(), _zero_store()
    d = _decide(m, trials)
    assert d.verdict is Verdict.PASS
    assert d.reasons == (REASON_PASS,)
    assert d.stopped_at_round == 4
    assert d.exit_code == 0
    assert len(d.history) == 4
    _check_history(d.history, ZERO_ROWS, 4, trials)
    assert d.history == evaluate_rounds(m, trials)
    assert d.history[-1].pass_wealth == "4.22732e+01"  # contract 4, verified example
    assert d.trials_sha256 == _digest(trials)
    assert d.threshold == "40/1"
    _assert_mirrors(d, m)
    assert d.n_cells == 20 and d.max_rounds == 20 and d.max_errored_pairs == 4
    assert (d.alpha, d.delta, d.stakes, d.scenario_seeds) == (
        "1/20",
        "1/10",
        ("1/4", "1/2"),
        "fixed",
    )
    assert _cells(d) == _expected_cells(m, ZERO_ROWS)
    assert [(c.task_id, c.condition_id) for c in d.cells] == list(cell_keys(m))


def test_all_minus_candidate_blocks_at_round_one() -> None:
    """Contract 5 situation k == r BLOCK."""
    m, rows = _m20(), [_row(MINUS)]
    trials = _store(m, rows)
    d = _decide(m, trials)
    assert (d.verdict, d.reasons, d.stopped_at_round, d.exit_code) == (
        Verdict.BLOCK,
        (REASON_BLOCK,),
        1,
        1,
    )
    _check_history(d.history, rows, 4, trials)
    assert d.trials_sha256 == _digest(trials)
    _assert_mirrors(d, m)
    assert _cells(d) == _expected_cells(m, rows)


def test_inconclusive_at_max_rounds() -> None:
    """Contract 5 situation k == r == max_rounds INCONCLUSIVE: alternating differences."""
    m = _m4()
    rows = [_row(ALTERNATING)] * 4
    trials = _store(m, rows)
    d = _decide(m, trials)
    assert d.verdict is Verdict.INCONCLUSIVE
    assert d.reasons == (REASON_NONE,)
    assert d.stopped_at_round == 4 and d.exit_code == 2
    assert len(d.history) == 4
    assert all(rd.verdict is Verdict.INCONCLUSIVE for rd in d.history)
    _check_history(d.history, rows, 4, trials)
    assert d.trials_sha256 == _digest(trials)
    _assert_mirrors(d, m)
    assert _cells(d) == _expected_cells(m, rows)


def test_cell_table_counts_errored_pairs_and_blocks_on_a_late_hard_violation() -> None:
    """Contract 2, SuiteCellStats (errored pairs counted once, partner PASS still counted);
    contract 5 situation k == r BLOCK at the last round."""
    m = _m4()
    r1 = [0] * N
    r1[0:5] = [1] * 5
    r1[5:10] = [-1] * 5
    r1[10] = 1  # errored below: baseline FAIL, candidate ERROR
    r2 = [0] * N
    r2[0:3] = [-1] * 3
    r2[3:6] = [1] * 3
    r3 = [0] * N
    r3[18], r3[19] = 1, -1
    rows = [
        _row(r1, errored={10}),
        _row(r2, errored={11}),
        _row(r3),
        _row(ZEROS, errored={12}, hard={7}),
    ]
    trials = _store(m, rows)
    d = _decide(m, trials)
    assert d.verdict is Verdict.BLOCK and d.reasons == (REASON_HARD,)
    assert d.stopped_at_round == 4 and d.exit_code == 1
    assert [rd.verdict for rd in d.history] == [Verdict.INCONCLUSIVE] * 3 + [Verdict.BLOCK]
    _check_history(d.history, rows, 4, trials)
    assert _cells(d) == _expected_cells(m, rows)
    by_key = {(c.task_id, c.condition_id): c for c in d.cells}
    keys = cell_keys(m)
    assert by_key[keys[10]].baseline_successes == 3  # FAIL in round 1, PASS in rounds 2 to 4
    assert by_key[keys[10]].candidate_successes == 3
    assert by_key[keys[10]].counts.errored == 1 and by_key[keys[10]].pairs == 4
    assert by_key[keys[11]].baseline_successes == 4  # partner errored in round 2
    assert by_key[keys[7]].candidate_hard_violations == 1
    assert sum(c.counts.errored for c in d.cells) == d.history[-1].counts.errored == 3


def test_mirrors_follow_a_non_default_manifest() -> None:
    """Contract 5, fields of every decision: mirrors and threshold = format_rational(2/alpha)."""
    m = suite_manifest(
        n_tasks=3,
        n_conditions=2,
        alpha="3/40",
        delta="1/20",
        stakes=("1/8", "1/2"),
        scenario_seeds="per_round",
        prior_runs=("earlier-run",),
        max_rounds=30,
        max_errored_pairs=2,
    )
    d = _decide(m, ())
    _assert_check_error(d, (WHOLE_ROUNDS,))
    _assert_mirrors(d, m)
    assert d.threshold == "80/3"
    assert d.n_cells == 6
    assert (d.alpha, d.delta, d.stakes) == ("3/40", "1/20", ("1/8", "1/2"))
    assert d.scenario_seeds == "per_round" and d.prior_runs == ("earlier-run",)
    assert d.trials_sha256 == hash_record({"trials": []})


# --- check 1: manifest values ----------------------------------------------------------------


def _bad_manifests() -> list[tuple[str, dict[str, object]]]:
    m = _m20()
    return [
        ("max_rounds zero", {"max_rounds": 0}),
        ("alpha not lowest terms", {"alpha": "2/40"}),
        ("alpha above one half", {"alpha": "3/4"}),
        ("no tasks", {"tasks": ()}),
        ("duplicate condition ids", {"conditions": (CONDITIONS[0], CONDITIONS[0])}),
        ("stakes not increasing", {"stakes": ("1/2", "1/4")}),
        ("unknown seed mode", {"scenario_seeds": "sometimes"}),
        ("acknowledgement without one round", {"acknowledge_single_round": True}),
        ("errored limit above registered pairs", {"max_errored_pairs": 401}),
        ("max_rounds wrong type", {"max_rounds": "many"}),
        # Contract 8 item 2: experiment_id has a fixed shape, so a malformed one no longer
        # rebuilds and check 1 fails on it.
        ("experiment_id without a digest", {"experiment_id": "suite-acceptance"}),
        ("experiment_id with a path separator", {"experiment_id": f"../suite@{'0' * 64}"}),
        ("experiment_id with uppercase hex", {"experiment_id": f"suite-acceptance@{'A' * 64}"}),
        ("lone surrogate in experiment_id", {"experiment_id": "\ud800"}),
        (
            "lone surrogate in a task",
            {"tasks": (SuiteTask(task_id="t0", task={"input": "\ud800"}), *m.tasks[1:])},
        ),
    ]


@pytest.mark.parametrize(
    ("label", "update"), _bad_manifests(), ids=[b[0] for b in _bad_manifests()]
)
def test_invalid_manifest_values_give_the_fixed_template(
    label: str, update: dict[str, object]
) -> None:
    """Contract 5, check 1 and the fixed template; trials_sha256 still computed."""
    del label
    bad = _m20().model_copy(update=update)
    trials = _zero_store()
    d = _decide(bad, trials)
    _assert_check_error(d, (MANIFEST_INVALID,))
    _assert_template(d)
    assert d.trials_sha256 == _digest(trials)


def test_model_construct_manifest_gives_the_fixed_template() -> None:
    """Contract 5: never raises for a SuiteManifest built with model_construct; check 1 fails."""
    trials = _zero_store()
    d = _decide(SuiteManifest.model_construct(), trials)
    _assert_check_error(d, (MANIFEST_INVALID,))
    _assert_template(d)
    assert d.trials_sha256 == _digest(trials)


def test_check_1_failure_skips_every_other_check() -> None:
    """Contract 5: if check 1 fails, checks 2 to 8 are skipped (no trial reasons)."""
    good = _zero_store()
    broken = good[0].model_copy(update={"failure_detail": "\ud800"})
    trials = (broken, *good[1:20], good[1])
    bad = _m20().model_copy(update={"max_rounds": 0, "record_sha256": "0" * 64})
    d = _decide(bad, trials)
    _assert_check_error(d, (MANIFEST_INVALID,))
    _assert_template(d)


# --- checks 2 to 4: manifest seal, rule digest, plan ---------------------------------------------


def test_broken_manifest_seal() -> None:
    """Contract 5, check 2 alone; manifest_sha256 is record_sha256 as supplied."""
    m = _m20().model_copy(update={"record_sha256": "0" * 64})
    trials = _zero_store()
    d = _decide(m, trials)
    _assert_check_error(d, (MANIFEST_SEAL,))
    assert d.manifest_sha256 == "0" * 64
    assert d.experiment_id == _m20().experiment_id
    assert d.trials_sha256 == _digest(trials)


def test_unsealed_manifest_edit_breaks_the_seal() -> None:
    """Contract 5, check 2: content changed under the old seal."""
    m = _m20().model_copy(update={"created_at": "2026-11-11", "fixtures_sha256": "edited"})
    d = _decide(m, _zero_store())
    assert d.verdict is Verdict.ERROR
    assert d.reasons[0] == MANIFEST_SEAL


@pytest.mark.parametrize("which", ["wrong digest", "wrong suite id"])
def test_stored_experiment_id_that_is_not_the_rule_digest(which: str) -> None:
    """Contract 5, check 3 alone: a sealed manifest whose experiment_id is not
    f"{suite_id}@{suite_rule_sha256}", with trials built for that manifest."""
    base = _m20()
    digest = base.experiment_id.split("@", 1)[1]
    experiment_id = (
        f"{base.suite_id}@{'0' * 64}" if which == "wrong digest" else f"other-suite@{digest}"
    )
    assert experiment_id != base.experiment_id
    m = SuiteManifest.create(
        **{**base.model_dump(exclude={"record_sha256"}), "experiment_id": experiment_id}
    )
    assert m.validate_seal()
    trials = _store(m, [_row(ZEROS)])
    d = _decide(m, trials)
    _assert_check_error(d, (RULE_DIGEST,))
    _assert_mirrors(d, m)


@pytest.mark.parametrize(
    ("label", "base_errored", "rows", "update"),
    [
        ("delta loosened", 4, ZERO_ROWS, {"delta": "1/20"}),
        ("errored limit raised", 1, (_row(PLUS, errored={0, 1}),), {"max_errored_pairs": 2}),
        ("fixtures changed", 4, ZERO_ROWS, {"fixtures_sha256": "0" * 64}),
    ],
    ids=["delta", "max_errored_pairs", "fixtures_sha256"],
)
def test_rule_changed_after_the_run_and_resealed_is_error(
    label: str, base_errored: int, rows: tuple[Row, ...], update: dict[str, object]
) -> None:
    """Contract 5, checks 3 and 6: the old experiment_id no longer matches the rule digest, and
    the seeds (derived from the recomputed digest) no longer match the stored trials."""
    del label
    base = _m20() if base_errored == 4 else _m_err1()
    trials = _store(base, rows)
    changed = SuiteManifest.create(**{**base.model_dump(exclude={"record_sha256"}), **update})
    assert changed.validate_seal() and changed.experiment_id == base.experiment_id
    d = _decide(changed, trials)
    _assert_check_error(d, (RULE_DIGEST, SCHEDULE))
    _assert_mirrors(d, changed)


@pytest.mark.parametrize(
    ("overrides", "rounds"),
    [
        # Contract 4 facts: a 20-cell plan with max_rounds 3 is refused (floor is round 4).
        ({"max_rounds": 3}, 1),
        # Check (b): 49 plus and 31 errored in 80 pairs does not cross (independent Fraction
        # computation); 30 errored still crosses, see the next test.
        ({"max_rounds": 4, "max_errored_pairs": 31}, 4),
    ],
    ids=["below the floor", "errored tolerance leaves PASS unreachable"],
)
def test_suite_plan_invalid(overrides: dict[str, Any], rounds: int) -> None:
    """Contract 5, check 4 alone."""
    m = suite_manifest(**overrides)
    trials = _store(m, [_row(ZEROS)] * rounds)
    d = _decide(m, trials)
    _assert_check_error(d, (PLAN_INVALID,))
    _assert_mirrors(d, m)
    assert d.trials_sha256 == _digest(trials)


def test_errored_tolerance_just_inside_the_plan_limit() -> None:
    """Contract 5, check 4 passes for 20 cells, 4 rounds, max_errored_pairs 30 (50 plus and 30
    errored still cross: independent Fraction computation); all zeros then PASS at round 4."""
    m = _m4(30)
    trials = _store(m, ZERO_ROWS)
    d = _decide(m, trials)
    assert d.verdict is Verdict.PASS and d.stopped_at_round == 4


@pytest.mark.parametrize(
    ("n_tasks", "max_rounds", "acknowledge"),
    [(10, 2, False), (20, 1, True)],
    ids=["40 cells, 2 rounds", "80 cells, 1 round"],
)
def test_plan_warnings_are_not_a_plan_failure(
    n_tasks: int, max_rounds: int, acknowledge: bool
) -> None:
    """Contract 5, check 4 is "check_suite_plan does not raise"; contract 4: a valid plan with
    max_rounds < 3 only returns the warning ("max_rounds below 3: few looks",). All-zero
    differences cross PASS at 79 pairs (contract 4 facts), so 80 zeros PASS at the last round."""
    m = suite_manifest(
        n_tasks=n_tasks,
        max_rounds=max_rounds,
        acknowledge_single_round=acknowledge,
        max_errored_pairs=0,
    )
    n_cells = n_tasks * 4
    assert n_cells * max_rounds == 80
    trials = _store(m, [_row((0,) * n_cells)] * max_rounds)
    d = _decide(m, trials)
    assert PLAN_INVALID not in d.reasons
    assert d.verdict is Verdict.PASS and d.reasons == (REASON_PASS,)
    assert d.stopped_at_round == max_rounds
    for r, rd in enumerate(d.history, start=1):
        _check_round(rd, r, (0, r * n_cells, 0, 0), 0, 0, trials, n_cells=n_cells)
    _assert_mirrors(d, m)


# --- check 5: trial values; normalisation ------------------------------------------------------


@pytest.mark.parametrize(
    "update",
    [
        {"outcome": "MAYBE"},
        {"seed": "not a number"},
        {"arm": "neither"},
        {"spec_sha256": "not-hex"},
        {"termination": "vanished"},
        {"failure_detail": "\ud800"},
    ],
    ids=["outcome", "seed", "arm", "spec_sha256", "termination", "lone surrogate"],
)
def test_invalid_trial_values(update: dict[str, object]) -> None:
    """Contract 5, check 5 alone (6 to 8 skipped, so the broken seal is not reported)."""
    good = _zero_store()
    trials = (*good[:5], good[5].model_copy(update=update), *good[6:])
    d = _decide(_m20(), trials)
    _assert_check_error(d, (TRIAL_INVALID,))
    _assert_mirrors(d, _m20())
    assert d.trials_sha256 == _digest(trials)


def test_model_construct_trial_is_invalid() -> None:
    """Contract 5: never raises for a TrialEnvelope built with model_construct; check 5 fails."""
    good = _zero_store()
    d = _decide(_m20(), (*good, TrialEnvelope.model_construct()))
    _assert_check_error(d, (TRIAL_INVALID,))


def test_check_5_failure_skips_checks_6_to_8() -> None:
    """Contract 5: with check 5 failing, duplicates, broken seals and partial rounds are not
    reported."""
    good = _zero_store()
    broken = good[2].model_copy(update={"failure_detail": "\ud800"})
    tampered = good[3].model_copy(update={"failure_detail": "edited"})
    trials = (good[0], good[1], broken, tampered, good[0], *good[4:-1])
    d = _decide(_m20(), trials)
    _assert_check_error(d, (TRIAL_INVALID,))


def test_wrong_typed_outcomes_are_normalised_before_scoring() -> None:
    """Contract 5, normalise first: model_copy(update={"outcome": "PASS"}) / "ERROR" keeps a
    valid seal, and the gate scores the rebuilt Outcome, so the decision is unchanged."""
    m = _m20()
    good = _zero_store()
    as_text = good[7].model_copy(update={"outcome": "PASS"})
    assert as_text.validate_seal() and as_text.outcome is not Outcome.PASS
    d_good = _decide(m, good)
    d_text = _decide(m, (*good[:7], as_text, *good[8:]))
    assert d_text == d_good and d_text.verdict is Verdict.PASS

    m1 = _m4(1)
    rows = [_row(ZEROS), _row(ZEROS, errored={5}), _row(ZEROS), _row(ZEROS)]
    errored_store = _store(m1, rows)
    index = next(
        i for i, t in enumerate(errored_store) if t.outcome is Outcome.ERROR
    )  # the one errored candidate trial
    as_error_text = errored_store[index].model_copy(update={"outcome": "ERROR"})
    assert as_error_text.validate_seal() and as_error_text.outcome is not Outcome.ERROR
    d_err = _decide(m1, errored_store)
    d_err_text = _decide(m1, (*errored_store[:index], as_error_text, *errored_store[index + 1 :]))
    assert d_err_text == d_err
    assert d_err_text.verdict is Verdict.INCONCLUSIVE
    assert d_err_text.history[-1].counts.errored == 1
    assert d_err_text.history[-1].counts.minus == 0


def test_seals_are_checked_on_the_rebuilt_instances() -> None:
    """Contract 5, normalise first: every later check (2 and 7 included) uses only the rebuilt
    instances. A wrong-typed copy ("20" for max_rounds, a str seed) fails validate_seal() as
    supplied but verifies once rebuilt, so the decision equals the untouched one."""
    m, good = _m20(), _zero_store()
    d_good = _decide(m, good)
    assert d_good.verdict is Verdict.PASS and d_good.stopped_at_round == 4

    m_text = m.model_copy(update={"max_rounds": "20"})
    m_rebuilt = SuiteManifest.model_validate(m_text.model_dump(mode="python"))
    assert not m_text.validate_seal() and m_rebuilt.validate_seal()
    d_m = _decide(m_text, good)
    assert MANIFEST_SEAL not in d_m.reasons
    assert d_m == d_good

    t_text = good[5].model_copy(update={"seed": str(good[5].seed)})
    t_rebuilt = TrialEnvelope.model_validate(t_text.model_dump(mode="python"))
    assert not t_text.validate_seal() and t_rebuilt.validate_seal()
    d_t = _decide(m, (*good[:5], t_text, *good[6:]))
    assert TRIAL_SEAL not in d_t.reasons
    assert d_t == d_good


# --- checks 6 to 8: schedule, seals, whole rounds -------------------------------------------------


def test_duplicate_trial() -> None:
    """Contract 5, check 6 (duplicate trial id) alone; check 8 skipped."""
    good = _zero_store()
    trials = (*good, good[0])
    d = _decide(_m20(), trials)
    _assert_check_error(d, (SCHEDULE,))
    assert d.trials_sha256 == _digest(trials)


def test_unknown_trial() -> None:
    """Contract 5, check 6: an id that is not in build_suite_schedule (round 21 of 20)."""
    good = _zero_store()
    stray = reseal(
        good[0],
        trial_id=good[0].trial_id.replace("r000001", "r000021"),
        pair_id=good[0].pair_id.replace("r000001", "r000021"),
    )
    d = _decide(_m20(), (*good, stray))
    _assert_check_error(d, (SCHEDULE,))


def test_trial_from_another_experiment() -> None:
    """Contract 5, check 6: same trial id, but scheduled for a different suite."""
    other = suite_manifest(suite_id="suite-other")
    foreign = round_trials(other, 1, ZEROS)[4]
    good = _zero_store()
    assert foreign.trial_id == good[4].trial_id and foreign.validate_seal()
    d = _decide(_m20(), (*good[:4], foreign, *good[5:]))
    _assert_check_error(d, (SCHEDULE,))


@pytest.mark.parametrize(
    "field",
    ["experiment_id", "pair_id", "arm", "task_id", "condition_id", "seed", "spec_sha256"],
)
def test_trial_identity_must_match_its_spec(field: str) -> None:
    """Contract 5, check 6: experiment_id, pair_id, arm, task_id, condition_id, seed and
    spec_sha256 are compared with the spec (as gate.py:41-50); resealed, so check 7 passes."""
    good = _zero_store()
    t = good[9]  # cell 4, candidate, round 1
    changed: object = {
        "experiment_id": "suite-acceptance@" + "1" * 64,
        "pair_id": "r000001:t9:clean",
        "arm": "baseline",
        "task_id": "t9",
        "condition_id": "nowhere",
        "seed": t.seed + 1,
        "spec_sha256": "0" * 64,
    }[field]
    impostor = reseal(t, **{field: changed})
    d = _decide(_m20(), (*good[:9], impostor, *good[10:]))
    _assert_check_error(d, (SCHEDULE,))


def test_replay_mode_spec_hash_mismatch() -> None:
    """Contract 5, check 6: a trial run from a REPLAY copy of its spec has another spec_sha256."""
    m = _m20()
    good = _store(m, [_row(ZEROS)])
    spec = build_suite_round(m, 1)[1]
    replay_spec = TrialSpec.model_validate({**spec.model_dump(), "tool_mode": "replay"})
    replayed = envelope(replay_spec, Outcome.PASS)
    assert replayed.trial_id == good[1].trial_id and replayed.validate_seal()
    d = _decide(m, (good[0], replayed, *good[2:]))
    _assert_check_error(d, (SCHEDULE,))


def test_broken_trial_seal() -> None:
    """Contract 5, check 7 alone."""
    good = _zero_store()
    tampered = good[11].model_copy(update={"failure_detail": "edited after the run"})
    trials = (*good[:11], tampered, *good[12:])
    d = _decide(_m20(), trials)
    _assert_check_error(d, (TRIAL_SEAL,))
    assert d.trials_sha256 == _digest(trials)


def _not_whole_stores() -> dict[str, tuple[TrialEnvelope, ...]]:
    good = _zero_store()
    per_round = 2 * N
    return {
        "empty store": (),
        "partial first round": good[: per_round - 1],
        "partial last round": good[: 2 * per_round - 3],
        "round 2 missing": good[:per_round] + good[2 * per_round : 3 * per_round],
        "round 2 alone": good[per_round : 2 * per_round],
    }


@pytest.mark.parametrize("label", list(_not_whole_stores()))
def test_trial_set_not_a_whole_number_of_rounds(label: str) -> None:
    """Contract 5, check 8 alone: not empty, rounds 1 to r, no partial round."""
    trials = _not_whole_stores()[label]
    d = _decide(_m20(), trials)
    _assert_check_error(d, (WHOLE_ROUNDS,))
    assert d.trials_sha256 == _digest(trials)
    _assert_mirrors(d, _m20())


def test_check_6_failure_skips_check_8_but_not_check_7() -> None:
    """Contract 5: check 8 is skipped when check 6 fails; check 7 still runs."""
    good = _zero_store()
    tampered = good[3].model_copy(update={"failure_detail": "edited"})
    trials = (good[0], good[1], good[2], tampered, good[0])  # duplicate and a partial round
    d = _decide(_m20(), trials)
    _assert_check_error(d, (SCHEDULE, TRIAL_SEAL))
    d2 = _decide(_m20(), (*good[:10], good[0]))
    _assert_check_error(d2, (SCHEDULE,))


def test_failing_checks_are_collected_in_order() -> None:
    """Contract 5: every failing check is collected, in table order (2, 3, 4, 7, 8)."""
    base = suite_manifest(max_rounds=3)
    m = SuiteManifest.create(
        **{
            **base.model_dump(exclude={"record_sha256"}),
            "experiment_id": f"{base.suite_id}@{'0' * 64}",
        }
    ).model_copy(update={"record_sha256": "1" * 64})
    good = round_trials(m, 1, ZEROS)
    tampered = good[3].model_copy(update={"failure_detail": "edited"})
    trials = (*good[:3], tampered, *good[4:-1])
    d = _decide(m, trials)
    _assert_check_error(d, (MANIFEST_SEAL, RULE_DIGEST, PLAN_INVALID, TRIAL_SEAL, WHOLE_ROUNDS))
    assert d.manifest_sha256 == "1" * 64


# --- situations after the walk -----------------------------------------------------------------


def test_trials_stored_after_a_decisive_round() -> None:
    """Contract 5 situation k < r; history is the walked rounds, cells cover all trials."""
    m = _m20()
    rows = [_row(MINUS), _row(ZEROS)]
    trials = _store(m, rows)
    d = _decide(m, trials)
    assert d.verdict is Verdict.ERROR and d.reasons == (AFTER_STOP,)
    assert len(d.history) == 1 and d.history[0].verdict is Verdict.BLOCK
    _check_history(d.history, rows, 4, trials)
    assert _cells(d) == _expected_cells(m, rows)
    assert all(c.pairs == 2 for c in d.cells)
    assert d.trials_sha256 == _digest(trials)
    _assert_mirrors(d, m)


def test_trials_stored_after_an_error_round() -> None:
    """Contract 5 situation k < r, where the earlier round's verdict is ERROR."""
    m = _m_err1()
    rows = [_row(PLUS, errored={0, 1}), _row(ZEROS)]
    trials = _store(m, rows)
    d = _decide(m, trials)
    assert d.verdict is Verdict.ERROR and d.reasons == (AFTER_STOP,)
    assert len(d.history) == 1 and d.history[0].verdict is Verdict.ERROR
    assert _cells(d) == _expected_cells(m, rows)


def test_stopped_without_a_decision() -> None:
    """Contract 5 situation k == r, INCONCLUSIVE, r < max_rounds."""
    m = _m20()
    rows = [_row(ZEROS)] * 2
    trials = _store(m, rows)
    d = _decide(m, trials)
    assert d.verdict is Verdict.ERROR and d.reasons == (NO_DECISION,)
    assert len(d.history) == 2
    _check_history(d.history, rows, 4, trials)
    assert _cells(d) == _expected_cells(m, rows)
    assert d.trials_sha256 == _digest(trials)


# --- trials_sha256 that cannot be computed ------------------------------------------------------


def test_trials_sha256_is_empty_for_a_lone_surrogate_seal() -> None:
    """Contract 5: trials_sha256 is "" when computing it raises; check 5 names the trial."""
    good = _zero_store()
    trials = (*good[:-1], good[-1].model_copy(update={"record_sha256": "\ud800"}))
    d = _decide(_m20(), trials)
    _assert_check_error(d, (TRIAL_INVALID,))
    assert d.trials_sha256 == ""
    _assert_mirrors(d, _m20())


def test_trials_sha256_is_empty_in_the_template_too() -> None:
    """Contract 5: the template with an uncomputable trials digest still seals."""
    good = _zero_store()
    trials = (good[0].model_copy(update={"record_sha256": "\ud800"}), *good[1:])
    d = _decide(_m20().model_copy(update={"tasks": ()}), trials)
    _assert_check_error(d, (MANIFEST_INVALID,))
    _assert_template(d)
    assert d.trials_sha256 == ""


def test_trials_sha256_is_empty_for_a_non_string_seal() -> None:
    """Contract 5 and 8 item 4: a seal that is not a str fails check 5, and the digest over the
    supplied seals, which cannot be sorted, is ""."""
    good = _zero_store()
    trials = (good[0].model_copy(update={"record_sha256": 5}), *good[1:])
    d = _decide(_m20(), trials)
    _assert_check_error(d, (TRIAL_INVALID,))
    assert d.trials_sha256 == ""
    _assert_mirrors(d, _m20())


@pytest.mark.parametrize("position", [0, 7, 159], ids=["first", "middle", "last"])
def test_bytes_seal_fails_check_5(position: int) -> None:
    """Contract 8 item 4: a supplied record_sha256 that is not a str fails check 5 even when
    rebuilding would coerce it. The bytes here hold the trial's own correct digest, so the
    rebuilt trial seals validly and nothing but item 4 refuses this store."""
    good = _zero_store()
    assert len(good) == 160  # 20 cells x 2 arms x 4 rounds
    original = good[position]
    as_bytes = original.model_copy(update={"record_sha256": original.record_sha256.encode()})
    assert as_bytes.record_sha256 == original.record_sha256.encode()
    rebuilt = TrialEnvelope.model_validate(as_bytes.model_dump(mode="python"))
    assert rebuilt.record_sha256 == original.record_sha256
    assert rebuilt == original and rebuilt.validate_seal()

    trials = (*good[:position], as_bytes, *good[position + 1 :])
    d = _decide(_m20(), trials)
    _assert_check_error(d, (TRIAL_INVALID,))
    assert d.trials_sha256 == ""
    _assert_mirrors(d, _m20())


def test_a_string_seal_of_the_wrong_value_is_check_7_not_check_5() -> None:
    """Contract 8 item 4 is about the type only: a str seal still reaches check 7, which is
    where a wrong digest is reported."""
    good = _zero_store()
    trials = (good[0].model_copy(update={"record_sha256": "0" * 64}), *good[1:])
    d = _decide(_m20(), trials)
    _assert_check_error(d, (TRIAL_SEAL,))
    assert d.trials_sha256 == _digest(trials)


# --- determinism and replay ---------------------------------------------------------------------


def test_same_inputs_same_decision_in_any_order() -> None:
    """Contract 5: pure and deterministic; every field is defined over the set of trials."""
    m = _m4()
    rows = [_row(ALTERNATING, errored={2}, hard=()), _row(ZEROS), _row(PLUS), _row(ZEROS)]
    trials = _store(m, rows)
    first = _decide(m, trials)
    assert _decide(m, trials) == first
    rng = random.Random(20261111)
    for _ in range(3):
        shuffled = list(trials)
        rng.shuffle(shuffled)
        assert _decide(m, shuffled) == first
    broken = (*trials, trials[0])
    error = _decide(m, broken)
    shuffled_broken = list(broken)
    rng.shuffle(shuffled_broken)
    assert _decide(m, shuffled_broken) == error


def test_replay_is_true_for_real_decisions() -> None:
    """Contract 5, replay_suite_decision: seal valid and decide_suite(...) == decision."""
    cases: list[tuple[SuiteManifest, tuple[TrialEnvelope, ...]]] = [
        (_m20(), _zero_store()),
        (_m20(), _store(_m20(), [_row(MINUS)])),
        (_m20(), (*_zero_store(), _zero_store()[0])),
        (_m20().model_copy(update={"max_rounds": 0}), _zero_store()),
    ]
    for m, trials in cases:
        d = _decide(m, trials)
        assert replay_suite_decision(d, m, trials) is True
        assert replay_suite_decision(d, m, tuple(reversed(trials))) is True


def _tampers() -> dict[str, object]:
    return {
        "verdict without reseal": "unsealed",
        "verdict resealed": "verdict",
        "reasons resealed": "reasons",
        "stopped_at_round resealed": "stopped",
        "history resealed": "history",
        "trials_sha256 resealed": "trials_sha256",
        "trials changed": "trials",
        "manifest changed": "manifest",
    }


@pytest.mark.parametrize("label", list(_tampers()))
def test_replay_is_false_after_any_tamper(label: str) -> None:
    """Contract 5, replay_suite_decision is false unless seal valid and decision identical."""
    m, trials = _m20(), _zero_store()
    d = _decide(m, trials)
    kind = _tampers()[label]
    replay_m, replay_trials = m, trials

    def resealed(**update: object) -> SuiteDecision:
        # Built without validation, so the test does not depend on SuiteDecision validators.
        t = d.model_copy(update=update)
        sealed = t.model_copy(update={"record_sha256": hash_record(digest_payload(t))})
        assert sealed.validate_seal()
        return sealed

    if kind == "unsealed":
        d = d.model_copy(update={"verdict": Verdict.BLOCK})
    elif kind == "verdict":
        d = resealed(verdict=Verdict.BLOCK, exit_code=1)
    elif kind == "reasons":
        d = resealed(reasons=(REASON_NONE,))
    elif kind == "stopped":
        d = resealed(stopped_at_round=3)
    elif kind == "history":
        d = resealed(history=d.history[:3])
    elif kind == "trials_sha256":
        d = resealed(trials_sha256="0" * 64)
    elif kind == "trials":
        replay_trials = trials[: 3 * 2 * N]
    else:
        replay_m = suite_manifest(prior_runs=("another-run",))
    assert replay_suite_decision(d, replay_m, replay_trials) is False


def test_replay_never_raises() -> None:
    """Contract 5: replay_suite_decision never raises."""
    m, trials = _m20(), _zero_store()
    assert replay_suite_decision(SuiteDecision.model_construct(), m, trials) is False
    d = _decide(m, trials)
    assert replay_suite_decision(d, SuiteManifest.model_construct(), trials) is False
    assert replay_suite_decision(d, m, (TrialEnvelope.model_construct(),)) is False


def test_replay_normalises_the_supplied_decision() -> None:
    """Contract 8 item 5: replay_suite_decision rebuilds the decision with
    SuiteDecision.model_validate(decision.model_dump(mode="python")), checks that seal and
    compares the rebuilt decision with decide_suite(manifest, trials). A copy holding the
    plain string "PASS", and one holding the string "20" for n_cells, both rebuild to the
    real decision, so both replay True."""
    m, trials = _m20(), _zero_store()
    d = _decide(m, trials)
    assert d.verdict is Verdict.PASS and d.n_cells == 20

    as_text = d.model_copy(update={"verdict": "PASS"})
    assert as_text.verdict is not Verdict.PASS
    assert SuiteDecision.model_validate(as_text.model_dump(mode="python")) == d
    assert replay_suite_decision(as_text, m, trials) is True

    # "20" for n_cells breaks the seal as supplied; the rebuilt record's seal verifies.
    coerced = d.model_copy(update={"n_cells": "20"})
    rebuilt = SuiteDecision.model_validate(coerced.model_dump(mode="python"))
    assert not coerced.validate_seal()
    assert rebuilt == d and rebuilt.validate_seal()
    assert replay_suite_decision(coerced, m, trials) is True


@pytest.mark.parametrize(
    "update",
    [
        {"verdict": "MAYBE"},
        {"n_cells": "many"},
        {"schema_version": "arci-suite/2"},
        {"stakes": None},
        {"exit_code": "zero"},
    ],
    ids=["verdict", "n_cells", "schema_version", "stakes", "exit_code"],
)
def test_replay_is_false_for_a_decision_that_cannot_rebuild(update: dict[str, object]) -> None:
    """Contract 8 item 5: a decision that does not rebuild is False."""
    m, trials = _m20(), _zero_store()
    d = _decide(m, trials)
    assert replay_suite_decision(d.model_copy(update=update), m, trials) is False


def test_replay_normalises_but_still_compares() -> None:
    """Contract 8 item 5: normalising is not forgiving. A sealed BLOCK decision whose verdict
    is the plain string "BLOCK" rebuilds and its rebuilt seal verifies, yet it is not the
    decision decide_suite gives for this store, so replay is False."""
    m, trials = _m20(), _zero_store()
    d = _decide(m, trials)
    block = SuiteDecision.model_validate(
        {**d.model_dump(mode="python"), "verdict": Verdict.BLOCK, "exit_code": 1}
    )
    sealed = block.model_copy(update={"record_sha256": hash_record(digest_payload(block))})
    assert sealed.validate_seal()
    as_text = sealed.model_copy(update={"verdict": "BLOCK"})
    assert as_text.verdict is not Verdict.BLOCK
    rebuilt = SuiteDecision.model_validate(as_text.model_dump(mode="python"))
    assert rebuilt == sealed and rebuilt.validate_seal()
    assert rebuilt != d
    assert replay_suite_decision(as_text, m, trials) is False


# --- cost (contract 8 item 6) -------------------------------------------------------------


def test_one_cell_by_five_thousand_rounds_decides_in_under_five_seconds() -> None:
    """Contract 8 item 6: a valid store of 1 cell by 5,000 rounds that never crosses decides
    in under 5 seconds (only decide_suite is timed; building the store is not).

    The differences alternate +1, -1, +1, ..., one pair per round. Per stake q, with
    up = q / (1 - delta) and down = q / (1 + delta), a +1 multiplies the PASS running product
    by f_plus = 1 + up * (1 + delta) and a -1 by f_minus = 1 + up * (delta - 1); the BLOCK
    product by g_plus = 1 - down * (1 + delta) and g_minus = 1 - down * (delta - 1). The exact
    checks below establish f_plus * f_minus < 1, g_plus * g_minus < 1 and 0 < g_plus < 1 for
    both default stakes. Hence after an even round 2k the products are (f_plus * f_minus) ** k
    and (g_plus * g_minus) ** k, both at most 1; after an odd round 2k + 1 they are
    f_plus * (f_plus * f_minus) ** k <= f_plus and g_plus * (g_plus * g_minus) ** k <= g_plus.
    Each wealth is the mean over the stakes of its products, so at every one of the 5,000
    round ends the PASS wealth is at most mean(max(1, f_plus)) and the BLOCK wealth at most 1,
    both below the threshold 40. Spot checks against reference_wealth confirm the algebra.
    """
    bound = Fraction(0)
    for q in STAKES:
        up = q / (1 - DELTA)
        down = q / (1 + DELTA)
        f_plus = 1 + up * (1 + DELTA)
        f_minus = 1 + up * (DELTA - 1)
        g_plus = 1 - down * (1 + DELTA)
        g_minus = 1 - down * (DELTA - 1)
        assert f_plus * f_minus < 1
        assert g_plus * g_minus < 1
        assert 0 < g_plus < 1
        bound += max(Fraction(1), f_plus)
    bound /= len(STAKES)
    assert bound < THRESHOLD and Fraction(1) < THRESHOLD

    rounds = 5000
    for r in (1, 2, 3, 9, 13, 79, 2500, 4999, rounds):
        plus = (r + 1) // 2  # the odd rounds carry the +1 differences
        pass_wealth, block_wealth = reference_wealth(r - plus, 0, plus, ALPHA, DELTA, STAKES)
        assert pass_wealth <= bound < THRESHOLD
        assert block_wealth <= 1 < THRESHOLD

    m = suite_manifest(n_tasks=1, n_conditions=1, max_rounds=rounds, max_errored_pairs=0)
    assert m.n_cells == 1
    trials = _store(m, [_row((1 if r % 2 else -1,)) for r in range(1, rounds + 1)])
    assert len(trials) == 2 * rounds

    start = time.perf_counter()
    d = decide_suite(m, trials)
    elapsed = time.perf_counter() - start

    assert d.verdict is Verdict.INCONCLUSIVE, d.reasons
    assert d.reasons == (REASON_NONE,)
    assert d.stopped_at_round == rounds
    assert len(d.history) == rounds
    last = d.history[-1]
    assert (last.counts.minus, last.counts.zero, last.counts.plus, last.counts.errored) == (
        rounds // 2,
        0,
        (rounds + 1) // 2,
        0,
    )
    assert last.pass_crossed is False and last.block_crossed is False
    assert d.validate_seal()
    assert elapsed < 5.0, f"decide_suite took {elapsed:.2f}s"


# --- no warnings (contract 8 item 7) -------------------------------------------------------


def _warning_cases() -> list[tuple[str, SuiteManifest, tuple[TrialEnvelope, ...]]]:
    """Inputs the gate must handle without emitting a warning, wrong-typed records included."""
    m, good = _m20(), _zero_store()

    def swap(index: int, **update: object) -> tuple[TrialEnvelope, ...]:
        return (*good[:index], good[index].model_copy(update=update), *good[index + 1 :])

    return [
        ("a valid store", m, good),
        ("manifest with a str max_rounds", m.model_copy(update={"max_rounds": "20"}), good),
        ("manifest that cannot rebuild", m.model_copy(update={"max_rounds": 0}), good),
        ("model_construct manifest", SuiteManifest.model_construct(), good),
        ("broken manifest seal", m.model_copy(update={"record_sha256": "0" * 64}), good),
        ("trial outcome as text", m, swap(7, outcome="PASS")),
        ("trial seed as text", m, swap(7, seed=str(good[7].seed))),
        ("trial outcome unknown", m, swap(7, outcome="MAYBE")),
        ("trial seal not a str", m, swap(7, record_sha256=5)),
        ("trial seal as bytes", m, swap(7, record_sha256=good[7].record_sha256.encode())),
        ("lone surrogate in a trial", m, swap(7, failure_detail="\ud800")),
        ("model_construct trial", m, (*good, TrialEnvelope.model_construct())),
        ("empty store", m, ()),
    ]


@pytest.mark.parametrize("label", [case[0] for case in _warning_cases()])
def test_the_gate_emits_no_warnings(label: str) -> None:
    """Contract 8 item 7: the gate emits no Python warning for any input, because its rebuild
    dumps are made with warnings off. Every warning raised inside the block below fails this
    test, whatever the module-level filters say."""
    _, m, trials = next(case for case in _warning_cases() if case[0] == label)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("error")
        d = decide_suite(m, trials)
        replayed = replay_suite_decision(d, m, trials)
    assert isinstance(d, SuiteDecision)
    assert isinstance(replayed, bool)
    assert [str(w.message) for w in caught] == []
