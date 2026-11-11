"""Suite descriptor input paths and exact rule values without changing v1 APIs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arci import descriptor
from arci.schema import Manifest
from arci.suite_schema import SuiteManifest

TEXT = """suite_id: tiny-suite
tasks:
  - {id: a, target: 1}
  - {id: b, target: 2}
  - {id: c, target: 3}
  - {id: d, target: 4}
  - {id: e, target: 5}
baseline: arci.demo.suite:control
candidate: arci.demo.suite:control
toolset: arci.demo.suite:make_world
oracle: arci.demo.suite:oracle
conditions:
  - {id: clean}
  - {id: timeout, fault: {name: tool_timeout, tool: finish}}
  - {id: error, fault: {name: tool_error_once, tool: finish, occurrence: 0}}
  - {id: empty, fault: {name: empty_result, tool: finish}}
"""


def compile_text(text: str, source: str = "<descriptor>") -> SuiteManifest:
    assert hasattr(descriptor, "loads_suite_descriptor"), "suite descriptor API is missing"
    result = descriptor.loads_suite_descriptor(text, source)
    assert isinstance(result, SuiteManifest)
    return result


def test_defaults_and_conditions() -> None:
    m = compile_text(TEXT)
    assert (m.n_cells, m.max_rounds, m.max_errored_pairs) == (20, 20, 4)
    assert (m.alpha, m.delta, m.stakes, m.scenario_seeds) == (
        "1/20",
        "1/10",
        ("1/4", "1/2"),
        "fixed",
    )
    assert [len(c.faults) for c in m.conditions] == [0, 1, 1, 1]
    assert m.tasks[0].task == {"target": 1}
    assert m.validate_seal()


def test_all_optional_keys() -> None:
    m = compile_text(
        TEXT.replace(
            "oracle: arci.demo.suite:oracle",
            "contract: {oracle: arci.demo.suite:oracle, max_tool_calls: 9}",
        )
        + """
rule:
  alpha: 1/10
  delta: 0.2
  stakes: [0.25, 1/2]
  max_rounds: 6
  scenario_seeds: per_round
  max_errored_pairs: 0
  acknowledge_single_round: false
