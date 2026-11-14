"""Builders and independent oracles for the imported-outcomes acceptance tests.

Every value here is derived from `docs/design/0015-imported-outcomes.md` (the record),
`docs/STATISTICS_OUTCOMES.md` and `plan/exec/v2/tasks/V3-CONTRACT.md`. Nothing imports the
feature under test: the oracles are the frozen kernel (`arci.suite_gate.walk_rounds`,
`arci.suite_stats`) and `arci.hashing.hash_record`, and the fixed strings are transcribed from
the record's "Fixed text" section, unwrapped (the record wraps them "here and nowhere else").
"""

from __future__ import annotations

import csv
import json
from collections.abc import Collection, Iterable, Mapping, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

import yaml

from arci.hashing import hash_record
from arci.suite_gate import RoundIncrement, RoundLook, walk_rounds
from arci.suite_stats import (
    SuiteRule,
    crossed,
    default_max_errored_pairs,
    default_max_rounds,
    wealth,
)

# Real tool outputs (`tests/unit/outcomes/real/README.md`).
REAL = Path(__file__).resolve().parents[1] / "unit" / "outcomes" / "real"

SCHEMA_VERSION = "arci-outcomes/1"  # record, "Record models"
NORMALISATION = 1  # V3 contract, Python names
ARMS = ("baseline", "candidate")
ALPHA, MARGIN, STAKES = "1/20", "1/10", ("1/4", "1/2")

# Record, "Record models": the decision's top-level fields, plus the seal V3 adds to the file.
DECISION_FIELDS = frozenset(
    {
        "schema_version",
        "rule_sha256",
        "rule",
        "normalisation",
        "inputs",
        "rounds_registered",
        "rounds_supplied",
        "last_round_evaluated",
        "round_digests",
        "history",
        "tasks",
        "stopped_at_round",
        "verdict",
        "exit_code",
        "reasons",
        "statements",
        "notices",
        "previous_sha256",
        "record_sha256",
    }
)

# --- fixed text (record, "Fixed text") -------------------------------------------------------

F1 = (
    "Descriptive verdict: the rule file declares it was written after outcomes existed. "
    "The error bound is not claimed."
)
F2 = (
    "Imported outcomes: ARCI did not run these trials. No fault injection, fault accounting, "
    "tool outcomes or replay."
)
F3 = (
    "The error bound depends on six conditions ARCI cannot check: (a) the rule and its task "
    "list were fixed before either evaluated arm ran, which the author declares in the rule "
    "file; (b) outcomes are independent across tasks and rounds, with no response cache shared "
    "across pairs or rounds; (c) each task behaves the same in every round; (d) pairing and "
    "logical round order were fixed before outcomes were observed, and no registered round was "
    "omitted or replaced; (e) infrastructure failures are labelled error, not fail; (f) the "
    "protocol was fixed before execution and both arms were graded by the same criterion."
)
F5 = (
    "Under (a) to (f) and the assumptions of docs/STATISTICS_SUITE.md, a wrong PASS and a "
    "wrong BLOCK each have probability at most alpha/2."
)
F9 = "if every further pair is a non-errored tie, PASS is not reached inside the registered rounds"
F12 = "rounds were assigned from the order of the files given"
F13 = (
    "task ids were extracted from the given files. This does not establish that the rule "
    "preceded the data. Fix the rule before either evaluated arm is run."
)
F15 = "PASS threshold crossed"
F16 = "BLOCK threshold crossed"
W1 = "max_rounds below 3: few looks"

# Inherited suite reasons, "printed unchanged".
PASS_REASON = "non-inferiority established"
BLOCK_REASON = "regression established"
NONE_REASON = "no test crossed"
ERRORED_REASON = "errored pairs exceed max_errored_pairs"
PLAN_NEVER_DIFFERS = "budget cannot establish PASS for a candidate that never differs"
PLAN_UNREACHABLE = "PASS unreachable once max_errored_pairs is used"


def f4(rounds_supplied: int) -> str:
    """F4; `<k>` is `rounds_supplied` (V3 contract, "Statements and notices")."""
    return (
        "ARCI checked the rule, the file structure of every input, the task ids against the "
        f"rule, and that both arms cover rounds 1 to {rounds_supplied}. It did not verify "
        "execution or any of those conditions."
    )


