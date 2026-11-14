"""Imported outcomes (`arci verdict`): the kernel, the fixed text, the digests and the refusals.

Written blind against `docs/design/0015-imported-outcomes.md` (the record),
`docs/STATISTICS_OUTCOMES.md` and `plan/exec/v2/tasks/V3-CONTRACT.md`, without reading the
implementation. Every expected value is computed here from the frozen kernel
(`arci.suite_gate.walk_rounds`, `arci.suite_stats`), from `arci.hashing.hash_record` or from the
raw fixture bytes with `json` and `xml.etree.ElementTree`; the feature is never asked for its
own expectation. The comment above each test or group names the passage it comes from.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml

from arci.cli import main
from arci.demo.suite import build_manifest
from arci.hashing import hash_record
from arci.suite_gate import decide_suite
from arci.suite_schema import SuiteDecision
from arci.suite_stats import scored_wealth, wealth_text
from tests.acceptance.outcomes_helpers import (
    BLOCK_REASON,
    DECISION_FIELDS,
    ERRORED_REASON,
    EXPORTERS,
    F1,
    F2,
    F3,
    F5,
    F9,
    F12,
    F13,
    F15,
    F16,
    NONE_REASON,
    NORMALISATION,
    PASS_REASON,
    PLAN_NEVER_DIFFERS,
    PLAN_UNREACHABLE,
    REAL,
    SCHEMA_VERSION,
    W1,
    Table,
    diff_round,
    expected_history,
    f4,
    f6,
    f7,
    f8,
    f10,
    f11,
    history_json,
    inspect_log,
    inspect_sample,
    junit,
    round_sha256,
    rule_fields,
    rule_sha256,
    suite_rule,
    task_counts_json,
    tie_rounds_to_pass,
    verdict_line,
    write_json,
    write_rule,
)
from tests.acceptance.suite_helpers import cell_keys, rounds_trials

pytestmark = pytest.mark.acceptance

TASKS = tuple(f"t{i:02d}" for i in range(10))
EXIT = {"PASS": 0, "BLOCK": 1, "INCONCLUSIVE": 2, "ERROR": 3}
# Record, "Formats": `<failure>` is fail, `<error>` and `<skipped>` are `error`.
JUNIT_STATUS = {"skipped": "error", "error": "error", "failure": "fail"}
EXPORTS = sorted(EXPORTERS)


# --- shared machinery ------------------------------------------------------------------------


def _artifact(path: Path) -> dict[str, Any]:
    body: Any = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(body, dict)
    return body


def _one_error(out: str, err: str) -> str:
    """A validation ERROR prints one `error: ...` line on stderr and nothing on stdout.

    V3 contract, "Where text goes"; record, "Validation and errors": "exit 3, with its fixed
    reason on stderr and no traceback".
    """
    assert out == ""
    assert "Traceback" not in err
    lines = err.splitlines()
    assert len(lines) == 1, err
    assert lines[0].startswith("error: ")
    return lines[0]


def _ties(rounds: int, tasks: Sequence[str] = TASKS) -> list[dict[str, dict[str, str]]]:
    return [diff_round(tasks, [0] * len(tasks)) for _ in range(rounds)]


def _inputs(
    folder: Path, tasks: Sequence[str], table: Table, export: str
) -> tuple[list[str], list[str]]:
    exporter = EXPORTERS[export]
    return (
        exporter(folder, "baseline", list(tasks), table),
        exporter(folder, "candidate", list(tasks), table),
    )


def _setup(
    folder: Path,
    table: Table,
    *,
    tasks: Sequence[str] = TASKS,
    export: str = "csv-round-column",
    **over: Any,
) -> tuple[dict[str, Any], Path, list[str], list[str]]:
    fields = rule_fields(tasks, **over)
    rule = write_rule(folder / "rule.yaml", fields)
    baseline, candidate = _inputs(folder, tasks, table, export)
    return fields, rule, baseline, candidate


def _argv(
    rule: Path | str, baseline: Sequence[str], candidate: Sequence[str], **options: str
) -> list[str]:
    argv = ["verdict", str(rule), "--baseline", *baseline, "--candidate", *candidate]
    for name, value in options.items():
        argv.extend((f"--{name.replace('_', '-')}", value))
    return argv


def _append(path: str, text: str) -> None:
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(text)


def _substitute(path: str, old: str, new: str) -> None:
    body = Path(path).read_text(encoding="utf-8")
    assert old in body
    Path(path).write_text(body.replace(old, new), encoding="utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    body: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(body, dict)
    return body


def _reseal(body: Mapping[str, Any]) -> dict[str, Any]:
    """A validly sealed copy: `record_sha256` is `hash_record` of the rest of the record.

    `arci.schema.Sealed` and `digest_payload`; justified for the written artifact by
    `test_the_artifact_seal_is_hash_record_of_the_record_without_its_seal`.
    """
    draft = {name: value for name, value in body.items() if name != "record_sha256"}
    return {**draft, "record_sha256": hash_record(draft)}


def _rule_matches(written: Mapping[str, Any], fields: Mapping[str, Any]) -> bool:
    """The decision's embedded rule, allowing the two optional fields to be carried as null.

    Record, "Record models": "The decision record may hold null exactly where the model says
    so"; `score` and `pass_at_least` are the only fields whose default is "absent".
    """
    extra = set(written) - set(fields)
    return (
        extra <= {"score", "pass_at_least"}
        and all(written[name] is None for name in extra)
        and all(written[name] == value for name, value in fields.items())
    )


# --- 1. kernel equality: record Decision item 2 and "Kernel extraction" ----------------------
# "The decision rule is the suite rule, unchanged"; "One kernel decides both paths."

ZEROS = (0,) * 20
MINUS = (-1,) * 20
ALTERNATING = (1, -1) * 10


def _demo_outcomes(
    rows: Sequence[Sequence[int]],
) -> tuple[list[str], list[dict[str, dict[str, str]]], SuiteDecision]:
    """The packaged demo suite's trials, read back as imported outcomes.

    Record item 4: "A cell is a task id, a string; a user with fault conditions or variants
    puts them in the id", so each suite (task, condition) cell becomes `task::condition`.
    The suite gate's own decision over the same trials is the oracle for kernel equality.
    """
    manifest = build_manifest()
    trials = rounds_trials(manifest, rows)
    tasks = sorted(f"{task}::{condition}" for task, condition in cell_keys(manifest))
    table: list[dict[str, dict[str, str]]] = [{"baseline": {}, "candidate": {}} for _ in rows]
    for trial in trials:
        # Contract 3, ids: trial_id = f"r{round:06d}:{task}:{condition}:{arm}".
        supplied = table[int(trial.trial_id[1:7]) - 1]
        supplied[trial.arm][f"{trial.task_id}::{trial.condition_id}"] = trial.outcome.value.lower()
    return tasks, table, decide_suite(manifest, trials)


@pytest.mark.parametrize("export", EXPORTS)
@pytest.mark.parametrize(
    ("rows", "verdict"),
    [
        pytest.param([ZEROS] * 4, "PASS", id="pass"),
        pytest.param([MINUS], "BLOCK", id="block"),
        pytest.param([ALTERNATING] * 4, "INCONCLUSIVE", id="inconclusive"),
    ],
)
def test_the_imported_verdict_equals_the_suite_gate_on_the_same_outcomes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    export: str,
    rows: Sequence[Sequence[int]],
    verdict: str,
) -> None:
    manifest = build_manifest()
    tasks, table, suite = _demo_outcomes(rows)
    assert suite.verdict.value == verdict and suite.validate_seal()
    fields, rule, baseline, candidate = _setup(
        tmp_path,
        table,
        tasks=tasks,
        export=export,
        max_rounds=manifest.max_rounds,
        max_errored_pairs=manifest.max_errored_pairs,
    )
    out = tmp_path / "decision.json"
    code = main(_argv(rule, baseline, candidate, json=str(out)))
    captured = capsys.readouterr()
    assert captured.err == ""
    assert code == EXIT[verdict] == suite.exit_code
    assert captured.out.splitlines()[0] == verdict_line(verdict, code)

    body = _artifact(out)
    history = expected_history(fields, table)
    assert body["history"] == history_json(history)
    assert body["verdict"] == verdict
    assert body["exit_code"] == EXIT[verdict]
    assert body["stopped_at_round"] == suite.stopped_at_round
    assert body["last_round_evaluated"] == len(history) == len(suite.history)
    assert body["rounds_registered"] == manifest.max_rounds
    assert body["rounds_supplied"] == len(table)
    assert body["rule_sha256"] == rule_sha256(fields)
    assert body["normalisation"] == NORMALISATION
    assert body["round_digests"] == [
        {"round": r, "outcomes_sha256": round_sha256(tasks, supplied)}
        for r, supplied in enumerate(table, 1)
    ]
    # The suite gate's own looks, field by field: the counts, both wealth strings, both
    # crossing flags, the verdict and the reasons must be the same numbers.
    for look, suite_look in zip(body["history"], suite.history, strict=True):
        assert look["round"] == suite_look.round
        assert look["pairs"] == suite_look.pairs
        assert look["counts"] == suite_look.counts.model_dump(mode="json")
        assert look["pass_wealth"] == suite_look.pass_wealth
        assert look["block_wealth"] == suite_look.block_wealth
        assert look["pass_crossed"] == suite_look.pass_crossed
        assert look["block_crossed"] == suite_look.block_crossed
        assert look["verdict"] == suite_look.verdict.value
        assert look["reasons"] == list(suite_look.reasons)
    assert body["reasons"] == list(suite.reasons)
    assert body["tasks"] == task_counts_json(tasks, table, len(history))


# --- 2. exit codes, first lines, reasons and statements --------------------------------------
# Record item 3 and V3 contract, "Where text goes" / "Statements and notices".


def _table_for(verdict: str) -> list[dict[str, dict[str, str]]]:
    """Four outcome tables for a 10-task, 8-round rule whose tolerance is one errored pair.

    80 ties cross PASS (the 79-pair floor of STATISTICS_OUTCOMES); 20 minus pairs cross BLOCK;
    alternating pairs cross neither; two errored pairs in round 1 exceed `max_errored_pairs`
    and give the inherited ERROR reason at a round end.
    """
    rows: dict[str, list[list[int]]] = {
        "PASS": [[0] * 10] * 8,
        "BLOCK": [[-1] * 10] * 2,
        "INCONCLUSIVE": [[1, -1] * 5] * 3,
    }
    if verdict == "ERROR":
        return [diff_round(TASKS, [0] * 10, errored=(0, 1))]
    return [diff_round(TASKS, row) for row in rows[verdict]]


@pytest.mark.parametrize("declared", [True, False], ids=["fixed_before_runs", "descriptive"])
@pytest.mark.parametrize("verdict", ["PASS", "BLOCK", "INCONCLUSIVE", "ERROR"])
def test_exit_code_first_lines_and_statements_for_each_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], verdict: str, declared: bool
) -> None:
    table = _table_for(verdict)
    _, rule, baseline, candidate = _setup(tmp_path, table, max_rounds=8, fixed_before_runs=declared)
    out = tmp_path / "decision.json"
    code = main(_argv(rule, baseline, candidate, json=str(out)))
    captured = capsys.readouterr()
    lines = captured.out.splitlines()

    # The verdict and the exit code are identical either way (record item 3).
    assert captured.err == ""
    assert code == EXIT[verdict]
    if declared:
        assert lines[0] == verdict_line(verdict, code)
    else:
        assert lines[0] == F1
        assert lines[1] == verdict_line(verdict, code)

    body = _artifact(out)
    assert body["verdict"] == verdict and body["exit_code"] == code
    supplied = len(table)
    statements = [F2, F3, f4(supplied)]
    if declared:
        statements.extend((F5, f6()))
    else:
        statements.insert(0, F1)
    assert body["statements"] == statements
    # F5 and F6 print only with a true declaration; F2, F3 and F4 always.
    for text in (F2, F3, f4(supplied)):
        assert text in captured.out
    assert (F5 in captured.out) is declared
    assert (f6() in captured.out) is declared
    assert (F1 in captured.out) is not declared

    expected = {
        "PASS": [PASS_REASON] if declared else [F15],
        "BLOCK": [BLOCK_REASON] if declared else [F16],
        "INCONCLUSIVE": [NONE_REASON],
        "ERROR": [ERRORED_REASON],
    }[verdict]
    assert body["reasons"] == expected
    for reason in expected:
        assert reason in captured.out


def test_the_markdown_report_leads_with_the_descriptive_label(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """V3 contract: the Markdown's first non-empty line is F1 when the declaration is false."""
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1), max_rounds=8, fixed_before_runs=False)
    report = tmp_path / "report.md"
    assert main(_argv(rule, baseline, candidate, markdown=str(report))) == 2
    capsys.readouterr()
    text = report.read_text(encoding="utf-8")
    assert next(line for line in text.splitlines() if line.strip()).strip() == F1
    for fixed in (F1, F2, F3, f4(1)):
        assert fixed in text
    assert F5 not in text


