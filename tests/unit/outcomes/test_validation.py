"""Independent validation cases, fixed reasons, and first-failure ordering."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from arci.outcomes import OutcomeError, decide_outcomes, load_rule
from arci.schema import Verdict

REAL = Path(__file__).parent / "real"


def rule_file(tmp_path: Path, **changes: object) -> Path:
    values: dict[str, object] = {
        "schema_version": "arci-outcomes/1",
        "suite_id": "validation",
        "tasks": ["a", "b"],
        "fixed_before_runs": False,
    }
    values.update(changes)
    path = tmp_path / "rule.yaml"
    path.write_text(yaml.safe_dump(values), encoding="utf-8")
    return path


def write(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return path


def good_csv(tmp_path: Path, name: str = "good.csv") -> Path:
    return write(tmp_path, name, "task_id,outcome\na,pass\nb,pass\n")


def inspect_source(
    *,
    ids: list[object] | None = None,
    scorers: list[str] | None = None,
    value: object = "C",
    epoch: int = 1,
) -> str:
    inventory = ["a", "b"] if ids is None else ids
    names = ["match"] if scorers is None else scorers
    return json.dumps(
        {
            "eval": {
                "config": {"epochs": 1},
                "dataset": {"sample_ids": inventory},
                "scorers": [{"name": name} for name in names],
            },
            "samples": [
                {"id": task, "epoch": epoch, "scores": {name: {"value": value} for name in names}}
                for task in inventory
            ],
        }
    )


@pytest.mark.parametrize(
    "tag,name,source,expected",
    [
        ("E1", "bad.csv", "task_id,outcome\nunknown,pass\n", "unknown task id: unknown"),
        (
            "E2",
            "bad.csv",
            "task_id,outcome\na,pass\na,fail\n",
            "duplicate outcome for baseline a round 1",
        ),
        ("E3", "bad.csv", "task_id,outcome,round\na,pass,201\n", "round 201 is outside 1 to 200"),
        ("E4", "bad.csv", "task_id,outcome,round\na,pass,2\n", "rounds are not contiguous from 1"),
        (
            "E6",
            "bad.csv",
            "task_id,outcome,outcome\na,pass,fail\n",
            "unreadable or unsupported input: {path}",
        ),
        (
            "E7",
            "bad.eval",
            "not read",
            ".eval files are not read: run inspect log dump FILE.eval > FILE.json "
            "and pass the JSON",
        ),
        (
            "E8",
            "bad.txt",
            "task_id,outcome\na,pass\n",
            "{path} has no recognised extension: use --format",
        ),
        (
            "E10",
            "bad.jsonl",
            '{"task_id":"a","outcome":"PASS"}\n',
            "outcome PASS for a cannot be read as pass, fail or error",
        ),
        (
            "E11",
            "bad.json",
            inspect_source(scorers=["match", "includes"]),
            "{path} reports more than one scorer and the rule sets no score",
        ),
        (
            "E14",
            "bad.jsonl",
            '{"task_id":"a","outcome":"pass","round":1}\n{"task_id":"b","outcome":"pass"}\n',
            "{path} gives round on some rows and not others",
        ),
        (
            "E29",
            "bad.xml",
            '<testsuite><testcase classname="c"/></testsuite>',
            "a test case has an empty classname or name: {path}",
        ),
    ],
)
def test_fixed_error_reasons(
    tmp_path: Path,
    tag: str,
    name: str,
    source: str,
    expected: str,
) -> None:
    assert tag.startswith("E")
    rule = rule_file(tmp_path)
    path = write(tmp_path, name, source)
    actual = decide_outcomes(rule, [path], [good_csv(tmp_path)])
    assert actual.verdict is Verdict.ERROR
    assert actual.reasons == (expected.format(path=path),)
    assert actual.exit_code == 3
    assert actual.validate_seal()


def test_e5_arms_supply_different_rounds(tmp_path: Path) -> None:
    a, b = good_csv(tmp_path), good_csv(tmp_path, "more.csv")
    actual = decide_outcomes(rule_file(tmp_path), [a], [a, b])
    assert actual.reasons == ("arms supply different rounds: baseline [1], candidate [1, 2]",)


def test_e9_more_than_one_inspect_log(tmp_path: Path) -> None:
    log = write(tmp_path, "a.json", inspect_source())
    actual = decide_outcomes(rule_file(tmp_path), [log, log], [log])
    assert actual.reasons == ("baseline supplies more than one Inspect log",)


def test_e12_selected_scorer_absent(tmp_path: Path) -> None:
    log = write(tmp_path, "a.json", inspect_source())
    actual = decide_outcomes(rule_file(tmp_path, score="other"), [log], [log])
    assert actual.reasons == (f"the rule's score other is absent from {log}",)


def test_e13_integer_string_collision_across_arms(tmp_path: Path) -> None:
    a = write(tmp_path, "a.json", inspect_source(ids=[7]))
    b = write(tmp_path, "b.json", inspect_source(ids=["7"]))
    actual = decide_outcomes(rule_file(tmp_path, tasks=["7"]), [a], [b])
    assert actual.reasons == ("task id 7 appears as both an integer and a string",)


def test_scorer_is_consistent_across_import(tmp_path: Path) -> None:
    a = write(tmp_path, "a.json", inspect_source(scorers=["match"]))
    b = write(tmp_path, "b.json", inspect_source(scorers=["includes"]))
    actual = decide_outcomes(rule_file(tmp_path), [a], [b])
    assert actual.reasons == (f"the rule's score match is absent from {b}",)


def test_auto_selected_scorer_does_not_hide_ambiguous_later_header(tmp_path: Path) -> None:
    a = write(tmp_path, "a.json", inspect_source())
    b = write(tmp_path, "b.json", inspect_source(scorers=["match", "includes"]))
    actual = decide_outcomes(rule_file(tmp_path), [a], [b])
    assert actual.reasons == (f"{b} reports more than one scorer and the rule sets no score",)


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"schema_version": "bad", "suite_id": "!"}, "schema_version must be arci-outcomes/1"),
        ({"suite_id": "!", "tasks": []}, "suite_id must match SuiteId"),
        ({"tasks": [], "alpha": "bad"}, "tasks must be a non-empty list of non-empty strings"),
        ({"alpha": "1/1", "margin": "bad"}, "alpha must be in [1/1000000, 1/2]"),
        ({"margin": "1/1", "stakes": []}, "margin must be in (0, 1)"),
        ({"stakes": [], "max_rounds": 0}, "stakes must contain 1 to 8 rational strings"),
        (
            {"max_rounds": 50001, "max_errored_pairs": -1},
            "max_rounds must be a positive integer with at most 100000 pairs",
        ),
        (
            {"max_errored_pairs": -1, "score": ""},
            "max_errored_pairs must be an integer within the registered budget",
        ),
        ({"score": "", "pass_at_least": "NaN"}, "score must be a non-empty string"),
        (
            {"pass_at_least": "NaN", "fixed_before_runs": "false"},
            "pass_at_least must be a finite rational n/d",
        ),
        ({"fixed_before_runs": "false", "max_rounds": 1}, "fixed_before_runs must be a boolean"),
        ({"max_rounds": 1}, "budget cannot establish PASS for a candidate that never differs"),
    ],
)
def test_e15_rule_field_order(tmp_path: Path, changes: dict[str, object], reason: str) -> None:
    rule = rule_file(tmp_path, **changes)
    with pytest.raises(OutcomeError) as error:
        load_rule(rule)
    assert error.value.reason == f"the rule file is not a valid arci-outcomes/1 rule: {reason}"
    actual = decide_outcomes(rule, [tmp_path / "absent.csv"], [tmp_path / "absent.csv"])
    assert actual.reasons == (error.value.reason,)
    assert actual.rule is None and actual.rule_sha256 is None


@pytest.mark.parametrize(
    "suffix,source",
    [
        ("csv", "task_id,outcome\na,pass,extra\n"),
        ("csv", 'task_id,outcome\na,"unterminated\n'),
        ("csv", "task_id,outcome,round\na,pass,one\n"),
        ("jsonl", '{"task_id":"a","task_id":"b","outcome":"pass"}\n'),
        ("jsonl", '{"task_id":"a","outcome":"pass","extra":NaN}\n'),
        ("jsonl", '{"task_id":"a","outcome":"pass","extra":{"value":Infinity}}\n'),
        ("jsonl", '{"task_id":"a","outcome":"pass","round":true}\n'),
        ("jsonl", '{"task_id":7,"outcome":"pass"}\n'),
        ("jsonl", '["a","pass"]\n'),
        ("jsonl", '{"task_id":"a"}\n'),
    ],
)
def test_neutral_malformed_records_are_e6(tmp_path: Path, suffix: str, source: str) -> None:
    a = write(tmp_path, f"bad.{suffix}", source)
    actual = decide_outcomes(rule_file(tmp_path), [a], [good_csv(tmp_path)])
    assert actual.reasons == (f"unreadable or unsupported input: {a}",)


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "suite_id",
        "tasks",
        "alpha",
        "margin",
        "stakes",
        "max_rounds",
        "max_errored_pairs",
        "score",
        "pass_at_least",
        "fixed_before_runs",
    ],
)
def test_explicit_null_is_never_a_default(tmp_path: Path, field: str) -> None:
    rule = rule_file(tmp_path, **{field: None})
    with pytest.raises(OutcomeError) as error:
        load_rule(rule)
    assert error.value.reason == (
        f"the rule file is not a valid arci-outcomes/1 rule: {field} must not be null"
    )


def test_duplicate_and_unknown_yaml_keys(tmp_path: Path) -> None:
    path = rule_file(tmp_path)
    original = path.read_text()
    path.write_text(original + "alpha: 1/20\nalpha: 1/10\n")
    with pytest.raises(OutcomeError) as error:
        load_rule(path)
    assert (
        error.value.reason
        == "the rule file is not a valid arci-outcomes/1 rule: duplicate key: alpha"
    )
    path.write_text(original + "other: yes\n")
    with pytest.raises(OutcomeError) as error:
        load_rule(path)
    assert (
        error.value.reason
        == "the rule file is not a valid arci-outcomes/1 rule: unknown rule fields: other"
    )


@pytest.mark.parametrize(
    "earlier,later,expected",
    [
        (
            "task_id,outcome\nunknown,maybe\n",
            "task_id,outcome\na,pass\n",
            "unknown task id: unknown",
        ),
        (
            "task_id,outcome\na,pass\na,maybe\n",
            "task_id,outcome\nb,pass\n",
            "duplicate outcome for baseline a round 1",
        ),
        (
            "task_id,outcome,round\na,maybe,201\n",
            "task_id,outcome\na,pass\n",
            "outcome maybe for a cannot be read as pass, fail or error",
        ),
        (
            "task_id,outcome,round\na,pass,201\n",
            "task_id,outcome\nunknown,pass\n",
            "unknown task id: unknown",
        ),
        (
            "task_id,outcome,round\na,pass,2\n",
            "task_id,outcome,round\na,pass,201\n",
            "round 201 is outside 1 to 200",
        ),
        (
            "task_id,outcome,round\na,pass,2\n",
            "task_id,outcome\na,pass\n",
            "rounds are not contiguous from 1",
        ),
        (
            "task_id,outcome\na,maybe\n",
            "task_id,outcome\nunknown,pass\n",
            "outcome maybe for a cannot be read as pass, fail or error",
        ),
    ],
)
def test_simultaneous_fault_order(
    tmp_path: Path,
    earlier: str,
    later: str,
    expected: str,
) -> None:
    a, b = write(tmp_path, "a.csv", earlier), write(tmp_path, "b.csv", later)
    actual = decide_outcomes(rule_file(tmp_path), [a], [b])
    assert actual.reasons == (expected,)


def test_invalid_rule_precedes_unreadable_input_and_previous(tmp_path: Path) -> None:
    actual = decide_outcomes(
        rule_file(tmp_path, tasks=[]),
        [tmp_path / "missing.csv"],
        [tmp_path / "missing.csv"],
        previous=tmp_path / "missing.json",
    )
    assert actual.reasons == (
        "the rule file is not a valid arci-outcomes/1 rule: "
        "tasks must be a non-empty list of non-empty strings",
    )


def test_bad_previous_precedes_bad_input(tmp_path: Path) -> None:
    bad = write(tmp_path, "bad.csv", "task_id,outcome\nunknown,pass\n")
    previous = write(tmp_path, "old.json", "{}")
    actual = decide_outcomes(rule_file(tmp_path), [bad], [bad], previous=previous)
    assert actual.reasons == (
        "the previous decision is not a usable arci-outcomes/1 decision: invalid record",
    )


def test_validation_error_uses_fixed_empty_template(tmp_path: Path) -> None:
    bad = write(tmp_path, "bad.csv", "task_id,outcome\nunknown,pass\n")
    actual = decide_outcomes(rule_file(tmp_path), [bad], [good_csv(tmp_path)])
    assert actual.rule is not None and actual.rule_sha256 is not None
    assert actual.normalisation == 1
    assert actual.inputs == actual.round_digests == actual.history == actual.tasks == ()
    assert (
        actual.rounds_registered
        == actual.rounds_supplied
        == actual.last_round_evaluated
        == actual.stopped_at_round
        == 0
    )
    assert actual.verdict is Verdict.ERROR and actual.exit_code == 3
    assert actual.notices == () and actual.previous_sha256 is None
    assert actual.statements == (
        "Imported outcomes: ARCI did not run these trials. No fault injection, "
        "fault accounting, tool outcomes or replay.",
    )
    assert actual.validate_seal()


def test_bom_escaped_csv_jsonl_and_ignored_extra_fields(tmp_path: Path) -> None:
    rule = rule_file(tmp_path, tasks=['comma,"quoted"', "line\nnewline"])
    a = write(
        tmp_path,
        "a.csv",
        '\ufefftask_id,outcome,ignored\n"comma,""quoted""",pass,x\n"line\nnewline",fail,y\n',
    )
    b = write(
        tmp_path,
        "b.jsonl",
        "\ufeff"
        + "\n".join(
            [
                json.dumps({"task_id": 'comma,"quoted"', "outcome": "pass", "extra": {"n": 0.5}}),
                json.dumps({"task_id": "line\nnewline", "outcome": "fail", "score": "anything"}),
            ]
        ),
    )
    actual = decide_outcomes(rule, [a], [b])
    assert actual.verdict is Verdict.INCONCLUSIVE
    assert actual.history[0].counts.zero == 2
    assert [item.format for item in actual.inputs] == ["csv", "jsonl"]