def f6(alpha: str = ALPHA) -> str:
    """F6; `<bound>` is alpha/2 in lowest terms (V3 contract, "Statements and notices")."""
    half = Fraction(alpha) / 2
    return (
        f"at alpha = {alpha}, a wrong PASS and a wrong BLOCK each have probability at most "
        f"{half.numerator}/{half.denominator}"
    )


def f7(supplied: int, registered: int) -> str:
    return f"{supplied} of {registered} registered rounds supplied"


def f8(more_rounds: int, more_pairs: int) -> str:
    return (
        f"if every further pair is a non-errored tie, PASS is reached after {more_rounds} "
        f"more complete rounds ({more_pairs} more pairs)"
    )


def f10(excluded: int) -> str:
    return f"{excluded} rounds after the stopping round were excluded from inference"


def f11(through_round: int) -> str:
    return f"errored pairs through round {through_round}"


def verdict_line(verdict: str, code: int) -> str:
    """V3 contract, "Where text goes"."""
    return f"VERDICT: {verdict} (exit {code})"


# --- the rule file ---------------------------------------------------------------------------


def rule_fields(tasks: Iterable[str], **over: Any) -> dict[str, Any]:
    """The expanded rule of the record's "Record models" table, defaults filled in.

    `max_rounds` defaults to `ceil(400 / n)` and `max_errored_pairs` to
    `ceil(n * max_rounds / 100)`, both recomputed from `n` after any override of either.
    """
    ids = sorted(tasks)
    n = len(ids)
    max_rounds = int(over.pop("max_rounds", default_max_rounds(n)))
    fields: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "suite_id": "imported-outcomes",
        "fixed_before_runs": True,
        "alpha": ALPHA,
        "margin": MARGIN,
        "stakes": list(STAKES),
        "max_rounds": max_rounds,
        "max_errored_pairs": default_max_errored_pairs(n, max_rounds),
        "tasks": ids,
    }
    fields.update(over)
    return fields