def test_a_one_round_rule_gets_the_warning_and_nothing_else(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record, "Record models": "A one-round rule gets W1 and nothing else; there is no
    acknowledgement flag here". 100 ties cross PASS at the first look."""
    tasks = tuple(f"c{i:03d}" for i in range(100))
    fields, rule, baseline, candidate = _setup(tmp_path, _ties(1, tasks), tasks=tasks, max_rounds=1)
    out = tmp_path / "decision.json"
    code = main(_argv(rule, baseline, candidate, json=str(out)))
    captured = capsys.readouterr()
    assert captured.err == ""
    assert code == 0
    body = _artifact(out)
    assert body["verdict"] == "PASS" and body["reasons"] == [PASS_REASON]
    assert body["history"] == history_json(expected_history(fields, _ties(1, tasks)))
    # notices, in order when they apply: W1; F12; F7; F8 or F9; F10; F14 (V3 contract).
    assert body["notices"] == [W1, f7(1, 1)]
    assert W1 in captured.out


# --- 3. fewer rounds than registered: record item 7 ------------------------------------------
# "the smallest number of further complete rounds of non-errored ties that would cross,
# computed exactly from the current counts, or that no such round exists".

FIFTY = tuple(f"c{i:02d}" for i in range(50))


@pytest.mark.parametrize(
    ("tasks", "max_rounds", "diffs"),
    [
        # The record's own example: 50 tasks, eight registered rounds, one round of 50 ties.
        pytest.param(FIFTY, 8, [0] * 50, id="record-example-50x8"),
        pytest.param(TASKS, 8, [0] * 10, id="ten-ties"),
        pytest.param(TASKS, 8, [-1, *([0] * 9)], id="one-minus-never-crosses"),
    ],
)
def test_a_partial_import_is_inconclusive_and_states_the_next_look(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    tasks: Sequence[str],
    max_rounds: int,
    diffs: Sequence[int],
) -> None:
    table = [diff_round(tasks, diffs)]
    fields, rule, baseline, candidate = _setup(tmp_path, table, tasks=tasks, max_rounds=max_rounds)
    out = tmp_path / "decision.json"
    code = main(_argv(rule, baseline, candidate, json=str(out)))
    captured = capsys.readouterr()
    assert captured.err == ""
    assert code == 2
    body = _artifact(out)
    assert body["verdict"] == "INCONCLUSIVE"
    assert body["rounds_supplied"] == 1 and body["rounds_registered"] == max_rounds
    ahead = tie_rounds_to_pass(fields, expected_history(fields, table)[-1])
    look = F9 if ahead is None else f8(*ahead)
    assert body["notices"] == [f7(1, max_rounds), look]
    assert look in captured.out
    assert f7(1, max_rounds) in captured.out
    # One round of 50 ties gives one more complete round, 50 more pairs.
    assert (ahead == (1, 50)) is (len(tasks) == 50)


def test_f8_and_f9_print_for_inconclusive_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record item 7: "F8 and F9 print for INCONCLUSIVE only"."""
    _, rule, baseline, candidate = _setup(tmp_path, _table_for("BLOCK"), max_rounds=8)
    out = tmp_path / "decision.json"
    assert main(_argv(rule, baseline, candidate, json=str(out))) == 1
    captured = capsys.readouterr()
    body = _artifact(out)
    assert body["verdict"] == "BLOCK"
    assert F9 not in captured.out
    assert "PASS is reached after" not in captured.out
    assert all("non-errored tie" not in notice for notice in body["notices"])
    # F7 is printed for every decision reached by inference (V3 contract).
    assert body["notices"][0] == f7(2, 8)


# --- 4. rounds supplied past the stop: record item 6 -----------------------------------------
# "Rounds after that round contribute to no count and the record keeps only their
# `outcomes_sha256`; F10 says how many were excluded."


def test_rounds_after_the_stopping_round_are_excluded_from_every_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    table = [diff_round(TASKS, [-1] * 10) for _ in range(2)]
    table.extend(diff_round(TASKS, [1] * 10) for _ in range(2))
    fields, rule, baseline, candidate = _setup(tmp_path, table, max_rounds=8)
    out = tmp_path / "decision.json"
    code = main(_argv(rule, baseline, candidate, json=str(out)))
    captured = capsys.readouterr()
    assert captured.err == ""
    assert code == 1
    body = _artifact(out)
    history = expected_history(fields, table)
    assert len(history) == 2 and history[-1].verdict.value == "BLOCK"
    assert body["history"] == history_json(history)
    assert body["last_round_evaluated"] == 2
    assert body["rounds_supplied"] == 4 and body["rounds_registered"] == 8
    # Every supplied round keeps its digest, the excluded ones included.
    assert body["round_digests"] == [
        {"round": r, "outcomes_sha256": round_sha256(fields["tasks"], supplied)}
        for r, supplied in enumerate(table, 1)
    ]
    # Counts per task cover rounds 1 to last_round_evaluated only: two minus pairs each,
    # never the two winning rounds that followed.
    assert body["tasks"] == task_counts_json(fields["tasks"], table, 2)
    assert all(row["pairs"] == 2 for row in body["tasks"])
    assert f10(2) in captured.out
    assert f10(2) in body["notices"]
    # F4's <k> is rounds_supplied; F11 labels the errored count with the evaluated round.
    assert f4(4) in body["statements"]
    assert f11(2) in captured.out


def test_a_structural_fault_after_the_stopping_round_is_still_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record item 6 and STATISTICS_OUTCOMES: "a fault in them is ERROR"."""
    table = [diff_round(TASKS, [-1] * 10) for _ in range(2)]
    table.append(diff_round(TASKS, [0] * 10))
    _, rule, baseline, candidate = _setup(tmp_path, table, max_rounds=8)
    _append(baseline[0], "ghost,pass,3\n")
    assert main(_argv(rule, baseline, candidate)) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == "error: unknown task id: ghost"


# --- 5. missing outcomes: record item 9 ------------------------------------------------------
# "A missing outcome in a supplied round is an errored pair, scored as the suite scores errored
# pairs, against both tests, to `max_errored_pairs`, then ERROR."


def test_missing_outcomes_are_errored_pairs_through_the_tolerance_then_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    table = [
        diff_round(TASKS, [0] * 10, missing=(0,)),
        diff_round(TASKS, [0] * 10, missing=(1, 2)),
    ]
    fields, rule, baseline, candidate = _setup(tmp_path, table, max_rounds=8)
    assert fields["max_errored_pairs"] == 1
    out = tmp_path / "decision.json"
    code = main(_argv(rule, baseline, candidate, json=str(out)))
    captured = capsys.readouterr()
    assert captured.err == ""
    assert code == 3
    body = _artifact(out)
    assert body["history"] == history_json(expected_history(fields, table))
    assert len(body["history"]) == 2
    assert body["history"][0]["counts"] == {"minus": 0, "zero": 9, "plus": 0, "errored": 1}
    # Round 2 has two missing outcomes: 9 + 8 ties, 1 + 2 errored pairs.
    assert body["history"][1]["counts"] == {"minus": 0, "zero": 17, "plus": 0, "errored": 3}
    # Scored against both tests: -1 in the PASS wealth, +1 in the BLOCK wealth.
    expected_pass, expected_block = scored_wealth(0, 9, 0, 1, suite_rule(fields))
    assert body["history"][0]["pass_wealth"] == wealth_text(expected_pass)
    assert body["history"][0]["block_wealth"] == wealth_text(expected_block)
    assert body["verdict"] == "ERROR" and body["reasons"] == [ERRORED_REASON]
    assert body["last_round_evaluated"] == 2
    assert body["stopped_at_round"] == 0
    assert captured.out.splitlines()[0] == verdict_line("ERROR", 3)


# --- 6. the error tags: record, "Validation and errors" and "Fixed text" ---------------------
# One ordered list; exit 3, the fixed reason on stderr, nothing on stdout, no traceback.
# A path placeholder is asserted as the path was given on the command line.


def test_e1_an_unknown_task_id(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1))
    _append(candidate[0], "ghost,pass,1\n")
    assert main(_argv(rule, baseline, candidate)) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == "error: unknown task id: ghost"