def test_explicit_format_overrides_extension_but_auto_never_sniffs(tmp_path: Path) -> None:
    path = write(tmp_path, "input.weird", "task_id,outcome\na,pass\nb,pass\n")
    rule = rule_file(tmp_path)
    assert decide_outcomes(rule, [path], [path]).reasons == (
        f"{path} has no recognised extension: use --format",
    )
    assert decide_outcomes(rule, [path], [path], fmt="csv").verdict is Verdict.INCONCLUSIVE
    disguised = write(tmp_path, "input.json", path.read_text())
    assert decide_outcomes(rule, [disguised], [disguised]).reasons == (
        f"unreadable or unsupported input: {disguised}",
    )


def test_unreadable_utf8_is_e6(tmp_path: Path) -> None:
    path = tmp_path / "bad.xml"
    path.write_bytes(b"\xff\xfe<testsuite/>")
    actual = decide_outcomes(rule_file(tmp_path), [path], [good_csv(tmp_path)])
    assert actual.reasons == (f"unreadable or unsupported input: {path}",)


def test_missing_observations_are_errored_not_observed_ties(tmp_path: Path) -> None:
    a = write(tmp_path, "a.csv", "task_id,outcome\na,pass\n")
    b = good_csv(tmp_path)
    actual = decide_outcomes(rule_file(tmp_path), [a], [b])
    assert actual.verdict is Verdict.INCONCLUSIVE
    assert actual.history[0].counts.errored == 1
    assert actual.history[0].counts.zero == 1
    assert actual.tasks[1].candidate_successes == 1
    assert actual.tasks[1].baseline_successes == 0


