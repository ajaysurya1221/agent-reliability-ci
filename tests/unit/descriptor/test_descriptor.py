"""`arci.yaml` compiles to the sealed Manifest a Python builder makes, or fails in one line."""

from __future__ import annotations

import datetime
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from arci.cli import main
from arci.demo.experiment import build_manifest as build_retry
from arci.descriptor import (
    Descriptor,
    DescriptorError,
    bare_arm_label,
    compile_descriptor,
    compile_descriptor_text,
    loads_descriptor,
    parse_yaml,
)
from arci.schema import Bucket, Manifest
from examples.guardrail_agent.experiment import build_manifest as build_guardrail
from examples.guardrail_agent.world import public_task

REPO = Path(__file__).resolve().parents[3]
DOC = REPO / "docs" / "DESCRIPTOR.md"
MOD = "tests.acceptance.fixture_agents"


def _doc_block(heading: str) -> str:
    text = DOC.read_text(encoding="utf-8")
    section = text[text.index(heading) :]
    match = re.search(r"```yaml\n(.*?)```", section, re.S)
    assert match is not None
    return match.group(1)


RETRY = _doc_block("## Example: the retry demo")

SMALL = f"""
experiment_id: exp-yaml
toolset: {MOD}:make_world
oracle: {MOD}:oracle
baseline: {MOD}:good_agent
candidate: {MOD}:fragile_agent
conditions:
  - id: fetch_timeout
    fault: {{name: tool_timeout, tool: fetch, occurrence: 0}}
n_per_arm: 6
"""

GUARDRAIL = """
experiment_id: guardrail-fixture-b-ask-provider_down-50
task_id: guardrail-shell-command-ask
task: TASK_JSON
oracle: examples.guardrail_agent.world:oracle
baseline:
  label: a
  candidate_id: guard-a
  command:
    argv: [PYTHON, -P, -m, examples.guardrail_agent.agent,
           --mcp-config, "{mcp_config}", --task-file, "{task_file}", --variant, a]
    infra_exit_codes: []
candidate:
  label: b
  candidate_id: guard-b
  command:
    argv: [PYTHON, -P, -m, examples.guardrail_agent.agent,
           --mcp-config, "{mcp_config}", --task-file, "{task_file}", --variant, b]
    infra_exit_codes: []
mcp_server:
  name: guardrail
  argv: [PYTHON, -P, -m, arci.mcp_toolset_server,
         --toolset, "examples.guardrail_agent.world:make_world",
         --workdir, "{workdir}", --seed, "{seed}", --task-file, "{task_file}"]
  snapshot: arci.mcp_toolset_server:snapshot
decisions:
  upstream: fixture
  fixture: "examples.guardrail_agent.decisions:fixture"
  model: jev-1.13.0
conditions:
  - id: provider_down
    fault: {name: decision_unavailable, tool: "decision:systemone"}
n_per_arm: 50
base_seed: 31000
budgets: {max_tool_calls: 4, max_model_steps: 10, max_seconds: 30.0, grader_seconds: 10.0}
prior_runs: []
"""


def _append(extra: str) -> Callable[[str], str]:
    return lambda text: text + extra


def _swap(old: str, new: str) -> Callable[[str], str]:
    return lambda text: text.replace(old, new)


def _whole(content: str) -> Callable[[str], str]:
    return lambda _text: content


def _compile(text: str) -> Manifest:
    return compile_descriptor_text(text, "arci.yaml")


def _error(text: str) -> str:
    with pytest.raises(DescriptorError) as caught:
        _compile(text)
    return str(caught.value)


def _semantic(manifest: Manifest) -> dict[str, Any]:
    dumped = manifest.model_dump(mode="json")
    del dumped["created_at"], dumped["record_sha256"]
    return dumped


# --- the two example files ---------------------------------------------------------------------