def test_e2_a_duplicate_outcome(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1))
    _append(baseline[0], "t00,pass,1\n")
    assert main(_argv(rule, baseline, candidate)) == 3
    captured = capsys.readouterr()
    assert (
        _one_error(captured.out, captured.err)
        == "error: duplicate outcome for baseline t00 round 1"
    )


def test_e3_a_round_outside_the_registered_range(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record item 6: "excess rounds are refused, not truncated"."""
    fields, rule, baseline, candidate = _setup(tmp_path, _ties(1), max_rounds=8)
    for paths in (baseline, candidate):
        _substitute(paths[0], "t00,pass,1", "t00,pass,99")
    assert main(_argv(rule, baseline, candidate)) == 3
    captured = capsys.readouterr()
    assert (
        _one_error(captured.out, captured.err)
        == f"error: round 99 is outside 1 to {fields['max_rounds']}"
    )


def test_e4_rounds_not_contiguous_from_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, rule, baseline, candidate = _setup(tmp_path, _ties(2), max_rounds=8)
    for paths in (baseline, candidate):
        _substitute(paths[0], ",2\n", ",3\n")
    assert main(_argv(rule, baseline, candidate)) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == "error: rounds are not contiguous from 1"


def test_e5_arms_supplying_different_rounds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The rendering of `<rounds>` is not pinned, so only the fixed prefix is asserted."""
    _, rule, baseline, candidate = _setup(tmp_path, _ties(2), max_rounds=8)
    kept = [
        line
        for line in Path(candidate[0]).read_text(encoding="utf-8").splitlines()
        if not line.endswith(",2")
    ]
    Path(candidate[0]).write_text("\n".join(kept) + "\n", encoding="utf-8")
    assert main(_argv(rule, baseline, candidate)) == 3
    captured = capsys.readouterr()
    line = _one_error(captured.out, captured.err)
    assert line.startswith("error: arms supply different rounds: baseline ")
    assert ", candidate " in line


def test_e6_an_unreadable_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1))
    Path(baseline[0]).write_bytes(b"\x00\x01\x02\xff\xfe")
    assert main(_argv(rule, baseline, candidate)) == 3
    captured = capsys.readouterr()
    assert (
        _one_error(captured.out, captured.err)
        == f"error: unreadable or unsupported input: {baseline[0]}"
    )


def test_e7_an_eval_file_is_not_read(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Record, "What is not in 2.2.0": the `.eval` entries are Zstandard-compressed."""
    rule = write_rule(tmp_path / "rule.yaml", rule_fields(["task-00"]))
    argv = _argv(
        rule,
        [str(REAL / "inspect" / "baseline.eval")],
        [str(REAL / "inspect" / "candidate.eval")],
    )
    assert main(argv) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == (
        "error: .eval files are not read: run inspect log dump FILE.eval > FILE.json "
        "and pass the JSON"
    )


def test_e8_an_unrecognised_extension(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Record, "Choosing the parser": `--format auto` maps by extension only."""
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1))
    odd = tmp_path / "baseline.txt"
    odd.write_text(Path(baseline[0]).read_text(encoding="utf-8"), encoding="utf-8")
    assert main(_argv(rule, [str(odd)], candidate)) == 3
    captured = capsys.readouterr()
    assert (
        _one_error(captured.out, captured.err)
        == f"error: {odd} has no recognised extension: use --format"
    )


def _real_inspect(folder: Path) -> tuple[list[str], str, str]:
    """Copies of the real Inspect logs, and their canonicalised sample ids."""
    paths: list[str] = []
    for arm in ("baseline", "candidate"):
        target = folder / f"{arm}.json"
        target.write_bytes((REAL / "inspect" / f"{arm}.json").read_bytes())
        paths.append(str(target))
    header: Any = json.loads(Path(paths[0]).read_text(encoding="utf-8"))["eval"]
    ids = sorted(str(value) for value in header["dataset"]["sample_ids"])
    return ids, paths[0], paths[1]


def test_e9_more_than_one_inspect_log_for_an_arm(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record, "Formats": "Exactly one log per arm; more than one is E9"."""
    ids, base, cand = _real_inspect(tmp_path)
    second = tmp_path / "baseline-2.json"
    second.write_bytes(Path(base).read_bytes())
    rule = write_rule(tmp_path / "rule.yaml", rule_fields(ids, score="match"))
    assert main(_argv(rule, [base, str(second)], [cand])) == 3
    captured = capsys.readouterr()
    assert (
        _one_error(captured.out, captured.err)
        == "error: baseline supplies more than one Inspect log"
    )


def test_e10_an_outcome_that_cannot_be_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record, "Neutral CSV and JSONL": `outcome` is exactly pass, fail or error, lower case."""
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1))
    _substitute(baseline[0], "t00,pass,1", "t00,PASS,1")
    assert main(_argv(rule, baseline, candidate)) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == (
        "error: outcome PASS for t00 cannot be read as pass, fail or error"
    )