def test_real_inspect_through_core(tmp_path: Path) -> None:
    a, b = REAL / "inspect" / "baseline.json", REAL / "inspect" / "candidate.json"
    raw_a, raw_b = json.loads(a.read_text()), json.loads(b.read_text())
    inventory = [str(value) for value in raw_a["eval"]["dataset"]["sample_ids"]]
    rule = rule_file(tmp_path, tasks=inventory, score="match")
    actual = decide_outcomes(rule, [a], [b])
    assert actual.exit_code != 3
    assert actual.rounds_supplied == 3
    independent: dict[tuple[str, int], list[str]] = {}
    for raw in (raw_a, raw_b):
        for row in raw["samples"]:
            value = (
                "error" if isinstance(row.get("error"), dict) else row["scores"]["match"]["value"]
            )
            independent.setdefault((str(row["id"]), row["epoch"]), []).append(value)
    counts = {"minus": 0, "zero": 0, "plus": 0, "errored": 0}
    for (_, round_number), (a_value, b_value) in independent.items():
        if round_number > actual.last_round_evaluated:
            continue
        if "error" in (a_value, b_value):
            counts["errored"] += 1
        else:
            difference = int(b_value == "C") - int(a_value == "C")
            counts[{-1: "minus", 0: "zero", 1: "plus"}[difference]] += 1
    assert actual.history[-1].counts.model_dump() == counts


