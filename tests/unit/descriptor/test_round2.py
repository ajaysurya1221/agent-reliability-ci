"""T03r2: unencodable integers, every shorthand violation, and depth through shared aliases."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

import pytest
import yaml

from arci.cli import main
from arci.descriptor import (
    MAX_DEPTH,
    DescriptorError,
    compile_descriptor,
    compile_descriptor_text,
    loads_descriptor,
    parse_yaml,
    shorthand_problems,
)

MOD = "tests.acceptance.fixture_agents"

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

LIMIT = sys.get_int_max_str_digits()
TOO_LARGE = f"integer too large to seal: more than {LIMIT} decimal digits"
HUGE_HEX = "0x1" + "0" * 3600  # 16**3600 has about 4335 decimal digits


def _where(text: str) -> str:
    with pytest.raises(DescriptorError) as caught:
        compile_descriptor_text(text, "arci.yaml")
    assert type(caught.value) is DescriptorError
    assert "\n" not in str(caught.value)
    return str(caught.value).removeprefix("descriptor arci.yaml:")


# --- 1. unencodable integers --------------------------------------------------------------------

needs_limit = pytest.mark.skipif(LIMIT == 0, reason="no integer string limit in this interpreter")


@needs_limit
@pytest.mark.parametrize(
    ("extra", "path"),
    [
        (f"task: {{x: {HUGE_HEX}}}\n", "task.x"),
        (f"task: {{x: !!int {HUGE_HEX}}}\n", "task.x"),
        ("task: {x: 1" + "0" * LIMIT + "}\n", "task.x"),
        (f"base_seed: {HUGE_HEX}\n", "base_seed"),
        (f"task: {{x: [1, {{y: {HUGE_HEX}}}]}}\n", "task.x[1].y"),
    ],
    ids=["hex", "tagged-hex", "decimal", "base_seed", "nested"],
)
def test_an_unencodable_integer_is_refused_at_its_path(extra: str, path: str) -> None:
    assert _where(SMALL + extra) == f"{path}: {TOO_LARGE}"
    with pytest.raises(DescriptorError) as caught:
        loads_descriptor(SMALL + extra, "arci.yaml")
    assert str(caught.value) == f"descriptor arci.yaml:{path}: {TOO_LARGE}"


@needs_limit
def test_the_largest_encodable_integer_still_seals() -> None:
    value = int("9" * LIMIT)
    manifest = compile_descriptor_text(SMALL + f"task: {{x: {'9' * LIMIT}}}\n")
    assert manifest.task == {"x": value}
    assert manifest.validate_seal()


@needs_limit
def test_the_cli_reports_an_unencodable_integer_with_exit_three(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("arci.yaml").write_text(SMALL + f"task: {{x: {HUGE_HEX}}}\n", encoding="utf-8")
    assert main(["run", "arci.yaml", "--out", "runs"]) == 3
    err = capsys.readouterr().err
    assert err == f"error: CliError: descriptor arci.yaml:task.x: {TOO_LARGE}\n"
    assert not Path("runs").exists()
    with pytest.raises(DescriptorError):
        compile_descriptor(Path("arci.yaml"))


def test_a_serialization_failure_after_parsing_is_a_descriptor_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(*_args: object, **_kwargs: object) -> str:
        raise ValueError("Exceeds the limit (4300 digits) for integer string conversion")

    monkeypatch.setattr(json, "dumps", refuse)
    with pytest.raises(DescriptorError) as caught:
        loads_descriptor(SMALL, "arci.yaml")
    assert type(caught.value) is DescriptorError
    assert str(caught.value) == (
        "descriptor arci.yaml: not a JSON value: "
        "Exceeds the limit (4300 digits) for integer string conversion"
    )


# --- 2. every shorthand violation of a condition is collected -----------------------------------

BOTH = "  - id: a\n    condition_id: b\n    fault: {name: tool_timeout, FAULT}\n    faults: []\n"
FAULT_MESSAGE = 'conditions[0].fault: "fault" and "faults" both given; give one, not both'


def _conditions(block: str) -> str:
    start = SMALL.index("  - id: fetch_timeout")
    end = SMALL.index("n_per_arm")
    return SMALL[:start] + block + SMALL[end:]


@pytest.mark.parametrize("unknown", ["    g: 1\n", ""])
@pytest.mark.parametrize("fault", ["occurrence: 0", "occurrence: 0, at_occurrence: 1"])
def test_every_condition_violation_is_collected(unknown: str, fault: str) -> None:
    text = _conditions(BOTH.replace("FAULT", fault) + unknown)
    assert _where(text) == FAULT_MESSAGE


def test_shorthand_problems_lists_each_independent_violation() -> None:
    data = parse_yaml(_conditions(BOTH.replace("FAULT", "occurrence: 0, at_occurrence: 1")))
    problems = shorthand_problems(cast(dict[str, object], data))
    assert sorted(path for path, _ in problems) == [
        ("conditions", 0, "fault"),
        ("conditions", 0, "fault", "occurrence"),
        ("conditions", 0, "id"),
    ]


def test_a_null_id_and_a_null_fault_are_both_collected() -> None:
    data = parse_yaml(_conditions("  - id: null\n    fault: null\n"))
    problems = shorthand_problems(cast(dict[str, object], data))
    assert sorted(problems) == [
        (("conditions", 0, "fault"), "must be a mapping; omit it for a clean condition"),
        (("conditions", 0, "id"), "must be a string"),
    ]


# --- 3. the depth limit holds through shared aliases --------------------------------------------


def _chain(links: int) -> str:
    lines = ["task:", "  a0: &a0 []"]
    lines += [f"  a{i}: &a{i} [*a{i - 1}]" for i in range(1, links + 1)]
    return "\n".join(lines) + "\n"


def test_a_chain_of_shared_aliases_cannot_nest_past_the_limit() -> None:
    message = _where(SMALL + _chain(MAX_DEPTH + 1))
    assert message.endswith(f": nested more than {MAX_DEPTH} levels deep")
    assert message.startswith("task.a")
    with pytest.raises(yaml.YAMLError, match=f"nested more than {MAX_DEPTH} levels deep"):
        parse_yaml(_chain(MAX_DEPTH + 1))


def test_a_shared_alias_used_deeper_than_its_first_use_is_measured_again() -> None:
    # `v` is first met two levels down; its second use puts its leaf at depth MAX_DEPTH + 1.
    inner = "[" * (MAX_DEPTH - 3) + "1" + "]" * (MAX_DEPTH - 3)
    text = SMALL + f"task: {{a: &v {inner}, b: [[*v]]}}\n"
    assert _where(text) == f"task.b[0][0]: nested more than {MAX_DEPTH} levels deep"
    assert compile_descriptor_text(SMALL + f"task: {{a: &v {inner}, b: [*v]}}\n").validate_seal()


def test_a_short_chain_of_shared_aliases_is_accepted() -> None:
    manifest = compile_descriptor_text(SMALL + _chain(20))
    assert json.dumps(manifest.task["a20"]) == "[" * 21 + "]" * 21
    assert json.dumps(manifest.task["a0"]) == "[]"
    assert manifest.validate_seal()


def test_shared_aliases_up_to_the_limit_are_accepted() -> None:
    # task (1) + a<i> (2) + i nested lists: the deepest leaf of a(MAX_DEPTH - 2) is at MAX_DEPTH.
    assert compile_descriptor_text(SMALL + _chain(MAX_DEPTH - 2)).validate_seal()
    assert _where(SMALL + _chain(MAX_DEPTH - 1)).endswith(
        f"nested more than {MAX_DEPTH} levels deep"
    )