def test_e10_a_numeric_inspect_score_without_pass_at_least(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record: "a number is read only through `pass_at_least`, anything else is E10"."""
    tasks = ["s1", "s2"]
    rule = write_rule(tmp_path / "rule.yaml", rule_fields(tasks, score="match"))
    samples = [inspect_sample(task, 1, {"match": 0.5}) for task in tasks]
    base = write_json(tmp_path / "baseline.json", inspect_log(tasks, 1, ["match"], samples))
    cand = write_json(tmp_path / "candidate.json", inspect_log(tasks, 1, ["match"], samples))
    assert main(_argv(rule, [base], [cand])) == 3
    captured = capsys.readouterr()
    line = _one_error(captured.out, captured.err)
    assert line.startswith("error: outcome ")
    assert line.endswith(" cannot be read as pass, fail or error")
    assert " for s1 " in line


@pytest.mark.parametrize(
    ("threshold", "high", "low"),
    [
        # "its comparison is inclusive", so 1/2 is reached by 0.5 exactly.
        pytest.param("1/2", "pass", "fail", id="inclusive"),
        # "a finite rational, sign allowed", separate from the positive-only suite rationals.
        pytest.param("-1/2", "pass", "pass", id="negative"),
    ],
)
def test_a_numeric_inspect_score_is_read_through_pass_at_least(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    threshold: str,
    high: str,
    low: str,
) -> None:
    """Record, "Record models": "`pass_at_least` has its own finite-rational parser, sign
    allowed ... and its comparison is inclusive"."""
    tasks = ["s1", "s2"]
    fields = rule_fields(tasks, score="match", pass_at_least=threshold)
    rule = write_rule(tmp_path / "rule.yaml", fields)
    base = write_json(
        tmp_path / "baseline.json",
        inspect_log(
            tasks,
            1,
            ["match"],
            [inspect_sample("s1", 1, {"match": 0.5}), inspect_sample("s2", 1, {"match": 0.4})],
        ),
    )
    cand = write_json(
        tmp_path / "candidate.json",
        inspect_log(
            tasks,
            1,
            ["match"],
            [inspect_sample("s1", 1, {"match": 0.4}), inspect_sample("s2", 1, {"match": 0.5})],
        ),
    )
    out = tmp_path / "decision.json"
    assert main(_argv(rule, [base], [cand], json=str(out))) == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    table = [
        {"baseline": {"s1": high, "s2": low}, "candidate": {"s1": low, "s2": high}},
    ]
    body = _artifact(out)
    assert body["history"] == history_json(expected_history(fields, table))
    assert body["tasks"] == task_counts_json(tasks, table, 1)


def test_an_explicit_format_applies_to_every_file_in_the_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record, "Choosing the parser": "An explicit `--format` applies to every file in the
    call", so an extension `auto` would refuse (E8) is read."""
    fields = rule_fields(TASKS, max_rounds=8)
    rule = write_rule(tmp_path / "rule.yaml", fields)
    table = _ties(1)
    baseline, candidate = _inputs(tmp_path, TASKS, table, "csv-round-column")
    renamed: list[list[str]] = []
    for arm, paths in (("baseline", baseline), ("candidate", candidate)):
        target = tmp_path / f"{arm}.txt"
        target.write_text(Path(paths[0]).read_text(encoding="utf-8"), encoding="utf-8")
        renamed.append([str(target)])
    out = tmp_path / "decision.json"
    assert main(_argv(rule, renamed[0], renamed[1], format="csv", json=str(out))) == 2
    assert capsys.readouterr().err == ""
    body = _artifact(out)
    assert body["history"] == history_json(expected_history(fields, table))
    assert [entry["format"] for entry in body["inputs"]] == ["csv", "csv"]


def test_e11_two_scorers_and_no_score_in_the_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record: "One scorer serves the whole import ... the first score present is never
    chosen"."""
    ids, base, cand = _real_inspect(tmp_path)
    rule = write_rule(tmp_path / "rule.yaml", rule_fields(ids))
    assert main(_argv(rule, [base], [cand])) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == (
        f"error: {base} reports more than one scorer and the rule sets no score"
    )


def test_e12_a_score_absent_from_the_log(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ids, base, cand = _real_inspect(tmp_path)
    rule = write_rule(tmp_path / "rule.yaml", rule_fields(ids, score="exact"))
    assert main(_argv(rule, [base], [cand])) == 3
    captured = capsys.readouterr()
    assert (
        _one_error(captured.out, captured.err)
        == f"error: the rule's score exact is absent from {base}"
    )


def test_e13_an_id_as_both_an_integer_and_a_string(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record: "an integer id is canonicalised to its decimal string"."""
    rule = write_rule(tmp_path / "rule.yaml", rule_fields(["7001"], score="match"))
    log = inspect_log(
        [7001, "7001"],
        1,
        ["match"],
        [inspect_sample(7001, 1, {"match": "C"}), inspect_sample("7001", 1, {"match": "C"})],
    )
    base = write_json(tmp_path / "baseline.json", log)
    cand = write_json(tmp_path / "candidate.json", log)
    assert main(_argv(rule, [base], [cand])) == 3
    captured = capsys.readouterr()
    assert (
        _one_error(captured.out, captured.err)
        == "error: task id 7001 appears as both an integer and a string"
    )


def test_e14_round_on_some_rows_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Record: "Within one file either every row carries `round` or none does"."""
    rule = write_rule(tmp_path / "rule.yaml", rule_fields(TASKS))
    _, candidate = _inputs(tmp_path, TASKS, _ties(1), "jsonl")
    base = tmp_path / "mixed.jsonl"
    rows = [{"task_id": task, "outcome": "pass", "round": 1} for task in TASKS]
    del rows[0]["round"]
    base.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    assert main(_argv(rule, [str(base)], candidate)) == 3
    captured = capsys.readouterr()
    assert (
        _one_error(captured.out, captured.err)
        == f"error: {base} gives round on some rows and not others"
    )


def test_e15_a_malformed_rule(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The `<reason>` inside E15 is not pinned except for the two rule-plan reasons."""
    fields = rule_fields(TASKS)
    fields["schema_version"] = "arci-outcomes/2"
    rule = write_rule(tmp_path / "rule.yaml", fields)
    baseline, candidate = _inputs(tmp_path, TASKS, _ties(1), "csv-round-column")
    assert main(_argv(rule, baseline, candidate)) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err).startswith(
        "error: the rule file is not a valid arci-outcomes/1 rule: "
    )


@pytest.mark.parametrize(
    ("over", "reason"),
    [
        # STATISTICS_OUTCOMES: 50 pairs cannot establish PASS by ties (the 79-pair floor).
        pytest.param({"max_rounds": 1, "max_errored_pairs": 0}, PLAN_NEVER_DIFFERS, id="floor"),
        pytest.param({"max_rounds": 8, "max_errored_pairs": 80}, PLAN_UNREACHABLE, id="tolerance"),
    ],
)
def test_e15_carries_the_rule_plan_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], over: dict[str, int], reason: str
) -> None:
    """Record, "Fixed text": `check_rule_plan`'s reasons are the ones quoted inside E15."""
    rule = write_rule(tmp_path / "rule.yaml", rule_fields(TASKS, **over))
    baseline, candidate = _inputs(tmp_path, TASKS, _ties(1), "csv-round-column")
    assert main(_argv(rule, baseline, candidate)) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == (
        f"error: the rule file is not a valid arci-outcomes/1 rule: {reason}"
    )


def test_e16_no_input_files_for_an_arm(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Record, step 1: "a missing or empty `--baseline` or `--candidate` (E16)"."""
    _, rule, _, candidate = _setup(tmp_path, _ties(1))
    assert main(["verdict", str(rule), "--candidate", *candidate]) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == "error: no input files were given for baseline"


def test_e16_an_empty_baseline_option(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, rule, _, candidate = _setup(tmp_path, _ties(1))
    assert main(["verdict", str(rule), "--baseline", "--candidate", *candidate]) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == "error: no input files were given for baseline"


def test_e17_an_output_that_is_also_an_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1))
    assert main(_argv(rule, baseline, candidate, json=baseline[0])) == 3
    captured = capsys.readouterr()
    assert (
        _one_error(captured.out, captured.err)
        == f"error: {baseline[0]} is both an output and an input, or is named twice"
    )


def test_e17_two_outputs_with_one_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1))
    both = str(tmp_path / "out.json")
    assert main(_argv(rule, baseline, candidate, json=both, markdown=both)) == 3
    captured = capsys.readouterr()
    assert (
        _one_error(captured.out, captured.err)
        == f"error: {both} is both an output and an input, or is named twice"
    )


def test_e18_an_output_directory_that_does_not_exist(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1))
    missing = str(tmp_path / "nowhere" / "out.json")
    assert main(_argv(rule, baseline, candidate, json=missing)) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == (
        f"error: the directory for {missing} does not exist"
    )


def test_e19_an_artifact_that_cannot_be_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record: "Artifacts are written after the decision is complete ... a write failure is
    E19". The report may already have reached stdout by then, so only stderr is pinned here.
    """
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1))
    blocked = tmp_path / "decision.json"
    blocked.mkdir()
    assert main(_argv(rule, baseline, candidate, json=str(blocked))) == 3
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert captured.err.splitlines() == [f"error: cannot write {blocked}"]


def test_e20_a_repeated_option(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Record, "Command grammar": "Each option appears at most once". How `<option>` renders
    is not pinned, so only the fixed tail and the option's name are asserted."""
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1))
    argv = _argv(rule, baseline, candidate)
    argv.extend(("--format", "csv", "--format", "csv"))
    assert main(argv) == 3
    captured = capsys.readouterr()
    line = _one_error(captured.out, captured.err)
    assert line.endswith(" was given more than once")
    assert "format" in line


def test_e21_example_with_another_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Record: "`--example` excludes every other input"."""
    _, _, baseline, candidate = _setup(tmp_path, _ties(1))
    assert main(["verdict", "--example", "--baseline", *baseline, "--candidate", *candidate]) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == "error: --example takes no other input"


def test_e22_verdict_rule_refuses_an_existing_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "rule.yaml"
    out.write_text("# already here\n", encoding="utf-8")
    tasks = tmp_path / "tasks.xml"
    tasks.write_text(junit([("c", "a", None)]), encoding="utf-8")
    assert main(["verdict-rule", "--tasks", str(tasks), "--out", str(out)]) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == f"error: --out already exists: {out}"
    assert out.read_text(encoding="utf-8") == "# already here\n"


def test_e29_an_empty_classname_or_name(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Record, "JUnit XML": "The id is `classname::name`, both parts non-empty (E29)"."""
    rule = write_rule(tmp_path / "rule.yaml", rule_fields(["c::a"]))
    base = tmp_path / "baseline.xml"
    cand = tmp_path / "candidate.xml"
    base.write_text(junit([("", "a", None)]), encoding="utf-8")
    cand.write_text(junit([("c", "a", None)]), encoding="utf-8")
    assert main(_argv(rule, [str(base)], [str(cand)])) == 3
    captured = capsys.readouterr()
    assert (
        _one_error(captured.out, captured.err)
        == f"error: a test case has an empty classname or name: {base}"
    )


# --- 7. validation order: record, "Validation and errors", the one ordered list --------------


def test_order_a_repeated_option_precedes_a_missing_arm(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Step 1, in its own order: E20 is listed before E16."""
    _, rule, _, candidate = _setup(tmp_path, _ties(1))
    argv = ["verdict", str(rule), "--candidate", *candidate, "--format", "csv", "--format", "csv"]
    assert main(argv) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err).endswith(" was given more than once")


def test_order_the_command_line_precedes_the_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Step 1 before step 2: a missing arm beats a malformed rule."""
    fields = rule_fields(TASKS)
    fields["suite_id"] = "not a suite id"
    rule = write_rule(tmp_path / "rule.yaml", fields)
    _, candidate = _inputs(tmp_path, TASKS, _ties(1), "csv-round-column")
    assert main(["verdict", str(rule), "--candidate", *candidate]) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == "error: no input files were given for baseline"


def test_order_the_command_line_precedes_the_previous_decision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Step 1 before step 3: an output that is also an input beats an unusable predecessor."""
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1))
    previous = tmp_path / "previous.json"
    previous.write_text("{}", encoding="utf-8")
    argv = _argv(rule, baseline, candidate, json=baseline[0], previous=str(previous))
    assert main(argv) == 3
    captured = capsys.readouterr()
    assert (
        _one_error(captured.out, captured.err)
        == f"error: {baseline[0]} is both an output and an input, or is named twice"
    )


def test_order_the_rule_precedes_the_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Step 2 before step 4: a malformed rule beats an unknown task id."""
    fields = rule_fields(TASKS)
    fields["schema_version"] = "arci-outcomes/2"
    rule = write_rule(tmp_path / "rule.yaml", fields)
    baseline, candidate = _inputs(tmp_path, TASKS, _ties(1), "csv-round-column")
    _append(candidate[0], "ghost,pass,1\n")
    assert main(_argv(rule, baseline, candidate)) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err).startswith(
        "error: the rule file is not a valid arci-outcomes/1 rule: "
    )


def test_order_the_rule_fields_precede_the_rule_plan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record, "Record models": the field order ends "`score`, `pass_at_least`,
    `fixed_before_runs`, then `check_rule_plan`", so an empty `score` is reported first."""
    rule = write_rule(
        tmp_path / "rule.yaml",
        rule_fields(TASKS, max_rounds=1, max_errored_pairs=0, score=""),
    )
    baseline, candidate = _inputs(tmp_path, TASKS, _ties(1), "csv-round-column")
    assert main(_argv(rule, baseline, candidate)) == 3
    captured = capsys.readouterr()
    line = _one_error(captured.out, captured.err)
    assert line.startswith("error: the rule file is not a valid arci-outcomes/1 rule: ")
    assert PLAN_NEVER_DIFFERS not in line
    assert PLAN_UNREACHABLE not in line


def test_order_the_rule_precedes_the_previous_decision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Step 2 before step 3."""
    fields = rule_fields(TASKS)
    fields["schema_version"] = "arci-outcomes/2"
    rule = write_rule(tmp_path / "rule.yaml", fields)
    baseline, candidate = _inputs(tmp_path, TASKS, _ties(1), "csv-round-column")
    previous = tmp_path / "previous.json"
    previous.write_text("{}", encoding="utf-8")
    assert main(_argv(rule, baseline, candidate, previous=str(previous))) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err).startswith(
        "error: the rule file is not a valid arci-outcomes/1 rule: "
    )


def test_order_the_previous_structure_precedes_the_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Step 3 before step 4."""
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1))
    _append(candidate[0], "ghost,pass,1\n")
    previous = tmp_path / "previous.json"
    previous.write_text("{}", encoding="utf-8")
    assert main(_argv(rule, baseline, candidate, previous=str(previous))) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err).startswith(
        "error: the previous decision is not a usable arci-outcomes/1 decision: "
    )