def test_the_retry_example_seals_byte_equal_to_the_demo_builder() -> None:
    compiled = _compile(RETRY)
    built = build_retry(200, "agent_b")
    assert compiled.record_sha256 == built.record_sha256
    assert compiled.model_dump_json() == built.model_dump_json()
    assert compiled.validate_seal() and compiled.created_at == ""


def test_the_guardrail_example_round_trips_to_its_builder() -> None:
    text = GUARDRAIL.replace("TASK_JSON", json.dumps(public_task("ask"))).replace(
        "PYTHON", json.dumps(sys.executable)
    )
    compiled = _compile(text)
    built = build_guardrail()
    commands = public_task("ask")["commands"]
    assert isinstance(commands, list) and len(commands) == 182
    assert _semantic(compiled) == _semantic(built)
    assert compiled.record_sha256 == built.record_sha256
    # Placeholders stay literal strings in the sealed manifest.
    assert compiled.mcp_server is not None and "{workdir}" in compiled.mcp_server.argv


def test_compile_descriptor_reads_a_file(tmp_path: Path) -> None:
    path = tmp_path / "arci.yaml"
    path.write_text(RETRY, encoding="utf-8")
    assert compile_descriptor(path).record_sha256 == build_retry().record_sha256
    with pytest.raises(DescriptorError, match=r"^descriptor .*missing\.yaml: cannot read: "):
        compile_descriptor(tmp_path / "missing.yaml")


# --- aliases and shorthands -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("short", "long"),
    [
        ("oracle: arci.demo.world:oracle", "contract: {oracle: 'arci.demo.world:oracle'}"),
        ("  - id: reserve-timeout", "  - condition_id: reserve-timeout"),
        ("occurrence: 0}", "at_occurrence: 0}"),
        (
            "    fault: {name: tool_timeout, tool: reserve, occurrence: 0}",
            "    faults: [{name: tool_timeout, tool: reserve, occurrence: 0, bucket: falsify}]",
        ),
    ],
)
def test_an_alias_compiles_like_its_full_key(short: str, long: str) -> None:
    assert short in RETRY
    assert _compile(RETRY.replace(short, long)).record_sha256 == build_retry().record_sha256


@pytest.mark.parametrize(
    ("anchor", "extra", "path", "first", "second"),
    [
        (
            "oracle: arci.demo.world:oracle",
            "\ncontract: {oracle: 'arci.demo.world:oracle'}",
            "oracle",
            "oracle",
            "contract",
        ),
        (
            "  - id: reserve-timeout",
            "\n    condition_id: reserve-timeout",
            "conditions[0].id",
            "id",
            "condition_id",
        ),
        ("occurrence: 0}", "", "conditions[0].fault.occurrence", "occurrence", "at_occurrence"),
        (
            "    fault: {name: tool_timeout, tool: reserve, occurrence: 0}",
            "\n    faults: [{name: tool_timeout, tool: reserve, occurrence: 0}]",
            "conditions[0].fault",
            "fault",
            "faults",
        ),
    ],
)
def test_an_alias_and_its_full_key_are_never_both_accepted(
    anchor: str, extra: str, path: str, first: str, second: str
) -> None:
    replacement = anchor + extra if extra else "occurrence: 0, at_occurrence: 0}"
    message = _error(RETRY.replace(anchor, replacement))
    assert message.startswith(f"descriptor arci.yaml:{path}: ")
    assert f'"{first}"' in message and f'"{second}"' in message


def test_bare_string_arms_and_fault_defaults() -> None:
    manifest = _compile(SMALL)
    assert manifest.baseline.label == "fixture_agents.good_agent"
    assert manifest.baseline.agent == f"{MOD}:good_agent"
    assert manifest.baseline.candidate_id == ""
    assert manifest.candidate.label == "fixture_agents.fragile_agent"
    assert manifest.task_id == "exp-yaml"  # defaults to the experiment id
    fault = manifest.conditions[0].faults[0]
    assert (fault.bucket, fault.params) == (Bucket.FALSIFY, {})
    bare = _compile(SMALL.replace(", tool: fetch, occurrence: 0", "")).conditions[0].faults[0]
    assert (bare.tool, bare.at_occurrence) == (None, None)
    assert bare_arm_label("app.v1:run") == "v1.run"
    assert bare_arm_label("agents:run") == "agents.run"