def test_e15_error_budget_plan_refusal(tmp_path: Path) -> None:
    path = rule_file(tmp_path, max_errored_pairs=400)
    with pytest.raises(OutcomeError) as error:
        load_rule(path)
    assert error.value.reason == (
        "the rule file is not a valid arci-outcomes/1 rule: "
        "PASS unreachable once max_errored_pairs is used"
    )


def test_cross_file_explicit_round_duplicate_is_e2(tmp_path: Path) -> None:
    first = write(tmp_path, "first.csv", "task_id,outcome,round\na,pass,1\n")
    second = write(tmp_path, "second.jsonl", '{"task_id":"a","outcome":"fail","round":1}\n')
    actual = decide_outcomes(rule_file(tmp_path), [first, second], [good_csv(tmp_path)])
    assert actual.reasons == ("duplicate outcome for baseline a round 1",)


def test_empty_neutral_id_is_unregistered(tmp_path: Path) -> None:
    path = write(tmp_path, "a.csv", "task_id,outcome\n,pass\n")
    actual = decide_outcomes(rule_file(tmp_path), [path], [good_csv(tmp_path)])
    assert actual.reasons == ("unknown task id: ",)


def test_empty_labelled_csv_cannot_invent_positional_round(tmp_path: Path) -> None:
    path = write(tmp_path, "a.csv", "task_id,outcome,round\n")
    actual = decide_outcomes(rule_file(tmp_path), [path], [good_csv(tmp_path)])
    assert actual.reasons == (f"unreadable or unsupported input: {path}",)