def test_order_the_input_files_precede_the_cross_file_checks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Step 4 before step 5: an unknown id beats a round outside the registered range."""
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1), max_rounds=8)
    _append(candidate[0], "ghost,pass,99\n")
    assert main(_argv(rule, baseline, candidate)) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == "error: unknown task id: ghost"


def test_order_baseline_files_precede_candidate_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Step 4: "in argument order, baseline before candidate"."""
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1))
    _substitute(baseline[0], "t00,pass,1", "t00,PASS,1")
    _append(candidate[0], "ghost,pass,1\n")
    assert main(_argv(rule, baseline, candidate)) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == (
        "error: outcome PASS for t00 cannot be read as pass, fail or error"
    )


def test_order_records_are_read_in_file_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Step 4: "each file's records in file order"."""
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1))
    rows = Path(baseline[0]).read_text(encoding="utf-8").splitlines()
    rows.insert(1, "ghost,pass,1")
    rows.append("t05,pass,1")
    Path(baseline[0]).write_text("\n".join(rows) + "\n", encoding="utf-8")
    assert main(_argv(rule, baseline, candidate)) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == "error: unknown task id: ghost"


# --- 8. the rule digest and the round digests: record items 5 and 8 --------------------------

SPELLED_OUT = """\
schema_version: arci-outcomes/1
suite_id: imported-outcomes
fixed_before_runs: true
alpha: 1/20
margin: 1/10
stakes:
- 1/4
- 1/2
max_rounds: 40
max_errored_pairs: 4
tasks:
""" + "".join(f"- {task}\n" for task in TASKS)

DEFAULTS_OMITTED = """\
schema_version: arci-outcomes/1
suite_id: imported-outcomes
fixed_before_runs: true
tasks:
""" + "".join(f"- {task}\n" for task in TASKS)

REORDERED_TASKS = """\
schema_version: arci-outcomes/1
suite_id: imported-outcomes
fixed_before_runs: true
tasks:
""" + "".join(f"- {task}\n" for task in reversed(TASKS))


def _digest_of(folder: Path, text: str, capsys: pytest.CaptureFixture[str]) -> str:
    """The rule digest the feature reports for one spelling of a rule file."""
    folder.mkdir()
    rule = folder / "rule.yaml"
    rule.write_text(text, encoding="utf-8")
    baseline, candidate = _inputs(folder, TASKS, _ties(1), "csv-round-column")
    out = folder / "decision.json"
    assert main(_argv(rule, baseline, candidate, json=str(out))) == 2
    capsys.readouterr()
    return str(_artifact(out)["rule_sha256"])


def test_the_rule_digest_is_hash_record_of_the_expanded_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record item 5: "the rule digest is `hash_record` of the expanded rule"."""
    fields, rule, baseline, candidate = _setup(tmp_path, _ties(1), max_rounds=8)
    out = tmp_path / "decision.json"
    assert main(_argv(rule, baseline, candidate, json=str(out))) == 2
    captured = capsys.readouterr()
    body = _artifact(out)
    assert body["rule_sha256"] == hash_record(fields) == rule_sha256(fields)
    assert _rule_matches(body["rule"], fields)
    # A well-formed rule's digest appears in every output of that call (STATISTICS_OUTCOMES).
    assert str(body["rule_sha256"]) in captured.out


def test_two_spellings_of_one_rule_give_one_digest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record, "Record models": "defaults are expanded before the digest, so two spellings of
    one rule give one digest"; `tasks` is "stored sorted"."""
    expected = hash_record(rule_fields(TASKS))
    spelled = _digest_of(tmp_path / "spelled", SPELLED_OUT, capsys)
    omitted = _digest_of(tmp_path / "omitted", DEFAULTS_OMITTED, capsys)
    reordered = _digest_of(tmp_path / "reordered", REORDERED_TASKS, capsys)
    assert spelled == omitted == reordered == expected


def test_the_declaration_is_part_of_the_rule_digest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record item 3: "the declaration is a rule field, so the two cases are different
    registrations"."""
    descriptive = SPELLED_OUT.replace("fixed_before_runs: true", "fixed_before_runs: false")
    true_digest = _digest_of(tmp_path / "declared", SPELLED_OUT, capsys)
    false_digest = _digest_of(tmp_path / "descriptive", descriptive, capsys)
    assert true_digest == hash_record(rule_fields(TASKS))
    assert false_digest == hash_record(rule_fields(TASKS, fixed_before_runs=False))
    assert true_digest != false_digest


@pytest.mark.parametrize(
    "spelling", [pytest.param("alpha: 2/40", id="alpha"), pytest.param("margin: 2/20", id="margin")]
)
def test_a_rational_not_in_lowest_terms_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], spelling: str
) -> None:
    """Record, "Record models": every rational field is constrained to "lowest terms"."""
    rule = tmp_path / "rule.yaml"
    rule.write_text(DEFAULTS_OMITTED + spelling + "\n", encoding="utf-8")
    baseline, candidate = _inputs(tmp_path, TASKS, _ties(1), "csv-round-column")
    assert main(_argv(rule, baseline, candidate)) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err).startswith(
        "error: the rule file is not a valid arci-outcomes/1 rule: "
    )


def test_a_round_digest_is_hash_record_of_the_normalised_outcomes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record item 8's payload definition, over every registered arm and task position."""
    table = [diff_round(TASKS, [*([0] * 9), -1]), diff_round(TASKS, [0] * 10, errored=(3,))]
    fields, rule, baseline, candidate = _setup(tmp_path, table, max_rounds=8)
    out = tmp_path / "decision.json"
    assert main(_argv(rule, baseline, candidate, json=str(out))) == 2
    capsys.readouterr()
    assert _artifact(out)["round_digests"] == [
        {"round": 1, "outcomes_sha256": round_sha256(fields["tasks"], table[0])},
        {"round": 2, "outcomes_sha256": round_sha256(fields["tasks"], table[1])},
    ]