budgets: {max_tool_calls: 9, max_model_steps: 7, max_seconds: 3.0, grader_seconds: 2.0}
fixtures_sha256: fixture-v1
prior_runs: [earlier]
"""
    )
    assert (m.alpha, m.delta, m.stakes) == ("1/10", "1/5", ("1/4", "1/2"))
    assert (m.max_rounds, m.scenario_seeds, m.max_errored_pairs) == (6, "per_round", 0)
    assert m.contract.max_tool_calls == m.budgets.max_tool_calls == 9
    assert m.fixtures_sha256 == "fixture-v1" and m.prior_runs == ("earlier",)


@pytest.mark.parametrize(
    "value,expected",
    [("1/20", "1/20"), ("0.05", "1/20"), ("0.0500", "1/20"), ("1.0e-6", "1/1000000")],
)
def test_exact_rationals(value: str, expected: str) -> None:
    m = compile_text(TEXT + f"rule: {{alpha: {value}, max_rounds: 100}}\n")
    assert m.alpha == expected


@pytest.mark.parametrize(
    "suffix,key,fix",
    [
        ("rule: {alpha: 2/40}", "rule.alpha", "lowest terms"),
        ("rule: {alpha: 0.050000000000000000001}", "rule.alpha", "7 digits"),
        ("rule: {alpha: true}", "rule.alpha", "rational"),
        ("rule: {alpha: 0.8}", "rule.alpha", "1/2"),
        ("rule: {delta: 1/1}", "rule.delta", "(0, 1)"),
        ("rule: {stakes: [1/2, 1/4]}", "rule.stakes", "increasing"),
        ("rule: {max_rounds: 3}", "rule.max_rounds", "increase"),
        ("rule: {max_errored_pairs: 400}", "rule.max_errored_pairs", "reduce"),
        ("rule: {scenario_seeds: unknown}", "rule.scenario_seeds", "per_round"),
        ("rule: {acknowledge_single_round: true}", "rule.acknowledge_single_round", "one round"),
        ("rule: {unknown: 2}", "rule.unknown", "remove"),
        ("unexpected: 2", "unexpected", "remove"),
        ("decisions: {}", "decisions", "remove"),
        ("rule: {max_rounds: '20'}", "rule.max_rounds", "integer"),
    ],
)
def test_rule_errors_name_key_and_fix(suffix: str, key: str, fix: str) -> None:
    with pytest.raises(descriptor.DescriptorError) as caught:
        compile_text(TEXT + suffix + "\n")
    assert key in str(caught.value) and fix in str(caught.value)
    assert len(str(caught.value).splitlines()) == 1


@pytest.mark.parametrize("extension", ["json", "yaml", "jsonl"])
def test_tasks_file_relative_to_descriptor(tmp_path: Path, extension: str) -> None:
    tasks = [{"id": f"task{i}", "target": i} for i in range(5)]
    text = "\n".join(json.dumps(t) for t in tasks) if extension == "jsonl" else json.dumps(tasks)
    path = tmp_path / f"tasks.{extension}"
    path.write_text(text)
    source = str(tmp_path / "arci.yaml")
    inline = TEXT[TEXT.index("baseline:") :]
    m = compile_text(f"suite_id: from-file\ntasks: tasks.{extension}\n" + inline, source)
    assert len(m.tasks) == 5 and m.tasks[-1].task == {"target": 4}


@pytest.mark.parametrize(
    "replacement,key",
    [
        ("tasks: []\n", "tasks"),
        ("tasks: missing.json\n", "tasks"),
        ("tasks: [{target: 1}]\n", "tasks[0].id"),
        ("tasks: [{id: a}, {id: a}]\n", "tasks"),
    ],
)
def test_tasks_errors(replacement: str, key: str) -> None:
    text = "suite_id: tiny-suite\n" + replacement + TEXT[TEXT.index("baseline:") :]
    with pytest.raises(descriptor.DescriptorError) as caught:
        compile_text(text)
    assert key in str(caught.value)


def test_prior_runs_are_sealed_before_execution(tmp_path: Path) -> None:
    assert hasattr(descriptor, "compile_run_descriptor")
    compile_run: Any = descriptor.compile_run_descriptor
    source = tmp_path / "arci.yaml"
    source.write_text(TEXT)
    out = tmp_path / "runs"
    first = compile_run(source, out_dir=out)
    assert isinstance(first, SuiteManifest)
    from arci.suite_storage import SuiteStore

    SuiteStore(out, first)
    second = compile_run(source, out_dir=out)
    assert second.prior_runs == (first.experiment_id,)
    assert second.experiment_id != first.experiment_id and second.validate_seal()
    source.write_text(TEXT.replace("suite_id: tiny-suite", "suite_id: different"))
    assert compile_run(source, out_dir=out).prior_runs == ()
    source.write_text(
        TEXT.replace("candidate: arci.demo.suite:control", "candidate: arci.demo.suite:regression")
    )
    assert compile_run(source, out_dir=out).prior_runs == ()


def test_v1_route_still_returns_v1(tmp_path: Path) -> None:
    assert hasattr(descriptor, "compile_run_descriptor")
    text = "experiment_id: old\n" + TEXT[TEXT.index("baseline:") :]
    source = tmp_path / "v1.yaml"
    source.write_text(text)
    result = descriptor.compile_run_descriptor(source)
    assert isinstance(result, Manifest)
    assert result == descriptor.compile_descriptor(source)


@pytest.mark.parametrize("key", ["max_rounds", "max_errored_pairs"])
def test_explicit_null_rule_is_not_a_default(key: str) -> None:
    with pytest.raises(descriptor.DescriptorError, match=f"rule.{key}"):
        compile_text(TEXT + f"rule: {{{key}: null}}\n")


def test_jsonl_rejects_duplicate_task_keys(tmp_path: Path) -> None:
    (tmp_path / "tasks.jsonl").write_text('{"id":"first", "id":"second"}\n')
    text = "suite_id: x\ntasks: tasks.jsonl\n" + TEXT[TEXT.index("baseline:") :]
    with pytest.raises(descriptor.DescriptorError, match="duplicate"):
        compile_text(text, str(tmp_path / "arci.yaml"))


def test_bad_yaml_v1_keeps_original_error(tmp_path: Path) -> None:
    path = tmp_path / "v1.yaml"
    path.write_text("experiment_id: [\n")
    with pytest.raises(descriptor.DescriptorError) as original:
        descriptor.compile_descriptor(path)
    with pytest.raises(descriptor.DescriptorError) as routed:
        descriptor.compile_run_descriptor(path)
    assert str(routed.value) == str(original.value)


def test_unobservable_contract_error_names_key_and_fix() -> None:
    text = TEXT.replace(
        "oracle: arci.demo.suite:oracle",
        "contract: {oracle: arci.demo.suite:oracle, unobservable: [private_thought]}",
    )
    with pytest.raises(descriptor.DescriptorError) as caught:
        compile_text(text)
    assert "contract.unobservable" in str(caught.value)
    assert "remove" in str(caught.value)