def test_explicit_task_id_and_a_clean_condition() -> None:
    text = SMALL.replace("experiment_id: exp-yaml", "experiment_id: exp-yaml\ntask_id: other")
    text = text.replace("    fault: {name: tool_timeout, tool: fetch, occurrence: 0}\n", "")
    manifest = _compile(text)
    assert manifest.task_id == "other"
    assert manifest.conditions[0].faults == ()


def test_fixtures_sha256_is_an_opaque_pass_through() -> None:
    manifest = _compile(SMALL + "fixtures_sha256: anything at all\n")
    assert manifest.fixtures_sha256 == "anything at all"


def test_a_custom_fault_factory_is_checked_for_syntax_but_never_imported() -> None:
    text = SMALL.replace("name: tool_timeout", "name: 'nowhere.not_a_module:factory'")
    assert _compile(text).conditions[0].faults[0].name == "nowhere.not_a_module:factory"
    assert "nowhere" not in sys.modules


def test_descriptor_defaults_and_bounds_are_the_manifest_s() -> None:
    ours = Descriptor.model_json_schema()["properties"]
    theirs = Manifest.model_json_schema()["properties"]
    shared = [
        "alpha",
        "delta",
        "n_per_arm",
        "interval_method",
        "looks",
        "base_seed",
        "fixtures_sha256",
        "prior_runs",
        "task",
        "toolset",
    ]
    for key in shared:
        strip = {"description", "title"}
        assert {k: v for k, v in ours[key].items() if k not in strip} == {
            k: v for k, v in theirs[key].items() if k not in strip
        }, key


# --- one-line errors --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (
            _append("n_per_arn: 3\n"),
            'descriptor arci.yaml:n_per_arn: unknown key "n_per_arn"',
        ),
        (
            _swap(f"baseline: {MOD}:good_agent", "baseline: pkg/run"),
            'descriptor arci.yaml:baseline: invalid reference "pkg/run"; expected module:function',
        ),
        (
            _swap("name: tool_timeout", "name: tool_timout"),
            'descriptor arci.yaml:conditions[0].fault.name: unknown fault "tool_timout"; '
            "expected one of decision_low_confidence, decision_unavailable, empty_result, "
            "tool_error_once, tool_timeout or module:function",
        ),
    ],
)
def test_errors_through_main_are_one_line_exit_three_with_empty_stdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    change: Callable[[str], str],
    expected: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("arci.yaml").write_text(change(SMALL), encoding="utf-8")
    assert main(["run", "arci.yaml", "--out", "runs"]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"error: CliError: {expected}\n"
    assert not Path("runs").exists()


@pytest.mark.parametrize("key", ["schema_version", "record_sha256", "created_at", "$schema"])
def test_sealer_owned_keys_are_unknown(key: str) -> None:
    message = _error(SMALL + f'"{key}": x\n')
    assert message.endswith(f'unknown key "{key}"')


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (_swap(f"oracle: {MOD}:oracle", ""), 'oracle: missing required key "oracle"'),
        (
            _swap("  - id: fetch_timeout\n    fault:", "  - fault:"),
            'conditions[0].id: missing required key "id" (or "condition_id")',
        ),
        (_swap("conditions:", "conditions: []\nx:"), ":conditions: "),
        (
            _append("contract: {oracle: 'a:b', unobservable: [mood]}\n"),
            ":oracle: ",  # both given; reported first by source path
        ),
        (_append("looks: [3]\n"), "arci.yaml: looks must start above 0 and end at n_per_arm"),
        (
            _swap("tool: fetch", "tool: 'decision:systemone'"),
            "arci.yaml: tool_timeout cannot target decisions",
        ),
        (
            _swap("name: tool_timeout", "name: decision_unavailable"),
            "arci.yaml: decision_unavailable needs `decisions`",
        ),
        (_append("mcp_server: {argv: [x], snapshot: 'a:b'}\n"), "need `toolset` and no"),
        (_whole("- a list\n"), "arci.yaml: must be one YAML mapping, got list"),
        (_whole(""), "arci.yaml: must be one YAML mapping, got empty"),
        (_whole('a: !!int "zz"\n'), "arci.yaml: invalid YAML at line 1, column 4: invalid integer"),
        (_append("task: [\n"), "arci.yaml: invalid YAML at line "),
        (_append("---\nx: 1\n"), "arci.yaml: invalid YAML at line "),
        (_append("task: {when: !!timestamp 2026-10-13}\n"), "task.when: not a JSON value"),
    ],
)
def test_error_paths_and_messages(change: Callable[[str], str], expected: str) -> None:
    message = _error(change(SMALL))
    assert expected in message
    assert "\n" not in message