def test_a_missing_outcome_and_an_explicit_error_give_different_digests(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record item 8: "`null` where an outcome is absent ... so a missing outcome differs from
    an explicit `error`"."""
    digests: list[str] = []
    tables = [
        [diff_round(TASKS, [0] * 10, errored=(0,))],
        [diff_round(TASKS, [0] * 10, missing=(0,))],
    ]
    for name, table in zip(("errored", "missing"), tables, strict=True):
        folder = tmp_path / name
        folder.mkdir()
        fields, rule, baseline, candidate = _setup(folder, table, max_rounds=8)
        out = folder / "decision.json"
        assert main(_argv(rule, baseline, candidate, json=str(out))) == 2
        capsys.readouterr()
        expected = round_sha256(fields["tasks"], table[0])
        assert _artifact(out)["round_digests"] == [{"round": 1, "outcomes_sha256": expected}]
        digests.append(expected)
    assert digests[0] != digests[1]


def test_the_artifact_seal_is_hash_record_of_the_record_without_its_seal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record: the decision is "sealed like other ARCI records" (`arci.schema.Sealed`)."""
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1), max_rounds=8)
    out = tmp_path / "decision.json"
    assert main(_argv(rule, baseline, candidate, json=str(out))) == 2
    capsys.readouterr()
    body = _artifact(out)
    assert set(body) == DECISION_FIELDS
    assert body == _reseal(body)


# --- 9. `--previous`: record item 8 ----------------------------------------------------------


def _previous(folder: Path, rounds: int, capsys: pytest.CaptureFixture[str], **over: Any) -> Path:
    """A genuine predecessor decision over `rounds` rounds of ties."""
    folder.mkdir()
    _, rule, baseline, candidate = _setup(folder, _ties(rounds), max_rounds=8, **over)
    out = folder / "decision.json"
    assert main(_argv(rule, baseline, candidate, json=str(out))) == 2
    capsys.readouterr()
    return out


def test_previous_accepts_unchanged_earlier_rounds_and_more_rounds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record item 8: "Re-running later with more rounds under the same rule is the intended
    use"; STATISTICS_OUTCOMES: "no second alpha, no correction"."""
    earlier = _previous(tmp_path / "earlier", 2, capsys)
    fields, rule, baseline, candidate = _setup(tmp_path, _ties(4), max_rounds=8)
    out = tmp_path / "decision.json"
    code = main(_argv(rule, baseline, candidate, previous=str(earlier), json=str(out)))
    captured = capsys.readouterr()
    assert captured.err == ""
    assert code == 2
    body = _artifact(out)
    assert body["previous_sha256"] == _artifact(earlier)["record_sha256"]
    assert body["rounds_supplied"] == 4
    assert body["history"] == history_json(expected_history(fields, _ties(4)))


def test_previous_is_null_without_the_option(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record, "Record models": `previous_sha256` is "null without `--previous`"."""
    out = _previous(tmp_path / "only", 2, capsys)
    assert _artifact(out)["previous_sha256"] is None


def test_e23_a_previous_decision_under_another_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Which digest `<digest>` renders is not pinned, so only its shape is asserted."""
    earlier = _previous(tmp_path / "earlier", 2, capsys)
    _, rule, baseline, candidate = _setup(tmp_path, _ties(2), max_rounds=8, fixed_before_runs=False)
    assert main(_argv(rule, baseline, candidate, previous=str(earlier))) == 3
    captured = capsys.readouterr()
    line = _one_error(captured.out, captured.err)
    assert line.startswith("error: the previous decision was made under another rule: ")
    digest = line.rsplit(" ", 1)[1]
    assert len(digest) == 64 and set(digest) <= set("0123456789abcdef")


def test_e24_an_unusable_previous_decision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, rule, baseline, candidate = _setup(tmp_path, _ties(2), max_rounds=8)
    previous = tmp_path / "previous.json"
    previous.write_text(json.dumps({"schema_version": SCHEMA_VERSION}), encoding="utf-8")
    assert main(_argv(rule, baseline, candidate, previous=str(previous))) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err).startswith(
        "error: the previous decision is not a usable arci-outcomes/1 decision: "
    )


def test_e24_a_previous_decision_with_a_broken_seal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record item 8: the predecessor must be "readable, sealed" before anything is compared."""
    earlier = _previous(tmp_path / "earlier", 2, capsys)
    body = _artifact(earlier)
    body["rounds_supplied"] = 3
    earlier.write_text(json.dumps(body), encoding="utf-8")
    _, rule, baseline, candidate = _setup(tmp_path, _ties(4), max_rounds=8)
    assert main(_argv(rule, baseline, candidate, previous=str(earlier))) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err).startswith(
        "error: the previous decision is not a usable arci-outcomes/1 decision: "
    )


def test_e25_a_previous_error_decision(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    folder = tmp_path / "errored"
    folder.mkdir()
    _, first, base, cand = _setup(folder, _table_for("ERROR"), max_rounds=8)
    earlier = folder / "decision.json"
    assert main(_argv(first, base, cand, json=str(earlier))) == 3
    # An ERROR raised at a round end is a decision: its report goes to stdout, not stderr.
    assert capsys.readouterr().err == ""
    assert _artifact(earlier)["verdict"] == "ERROR"
    _, rule, baseline, candidate = _setup(tmp_path, _ties(2), max_rounds=8)
    assert main(_argv(rule, baseline, candidate, previous=str(earlier))) == 3
    captured = capsys.readouterr()
    assert (
        _one_error(captured.out, captured.err)
        == f"error: the previous decision is an ERROR decision: {earlier}"
    )


def test_e26_a_previous_decision_with_more_rounds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    earlier = _previous(tmp_path / "earlier", 4, capsys)
    _, rule, baseline, candidate = _setup(tmp_path, _ties(2), max_rounds=8)
    assert main(_argv(rule, baseline, candidate, previous=str(earlier))) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == (
        "error: the previous decision supplied 4 rounds; this call supplies 2"
    )


def test_e27_a_previous_decision_under_another_normalisation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The forged predecessor is resealed, so `normalisation` is the only thing left wrong."""
    earlier = _previous(tmp_path / "earlier", 2, capsys)
    forged = _reseal({**_artifact(earlier), "normalisation": NORMALISATION + 1})
    earlier.write_text(json.dumps(forged), encoding="utf-8")
    _, rule, baseline, candidate = _setup(tmp_path, _ties(2), max_rounds=8)
    assert main(_argv(rule, baseline, candidate, previous=str(earlier))) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == (
        f"error: the previous decision used normalisation {NORMALISATION + 1}; "
        f"this call uses {NORMALISATION}"
    )


def test_e28_a_round_that_differs_from_the_previous_decision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    earlier = _previous(tmp_path / "earlier", 2, capsys)
    table = [diff_round(TASKS, [0] * 10), diff_round(TASKS, [-1, *([0] * 9)])]
    _, rule, baseline, candidate = _setup(tmp_path, table, max_rounds=8)
    assert main(_argv(rule, baseline, candidate, previous=str(earlier))) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == (
        "error: round 2 differs from the previous decision"
    )


# --- 10. the real fixtures: record, "Formats" ------------------------------------------------


def _inspect_table(
    base: str, cand: str, score: str
) -> tuple[list[str], list[dict[str, dict[str, str]]]]:
    """The outcome table of two Inspect logs, read with `json` only.

    Record: epochs are the rounds, `"C"` is pass and `"I"` is fail, a sample with an `error`
    object is `error`, and an integer id is canonicalised to its decimal string.
    """
    rounds: dict[int, dict[str, dict[str, str]]] = {}
    ids: list[str] = []
    epochs = 0
    for arm, path in (("baseline", base), ("candidate", cand)):
        log: Any = json.loads(Path(path).read_text(encoding="utf-8"))
        epochs = int(log["eval"]["config"]["epochs"])
        ids = sorted(str(value) for value in log["eval"]["dataset"]["sample_ids"])
        for sample in log["samples"]:
            supplied = rounds.setdefault(int(sample["epoch"]), {"baseline": {}, "candidate": {}})
            if sample.get("error"):
                supplied[arm][str(sample["id"])] = "error"
                continue
            value = sample["scores"][score]["value"]
            assert value in ("C", "I")
            supplied[arm][str(sample["id"])] = "pass" if value == "C" else "fail"
    return ids, [rounds[r] for r in range(1, epochs + 1)]


def test_inspect_logs_decide_through_their_epochs_as_rounds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record: "Its rounds are its epochs and it supplies `eval.config.epochs` of them"."""
    ids, base, cand = _real_inspect(tmp_path)
    tasks, table = _inspect_table(base, cand, "match")
    assert tasks == ids and len(table) == 3
    assert "7001" in tasks  # the integer id, canonicalised to a string
    fields = rule_fields(tasks, score="match")
    rule = write_rule(tmp_path / "rule.yaml", fields)
    out = tmp_path / "decision.json"
    code = main(_argv(rule, [base], [cand], json=str(out)))
    captured = capsys.readouterr()
    assert captured.err == ""
    history = expected_history(fields, table)
    assert code == EXIT[history[-1].verdict.value]
    body = _artifact(out)
    assert body["history"] == history_json(history)
    assert body["rounds_supplied"] == 3
    assert body["rounds_registered"] == fields["max_rounds"]
    assert body["tasks"] == task_counts_json(tasks, table, len(history))
    assert body["round_digests"] == [
        {"round": r, "outcomes_sha256": round_sha256(tasks, supplied)}
        for r, supplied in enumerate(table, 1)
    ]
    # The errored sample: `task-03`, epoch 2, in the candidate log.
    assert body["history"][1]["counts"]["errored"] == 1
    errored = next(row for row in body["tasks"] if row["task_id"] == "task-03")
    assert errored["counts"]["errored"] == 1
    # The rounds came from the epoch labels, not from file position, so F12 must not print.
    assert F12 not in captured.out
    assert [entry["rounds"] for entry in body["inputs"]] == [[1, 2, 3], [1, 2, 3]]
    assert [entry["format"] for entry in body["inputs"]] == ["inspect", "inspect"]


def _junit_round(path: Path) -> dict[str, str]:
    """One JUnit file's outcomes, read with `xml.etree.ElementTree` only."""
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for case in root.iter("testcase"):
        task = f"{case.get('classname')}::{case.get('name')}"
        outcome = "pass"
        for child in ("skipped", "error", "failure"):
            if case.find(child) is not None:
                outcome = JUNIT_STATUS[child]
                break
        assert task not in out
        out[task] = outcome
    return out


def _copy(source: Path, target: Path) -> str:
    target.write_bytes(source.read_bytes())
    return str(target)


def test_junit_one_file_is_one_round_for_its_arm(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record: "One file is one round for its arm, from file position", so F12 prints."""
    single = REAL / "pytest" / "single.xml"
    base = _copy(single, tmp_path / "baseline.xml")
    cand = _copy(single, tmp_path / "candidate.xml")
    outcomes = _junit_round(single)
    tasks = sorted(outcomes)
    assert len(tasks) == 6
    table = [{"baseline": outcomes, "candidate": outcomes}]
    fields = rule_fields(tasks)
    rule = write_rule(tmp_path / "rule.yaml", fields)
    out = tmp_path / "decision.json"
    code = main(_argv(rule, [base], [cand], json=str(out)))
    captured = capsys.readouterr()
    assert captured.err == ""
    history = expected_history(fields, table)
    assert code == EXIT[history[-1].verdict.value] == 2
    body = _artifact(out)
    assert body["history"] == history_json(history)
    # `<skipped>` and `<error>` are errored pairs; `<failure>` on both arms is a tie.
    assert body["history"][0]["counts"] == {"minus": 0, "zero": 4, "plus": 0, "errored": 2}
    assert body["notices"][0] == F12
    assert F12 in captured.out
    assert body["inputs"][0]["arm"] == "baseline"
    assert body["inputs"][0]["path"] == base
    assert body["inputs"][0]["rounds"] == [1]
    assert body["inputs"][0]["format"] == "junit"


def test_junit_failure_error_and_skipped_map_to_the_recorded_outcomes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`<failure>` is fail while `<error>` and `<skipped>` are `error`: the baseline's failed
    assertion against a passing candidate is a +1 pair, the two others are errored."""
    single = REAL / "pytest" / "single.xml"
    outcomes = _junit_round(single)
    tasks = sorted(outcomes)
    base = _copy(single, tmp_path / "baseline.xml")
    cand = tmp_path / "candidate.xml"
    cand.write_text(
        junit([(task.split("::")[0], task.split("::")[1], None) for task in tasks]),
        encoding="utf-8",
    )
    table = [{"baseline": outcomes, "candidate": dict.fromkeys(tasks, "pass")}]
    fields = rule_fields(tasks)
    rule = write_rule(tmp_path / "rule.yaml", fields)
    out = tmp_path / "decision.json"
    assert main(_argv(rule, [base], [str(cand)], json=str(out))) == 2
    capsys.readouterr()
    body = _artifact(out)
    assert body["history"] == history_json(expected_history(fields, table))
    assert body["history"][0]["counts"] == {"minus": 0, "zero": 3, "plus": 1, "errored": 2}
    rows = {str(row["task_id"]): row for row in body["tasks"]}
    assert rows["test_sample::test_word[beta]"]["counts"]["plus"] == 1
    assert rows["test_sample::test_word[beta]"]["baseline_successes"] == 0
    assert rows["test_sample::test_word[beta]"]["candidate_successes"] == 1
    assert rows["test_sample::test_skipped"]["counts"]["errored"] == 1
    assert rows["test_sample::test_setup_error"]["counts"]["errored"] == 1


@pytest.mark.parametrize(
    "children",
    [
        pytest.param(("failure", "error"), id="error-outranks-failure"),
        pytest.param(("failure", "skipped"), id="skipped-outranks-failure"),
    ],
)
def test_junit_status_children_that_coexist(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], children: Sequence[str]
) -> None:
    """Record: "when status children coexist `<error>` or `<skipped>` outranks `<failure>`"."""
    inner = "".join(f"<{name} message='x'>d</{name}>" for name in children)
    document = (
        '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="s">'
        f'<testcase classname="c" name="a">{inner}</testcase>'
        '<testcase classname="c" name="b"></testcase></testsuite></testsuites>'
    )
    tasks = ["c::a", "c::b"]
    base = tmp_path / "baseline.xml"
    base.write_text(document, encoding="utf-8")
    cand = tmp_path / "candidate.xml"
    cand.write_text(junit([("c", "a", None), ("c", "b", None)]), encoding="utf-8")
    fields = rule_fields(tasks)
    rule = write_rule(tmp_path / "rule.yaml", fields)
    out = tmp_path / "decision.json"
    assert main(_argv(rule, [str(base)], [str(cand)], json=str(out))) == 2
    capsys.readouterr()
    table = [
        {
            "baseline": {"c::a": "error", "c::b": "pass"},
            "candidate": {"c::a": "pass", "c::b": "pass"},
        }
    ]
    body = _artifact(out)
    assert body["history"] == history_json(expected_history(fields, table))
    assert body["history"][0]["counts"]["errored"] == 1


def test_pytest_repeat_suffixes_stay_literal_task_ids(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record: "Repeat suffixes such as pytest-repeat's `[i-n]` stay literal ids"."""
    repeat = REAL / "pytest" / "repeat.xml"
    outcomes = _junit_round(repeat)
    tasks = sorted(outcomes)
    assert len(tasks) == 18
    assert "test_sample::test_word[beta-2-3]" in tasks
    base = _copy(repeat, tmp_path / "baseline.xml")
    cand = _copy(repeat, tmp_path / "candidate.xml")
    fields = rule_fields(tasks)
    rule = write_rule(tmp_path / "rule.yaml", fields)
    out = tmp_path / "decision.json"
    # Six of the 18 literal ids are a set-up error or a skip in both arms: six errored pairs,
    # above the default tolerance of five, so the round ends in ERROR, not INCONCLUSIVE.
    assert fields["max_errored_pairs"] == 5
    assert main(_argv(rule, [base], [cand], json=str(out))) == 3
    capsys.readouterr()
    body = _artifact(out)
    assert body["history"] == history_json(
        expected_history(fields, [{"baseline": outcomes, "candidate": outcomes}])
    )
    assert body["history"][0]["counts"]["errored"] == 6
    assert body["verdict"] == "ERROR" and body["reasons"] == [ERRORED_REASON]
    assert [str(row["task_id"]) for row in body["tasks"]] == tasks


def test_an_unsuffixed_inventory_fails_to_pair_with_repeat_ids(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record: "pairing fails against an unsuffixed inventory"."""
    repeat = REAL / "pytest" / "repeat.xml"
    base = _copy(repeat, tmp_path / "baseline.xml")
    cand = _copy(repeat, tmp_path / "candidate.xml")
    plain = sorted(_junit_round(REAL / "pytest" / "single.xml"))
    rule = write_rule(tmp_path / "rule.yaml", rule_fields(plain))
    assert main(_argv(rule, [base], [cand])) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err).startswith("error: unknown task id: ")


@pytest.mark.parametrize(
    "document",
    [
        pytest.param(
            '<?xml version="1.0" encoding="utf-8"?><!DOCTYPE testsuites>'
            '<testsuites><testsuite name="s">'
            '<testcase classname="c" name="a"></testcase></testsuite></testsuites>',
            id="doctype",
        ),
        pytest.param(
            '<?xml version="1.0" encoding="utf-8"?>'
            '<!DOCTYPE t [<!ENTITY x "y">]><testsuites><testsuite name="s">'
            '<testcase classname="c" name="a"></testcase></testsuite></testsuites>',
            id="entity",
        ),
        pytest.param(
            '<?xml version="1.0" encoding="iso-8859-1"?><testsuites><testsuite name="s">'
            '<testcase classname="c" name="a"></testcase></testsuite></testsuites>',
            id="encoding-declaration",
        ),
    ],
)
def test_junit_hardening_refuses_doctype_entity_and_another_encoding(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], document: str
) -> None:
    """Record: "an XML declaration naming another encoding, are E6, and the refusal of
    `<!DOCTYPE` and `<!ENTITY` runs on the decoded text". The record does not name a tag for
    the DOCTYPE and ENTITY refusals; E6 is assumed, no other tag covering them."""
    rule = write_rule(tmp_path / "rule.yaml", rule_fields(["c::a"]))
    base = tmp_path / "baseline.xml"
    base.write_text(document, encoding="utf-8")
    cand = tmp_path / "candidate.xml"
    cand.write_text(junit([("c", "a", None)]), encoding="utf-8")
    assert main(_argv(rule, [str(base)], [str(cand)])) == 3
    captured = capsys.readouterr()
    assert (
        _one_error(captured.out, captured.err) == f"error: unreadable or unsupported input: {base}"
    )