def test_inspect_scorer_header_failure_precedes_sample_failure(tmp_path: Path) -> None:
    first = write(tmp_path, "a.json", inspect_source())
    second = write(tmp_path, "b.json", inspect_source(scorers=["other"], value="unreadable"))
    actual = decide_outcomes(rule_file(tmp_path), [first], [second])
    assert actual.reasons == (f"the rule's score match is absent from {second}",)


def test_ambiguous_header_remains_e11_before_sample_failure(tmp_path: Path) -> None:
    first = write(tmp_path, "a.json", inspect_source())
    second = write(
        tmp_path, "b.json", inspect_source(scorers=["match", "other"], value="unreadable")
    )
    actual = decide_outcomes(rule_file(tmp_path), [first], [second])
    assert actual.reasons == (f"{second} reports more than one scorer and the rule sets no score",)


def test_inspect_options_do_not_interpret_neutral_outcomes(tmp_path: Path) -> None:
    path = good_csv(tmp_path)
    rule = rule_file(tmp_path, score="ignored", pass_at_least="-1/2")
    actual = decide_outcomes(rule, [path], [path])
    assert actual.history[0].counts.zero == 2
    assert actual.verdict is Verdict.INCONCLUSIVE


def test_rule_missing_required_declaration_refused(tmp_path: Path) -> None:
    path = rule_file(tmp_path)
    raw = yaml.safe_load(path.read_text())
    del raw["fixed_before_runs"]
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(OutcomeError) as error:
        load_rule(path)
    assert error.value.reason == (
        "the rule file is not a valid arci-outcomes/1 rule: fixed_before_runs must be a boolean"
    )


def test_huge_inspect_epoch_count_is_rejected_before_expansion(tmp_path: Path) -> None:
    raw = json.loads(inspect_source())
    raw["eval"]["config"]["epochs"] = 10**12
    path = write(tmp_path, "a.json", json.dumps(raw))
    actual = decide_outcomes(rule_file(tmp_path), [path], [path])
    assert actual.reasons == ("round 201 is outside 1 to 200",)


def test_huge_inspect_epoch_count_does_not_limit_inventory_discovery(tmp_path: Path) -> None:
    from arci.outcomes import discover_rule

    raw = json.loads(inspect_source())
    raw["eval"]["config"]["epochs"] = 10**12
    path = write(tmp_path, "a.json", json.dumps(raw))
    actual = discover_rule([path])
    assert actual.tasks == ("a", "b")
    assert actual.max_rounds == 200
    assert actual.fixed_before_runs is False


def test_import_wide_id_conflict_precedes_later_bad_score(tmp_path: Path) -> None:
    first = write(tmp_path, "a.json", inspect_source(ids=[7]))
    second = write(tmp_path, "b.json", inspect_source(ids=["7"], value="unreadable"))
    actual = decide_outcomes(rule_file(tmp_path, tasks=["7"]), [first], [second])
    assert actual.reasons == ("task id 7 appears as both an integer and a string",)