def test_unobservable_contract_is_rejected_at_its_path() -> None:
    text = SMALL.replace(
        f"oracle: {MOD}:oracle", f"contract: {{oracle: '{MOD}:oracle', unobservable: [mood]}}"
    )
    assert ":contract.unobservable: invariants outside the tool boundary" in _error(text)


def test_the_first_error_by_source_path_is_reported() -> None:
    text = SMALL + "zzz: 1\nalpha: 7\n"
    assert _error(text).startswith("descriptor arci.yaml:alpha: ")


def test_control_characters_are_escaped_into_one_line() -> None:
    message = _error(SMALL + '"bad\\nkey\\u0007": 1\n')
    assert "\n" not in message and "\x07" not in message
    assert message.endswith('unknown key "bad\\nkey\\u0007"')


def test_descriptor_error_is_a_value_error_with_its_parts() -> None:
    with pytest.raises(ValueError) as caught:
        loads_descriptor(SMALL + "n_per_arn: 3\n", "x.yaml")
    error = caught.value
    assert isinstance(error, DescriptorError)
    assert (error.source, error.path, error.message) == (
        "x.yaml",
        ("n_per_arn",),
        'unknown key "n_per_arn"',
    )


# --- YAML parsing (ruling 3) ------------------------------------------------------------------


def test_the_descriptor_loader_resolves_only_unambiguous_scalars() -> None:
    parsed = parse_yaml(
        "a: yes\nb: no\nc: on\nd: off\ne: True\nf: 010\ng: 0o10\nh: 0x1f\ni: 0b101\n"
        'j: "true"\nk: 2026-10-13\nl: 2026-10-13T10:00:00Z\nm: true\nn: false\no: -42\n'
        "p: 1.5\nq: null\nr: ~\ns: 1:30\nt: 1_000\n"
    )
    assert parsed == {
        "a": "yes",
        "b": "no",
        "c": "on",
        "d": "off",
        "e": "True",
        "f": 10,
        "g": 8,
        "h": 31,
        "i": 5,
        "j": "true",
        "k": "2026-10-13",
        "l": "2026-10-13T10:00:00Z",
        "m": True,
        "n": False,
        "o": -42,
        "p": 1.5,
        "q": None,
        "r": None,
        "s": "1:30",
        "t": "1_000",
    }


def test_the_global_safe_load_is_unchanged() -> None:
    parse_yaml("a: yes\n")
    assert yaml.safe_load("a: yes\nb: 010\nc: 2026-10-13\nd: on\n") == {
        "a": True,
        "b": 8,
        "c": datetime.date(2026, 10, 13),
        "d": True,
    }


def test_yes_in_a_task_stays_a_string_in_the_manifest() -> None:
    text = SMALL + "task: {answer: yes, code: 010, day: 2026-10-13}\n"
    assert _compile(text).task == {"answer": "yes", "code": 10, "day": "2026-10-13"}