def test_junit_bytes_that_are_not_utf8_are_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record: "The file is decoded as UTF-8, a byte-order mark allowed; bytes that are not
    valid UTF-8 ... are E6"."""
    rule = write_rule(tmp_path / "rule.yaml", rule_fields(["c::a"]))
    base = tmp_path / "baseline.xml"
    base.write_bytes(junit([("c", "a", None)]).encode().replace(b'name="a"', b'name="\xff"'))
    cand = tmp_path / "candidate.xml"
    cand.write_text(junit([("c", "a", None)]), encoding="utf-8")
    assert main(_argv(rule, [str(base)], [str(cand)])) == 3
    captured = capsys.readouterr()
    assert (
        _one_error(captured.out, captured.err) == f"error: unreadable or unsupported input: {base}"
    )


def test_a_testsuite_root_is_accepted(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Record: "Root `<testsuite>` or `<testsuites>`, every test case below it visited
    recursively once"."""
    tasks = ["c::a", "c::b"]
    fields = rule_fields(tasks)
    rule = write_rule(tmp_path / "rule.yaml", fields)
    base = tmp_path / "baseline.xml"
    base.write_text(junit([("c", "a", None), ("c", "b", "failure")], root="testsuite"))
    cand = tmp_path / "candidate.xml"
    cand.write_text(junit([("c", "a", None), ("c", "b", None)], root="testsuites"))
    out = tmp_path / "decision.json"
    assert main(_argv(rule, [str(base)], [str(cand)], json=str(out))) == 2
    capsys.readouterr()
    table = [
        {
            "baseline": {"c::a": "pass", "c::b": "fail"},
            "candidate": {"c::a": "pass", "c::b": "pass"},
        }
    ]
    assert _artifact(out)["history"] == history_json(expected_history(fields, table))


@pytest.mark.parametrize(
    ("cases", "task_id"),
    [
        pytest.param([("c", "a", None), ("c", "a", None)], "c::a", id="same-case-twice"),
        # "unique in the file including delimiter collisions": `a::b` + `c` collides with
        # `a` + `b::c`.
        pytest.param([("a::b", "c", None), ("a", "b::c", None)], "a::b::c", id="collision"),
    ],
)
def test_duplicate_junit_ids_are_refused(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    cases: Sequence[tuple[str, str, str | None]],
    task_id: str,
) -> None:
    rule = write_rule(tmp_path / "rule.yaml", rule_fields([task_id]))
    base = tmp_path / "baseline.xml"
    base.write_text(junit(cases), encoding="utf-8")
    cand = tmp_path / "candidate.xml"
    cand.write_text(junit(cases[:1]), encoding="utf-8")
    assert main(_argv(rule, [str(base)], [str(cand)])) == 3
    captured = capsys.readouterr()
    assert (
        _one_error(captured.out, captured.err)
        == f"error: duplicate outcome for baseline {task_id} round 1"
    )


# --- 11. `verdict-rule`: record item 10 and "Command grammar" --------------------------------


def test_verdict_rule_writes_a_complete_rule_that_verdict_accepts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record: "`verdict-rule` writes a rule whose `tasks` are the ids it found ... whose
    `suite_id` defaults to `imported-outcomes`; whose `fixed_before_runs` is always `false`"."""
    single = REAL / "pytest" / "single.xml"
    base = _copy(single, tmp_path / "baseline.xml")
    cand = _copy(single, tmp_path / "candidate.xml")
    out = tmp_path / "rule.yaml"
    assert main(["verdict-rule", "--tasks", base, "--out", str(out)]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert F13 in captured.out
    written = _load_yaml(out)
    tasks = sorted(_junit_round(single))
    assert written["tasks"] == tasks
    assert written["fixed_before_runs"] is False
    assert written["suite_id"] == "imported-outcomes"
    assert written["schema_version"] == SCHEMA_VERSION
    # "writes every field explicitly (defaults expanded)", and a rule file refuses explicit
    # nulls, so the two optional fields are absent.
    assert written == rule_fields(tasks, fixed_before_runs=False)
    # The rule it writes is accepted by `verdict`, which labels it descriptive.
    assert main(_argv(out, [base], [cand])) == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.splitlines()[0] == F1


def test_verdict_rule_deduplicates_ids_across_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record: "deduplicated across files and repetitions after duplicate observations in one
    file have been refused"."""
    single = REAL / "pytest" / "single.xml"
    first = _copy(single, tmp_path / "one.xml")
    second = _copy(single, tmp_path / "two.xml")
    out = tmp_path / "rule.yaml"
    assert main(["verdict-rule", "--tasks", first, second, "--out", str(out)]) == 0
    capsys.readouterr()
    assert _load_yaml(out)["tasks"] == sorted(_junit_round(single))


def test_verdict_rule_canonicalises_an_integer_inspect_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record: "`verdict-rule` lists every id it finds, skipped ones included"."""
    ids, base, _ = _real_inspect(tmp_path)
    out = tmp_path / "rule.yaml"
    assert main(["verdict-rule", "--tasks", base, "--out", str(out), "--score", "match"]) == 0
    capsys.readouterr()
    written = _load_yaml(out)
    assert written["tasks"] == ids
    assert written["tasks"][0] == "7001"
    assert written["score"] == "match"


def test_verdict_rule_applies_no_round_budget_to_what_it_reads(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record: "It applies no round budget to what it reads, because discovering an inventory
    is not a run"; the written `max_rounds` is the default `ceil(400 / n)`."""
    tasks = [f"c::{i:03d}" for i in range(7)]
    source = tmp_path / "tasks.xml"
    source.write_text(junit([("c", f"{i:03d}", None) for i in range(7)]), encoding="utf-8")
    out = tmp_path / "rule.yaml"
    assert main(["verdict-rule", "--tasks", str(source), "--out", str(out)]) == 0
    capsys.readouterr()
    assert _load_yaml(out) == rule_fields(tasks, fixed_before_runs=False)


# --- 12. the JSON artifact: V3 contract, "Where text goes"; record, "Record models" ----------


def test_the_artifact_holds_exactly_the_records_fields(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fields, rule, baseline, candidate = _setup(tmp_path, _ties(1), max_rounds=8)
    out = tmp_path / "decision.json"
    assert main(_argv(rule, baseline, candidate, json=str(out))) == 2
    capsys.readouterr()
    body = _artifact(out)
    assert set(body) == DECISION_FIELDS
    assert body["schema_version"] == SCHEMA_VERSION
    assert len(body["inputs"]) == 2
    assert [entry["arm"] for entry in body["inputs"]] == ["baseline", "candidate"]
    assert [entry["path"] for entry in body["inputs"]] == [baseline[0], candidate[0]]
    assert [entry["format"] for entry in body["inputs"]] == ["csv", "csv"]
    assert _rule_matches(body["rule"], fields)


def test_a_validation_error_after_step_one_writes_the_fixed_empty_template(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Record, "Record models": the fixed empty template "carries every ERROR raised before
    inference: `rule` and `rule_sha256` null for a malformed rule"."""
    fields = rule_fields(TASKS)
    fields["schema_version"] = "arci-outcomes/2"
    rule = write_rule(tmp_path / "rule.yaml", fields)
    baseline, candidate = _inputs(tmp_path, TASKS, _ties(1), "csv-round-column")
    out = tmp_path / "decision.json"
    assert main(_argv(rule, baseline, candidate, json=str(out))) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err).startswith(
        "error: the rule file is not a valid arci-outcomes/1 rule: "
    )
    body = _artifact(out)
    assert set(body) == DECISION_FIELDS
    assert body["rule"] is None and body["rule_sha256"] is None
    assert body["normalisation"] == NORMALISATION
    assert body["inputs"] == []
    assert body["round_digests"] == []
    assert body["history"] == []
    assert body["tasks"] == []
    assert body["rounds_registered"] == 0
    assert body["rounds_supplied"] == 0
    assert body["last_round_evaluated"] == 0
    assert body["stopped_at_round"] == 0
    assert body["verdict"] == "ERROR" and body["exit_code"] == 3
    assert len(body["reasons"]) == 1
    assert body["statements"] == [F2]
    assert body["notices"] == []
    assert body["previous_sha256"] is None
    assert body == _reseal(body)


def test_the_template_of_an_error_raised_after_the_inputs_were_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The record says `statements` holds "F2 with F4 when inputs were validated", but the
    template has no `rounds_supplied` for F4's `<k>`; V3's narrowing (F2 alone) is asserted."""
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1), max_rounds=8)
    _append(candidate[0], "ghost,pass,1\n")
    out = tmp_path / "decision.json"
    assert main(_argv(rule, baseline, candidate, json=str(out))) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == "error: unknown task id: ghost"
    body = _artifact(out)
    assert body["rule"] is not None
    assert body["rule_sha256"] == rule_sha256(rule_fields(TASKS, max_rounds=8))
    assert body["reasons"] == ["unknown task id: ghost"]
    assert body["statements"] == [F2]
    assert body["verdict"] == "ERROR" and body["exit_code"] == 3


def test_the_template_reports_no_registered_rounds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Isolated, because the record contradicts itself: the field table says
    `rounds_registered` is "`max_rounds`, or 0 without a valid rule", while the fixed empty
    template says "`rounds_registered`, `rounds_supplied`, `last_round_evaluated` and
    `stopped_at_round` 0". The template's own definition is taken as the more specific rule."""
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1), max_rounds=8)
    _append(candidate[0], "ghost,pass,1\n")
    out = tmp_path / "decision.json"
    assert main(_argv(rule, baseline, candidate, json=str(out))) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == "error: unknown task id: ghost"
    assert _artifact(out)["rounds_registered"] == 0


@pytest.mark.parametrize(
    "broken", [pytest.param("directory", id="e18"), pytest.param("input", id="e17")]
)
def test_nothing_is_written_for_a_step_one_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], broken: str
) -> None:
    """V3 contract: "For a step 1 failure nothing is written"."""
    _, rule, baseline, candidate = _setup(tmp_path, _ties(1))
    report = tmp_path / "report.md"
    missing = tmp_path / "nowhere" / "out.json"
    target = str(missing) if broken == "directory" else baseline[0]
    expected = (
        f"error: the directory for {missing} does not exist"
        if broken == "directory"
        else f"error: {baseline[0]} is both an output and an input, or is named twice"
    )
    assert main(_argv(rule, baseline, candidate, json=target, markdown=str(report))) == 3
    captured = capsys.readouterr()
    assert _one_error(captured.out, captured.err) == expected
    assert not report.exists()
    assert not missing.exists()
    assert Path(baseline[0]).read_text(encoding="utf-8").startswith("task_id,outcome,round")