def write_rule(path: Path, fields: Mapping[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(dict(fields), sort_keys=False), encoding="utf-8")
    return path


def rule_sha256(fields: Mapping[str, Any]) -> str:
    """Record, Decision item 5: the rule digest is `hash_record` of the expanded rule."""
    return hash_record(dict(fields))


def suite_rule(fields: Mapping[str, Any]) -> SuiteRule:
    """The kernel rule the record's Decision item 2 keeps unchanged; `margin` is the suite delta."""
    return SuiteRule(
        Fraction(str(fields["alpha"])),
        Fraction(str(fields["margin"])),
        tuple(Fraction(str(q)) for q in fields["stakes"]),
        len(fields["tasks"]),
        int(fields["max_rounds"]),
        int(fields["max_errored_pairs"]),
    )


# --- outcome tables --------------------------------------------------------------------------
# A table is one mapping per round, in round order: arm -> {task id: "pass"|"fail"|"error"}.
# A task id absent from an arm's mapping is a missing outcome (record, Decision item 9).

Arm = Mapping[str, str]
Round = Mapping[str, Arm]
Table = Sequence[Round]


def diff_round(
    tasks: Sequence[str],
    diffs: Sequence[int],
    *,
    errored: Collection[int] = (),
    missing: Collection[int] = (),
) -> dict[str, dict[str, str]]:
    """One round from per-task differences, as `suite_helpers.round_trials` reads them.

    `diffs[i]` is candidate minus baseline for `tasks[i]`: +1 candidate passes and baseline
    fails, -1 the reverse, 0 both pass. An index in `errored` makes the candidate `error`; an
    index in `missing` leaves the candidate's outcome out of the file altogether.
    """
    if len(diffs) != len(tasks):
        raise ValueError("one difference per task")
    baseline: dict[str, str] = {}
    candidate: dict[str, str] = {}
    for i, (task, d) in enumerate(zip(tasks, diffs, strict=True)):
        baseline[task] = "fail" if d == 1 else "pass"
        if i in missing:
            continue
        candidate[task] = "error" if i in errored else ("fail" if d == -1 else "pass")
    return {"baseline": baseline, "candidate": candidate}


def increments(tasks: Sequence[str], table: Table) -> list[RoundIncrement]:
    """Record item 9 and STATISTICS_OUTCOMES "Errored pairs, and why missing means errored".

    A pair is errored when either arm's outcome is `error` or absent from the supplied round;
    otherwise the difference is the candidate's pass minus the baseline's. No hard violations
    exist on this path, so the ladder's second step always reads zero.
    """
    out: list[RoundIncrement] = []
    for supplied in table:
        minus = zero = plus = errored = 0
        for task in tasks:
            b = supplied["baseline"].get(task)
            c = supplied["candidate"].get(task)
            if b in (None, "error") or c in (None, "error"):
                errored += 1
                continue
            d = int(c == "pass") - int(b == "pass")
            minus += d == -1
            zero += d == 0
            plus += d == 1
        out.append(RoundIncrement(minus, zero, plus, errored, 0))
    return out


def expected_history(fields: Mapping[str, Any], table: Table) -> tuple[RoundLook, ...]:
    """The kernel's looks: record's "Kernel extraction" says this path decides through it."""
    return walk_rounds(suite_rule(fields), increments(list(fields["tasks"]), table))


def history_json(history: Sequence[RoundLook]) -> list[dict[str, Any]]:
    """`OutcomeRoundLook` as the record's "Record models" lists its fields."""
    return [
        {
            "round": look.round,
            "pairs": look.pairs,
            "counts": {
                "minus": look.counts.minus,
                "zero": look.counts.zero,
                "plus": look.counts.plus,
                "errored": look.counts.errored,
            },
            "pass_wealth": look.pass_wealth,
            "block_wealth": look.block_wealth,
            "pass_crossed": look.pass_crossed,
            "block_crossed": look.block_crossed,
            "verdict": look.verdict.value,
            "reasons": list(look.reasons),
        }
        for look in history
    ]


def task_counts_json(
    tasks: Sequence[str], table: Table, last_round_evaluated: int
) -> list[dict[str, Any]]:
    """`OutcomeTaskCounts`, sorted by `task_id`, over rounds 1 to `last_round_evaluated` only.

    Record item 6: "Every count in the record and in a report, per round and per task, covers
    rounds 1 through `last_round_evaluated`."
    """
    rows: list[dict[str, Any]] = []
    for task in sorted(tasks):
        minus = zero = plus = errored = 0
        base_ok = cand_ok = 0
        for supplied in table[:last_round_evaluated]:
            b = supplied["baseline"].get(task)
            c = supplied["candidate"].get(task)
            base_ok += b == "pass"
            cand_ok += c == "pass"
            if b in (None, "error") or c in (None, "error"):
                errored += 1
                continue
            d = int(c == "pass") - int(b == "pass")
            minus += d == -1
            zero += d == 0
            plus += d == 1
        rows.append(
            {
                "task_id": task,
                "pairs": minus + zero + plus + errored,
                "baseline_successes": base_ok,
                "candidate_successes": cand_ok,
                "counts": {"minus": minus, "zero": zero, "plus": plus, "errored": errored},
            }
        )
    return rows


def round_sha256(tasks: Iterable[str], supplied: Round) -> str:
    """Record item 8, verbatim:

    hash_record({"normalisation": 1, "outcomes": [[arm, task_id, outcome_or_null], ...]})

    over every registered arm and task position, null where absent, sorted by arm then task id.
    """
    outcomes = [
        [arm, task, supplied[arm].get(task)] for arm in sorted(ARMS) for task in sorted(tasks)
    ]
    return hash_record({"normalisation": NORMALISATION, "outcomes": outcomes})


def tie_rounds_to_pass(fields: Mapping[str, Any], look: RoundLook) -> tuple[int, int] | None:
    """F8/F9: the smallest number of further complete rounds of non-errored ties that cross.

    Record item 7, "computed exactly from the current counts", and STATISTICS_OUTCOMES: the
    look is a complete round end, so the figure is a number of whole rounds. Errored pairs are
    already scored as -1 in the PASS wealth, which is why they are folded into `minus` here.
    """
    rule = suite_rule(fields)
    n = rule.n_cells
    minus = look.counts.minus + look.counts.errored
    for more in range(1, rule.max_rounds - look.round + 1):
        if crossed(wealth(minus, look.counts.zero + more * n, look.counts.plus, rule)[0], rule):
            return more, more * n
    return None


# --- neutral CSV and JSONL exports -----------------------------------------------------------


def _rows(tasks: Iterable[str], supplied: Round, arm: str) -> list[tuple[str, str]]:
    return [(task, supplied[arm][task]) for task in tasks if task in supplied[arm]]


def write_csv_per_round(folder: Path, arm: str, tasks: Sequence[str], table: Table) -> list[str]:
    """One file per round per arm, no `round` column: the round comes from file position."""
    paths: list[str] = []
    for r, supplied in enumerate(table, 1):
        path = folder / f"{arm}-r{r}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(("task_id", "outcome"))
            writer.writerows(_rows(tasks, supplied, arm))
        paths.append(str(path))
    return paths


def write_csv(folder: Path, arm: str, tasks: Sequence[str], table: Table) -> list[str]:
    """One file per arm with a `round` column."""
    path = folder / f"{arm}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("task_id", "outcome", "round"))
        for r, supplied in enumerate(table, 1):
            writer.writerows(
                (task, outcome, str(r)) for task, outcome in _rows(tasks, supplied, arm)
            )
    return [str(path)]


def write_jsonl(folder: Path, arm: str, tasks: Sequence[str], table: Table) -> list[str]:
    """One file per arm, one object per line, with a `round` field."""
    path = folder / f"{arm}.jsonl"
    lines: list[str] = []
    for r, supplied in enumerate(table, 1):
        lines.extend(
            json.dumps({"task_id": task, "outcome": outcome, "round": r})
            for task, outcome in _rows(tasks, supplied, arm)
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [str(path)]


EXPORTERS = {
    "csv-per-round": write_csv_per_round,
    "csv-round-column": write_csv,
    "jsonl": write_jsonl,
}


# --- synthetic Inspect AI logs ---------------------------------------------------------------


def inspect_log(
    sample_ids: Sequence[Any],
    epochs: int,
    scorers: Sequence[str],
    samples: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """An Inspect JSON log with the header fields the record requires to be present.

    "The header's `eval.config.epochs`, `eval.dataset.sample_ids` and `eval.scorers[].name`
    must be present and must agree with the samples." The shape follows the real logs in
    `tests/unit/outcomes/real/inspect/`.
    """
    return {
        "version": 2,
        "status": "success",
        "eval": {
            "task": "synthetic",
            "model": "mockllm/model",
            "dataset": {"samples": len(sample_ids), "sample_ids": list(sample_ids)},
            "config": {"epochs": epochs},
            "scorers": [{"name": name} for name in scorers],
        },
        "samples": list(samples),
    }


def inspect_sample(
    sample_id: Any, epoch: int, scores: Mapping[str, Any] | None = None, *, error: bool = False
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": sample_id,
        "epoch": epoch,
        "scores": {name: {"value": value} for name, value in (scores or {}).items()},
    }
    if error:
        body["error"] = {"message": "boom", "traceback": ""}
    return body


def write_json(path: Path, body: Any) -> str:
    path.write_text(json.dumps(body), encoding="utf-8")
    return str(path)


# --- JUnit XML -------------------------------------------------------------------------------


def junit(cases: Iterable[tuple[str, str, str | None]], *, root: str = "testsuites") -> str:
    """A JUnit file from (classname, name, status child or None) triples.

    Record: "`<failure>` is fail, `<error>` is `error` and a `<skipped>` case is `error`".
    """
    body: list[str] = []
    for classname, name, status in cases:
        child = "" if status is None else f"<{status} message='x'>detail</{status}>"
        body.append(f'<testcase classname="{classname}" name="{name}">{child}</testcase>')
    inner = f'<testsuite name="s">{"".join(body)}</testsuite>'
    document = inner if root == "testsuite" else f'<testsuites name="t">{inner}</testsuites>'
    return f'<?xml version="1.0" encoding="utf-8"?>{document}'