# --- 13. no traceback, ever: record, "Validation and errors" ---------------------------------


@pytest.mark.parametrize(
    ("name", "payload", "empty"),
    [
        pytest.param("baseline.csv", b"", True, id="empty-csv"),
        pytest.param("baseline.csv", b"\x00\x01\x02\x80\xff", False, id="binary-csv"),
        pytest.param(
            "baseline.csv", b"task_id,outcome,task_id\nt00,pass,t00\n", False, id="dup-header"
        ),
        pytest.param("baseline.csv", b'task_id,outcome\n"t00,pass\n', False, id="unclosed-quote"),
        pytest.param("baseline.jsonl", b"", True, id="empty-jsonl"),
        pytest.param(
            "baseline.jsonl", b'{"task_id": "t00", "outcome":', False, id="truncated-jsonl"
        ),
        pytest.param("baseline.jsonl", b"[1, 2, 3]\n", False, id="jsonl-not-an-object"),
        pytest.param(
            "baseline.jsonl",
            b'{"task_id": "t00", "outcome": "pass", "task_id": "t01"}\n',
            False,
            id="duplicate-key",
        ),
        pytest.param("baseline.json", b"", False, id="empty-inspect"),
        pytest.param("baseline.json", b"[]", False, id="inspect-wrong-top-level"),
        pytest.param(
            "baseline.json", b'{"eval": {"config": {"epochs"', False, id="truncated-inspect"
        ),
        pytest.param("baseline.json", b"\x00\x01\x02\x80\xff", False, id="binary-inspect"),
        pytest.param("baseline.xml", b"", False, id="empty-junit"),
        pytest.param("baseline.xml", b"<testsuites><testsuite>", False, id="truncated-junit"),
        pytest.param("baseline.xml", b"\x00\x01\x02\x80\xff", False, id="binary-junit"),
    ],
)
def test_a_malformed_input_never_raises_or_prints_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], name: str, payload: bytes, empty: bool
) -> None:
    """Record: "A duplicate header, a duplicate key in one record, a malformed row and a
    non-finite number are E6", and an unreadable or wrongly shaped log is the same refusal.

    A neutral file holding no records at all may instead be refused by step 5, since it leaves
    its arm without round 1; the record does not say which, so both are accepted there.
    """
    rule = write_rule(tmp_path / "rule.yaml", rule_fields(TASKS))
    _, candidate = _inputs(tmp_path, TASKS, _ties(1), "csv-round-column")
    folder = tmp_path / "broken"
    folder.mkdir()
    broken = folder / name
    broken.write_bytes(payload)
    assert main(_argv(rule, [str(broken)], candidate)) == 3
    captured = capsys.readouterr()
    line = _one_error(captured.out, captured.err)
    unreadable = f"error: unreadable or unsupported input: {broken}"
    if empty:
        assert line == unreadable or line.startswith(
            ("error: rounds are not contiguous from 1", "error: arms supply different rounds: ")
        )
    else:
        assert line == unreadable
