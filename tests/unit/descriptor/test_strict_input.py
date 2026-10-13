"""T03r1: only JSON-shaped, strictly typed input seals, and every refusal is a DescriptorError."""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from arci.cli import main
from arci.descriptor import (
    MAX_DEPTH,
    Descriptor,
    DescriptorError,
    compile_descriptor,
    compile_descriptor_text,
    loads_descriptor,
    parse_yaml,
    source_path,
    validation_problems,
)
from arci.schema import Manifest

REPO = Path(__file__).resolve().parents[3]
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

COMMAND = """
experiment_id: cmd
oracle: m.world:oracle
task: {b: 2, a: 1, nested: {z: [3, 2, 1], y: true, x: null}, ratio: 0.25}
baseline: {label: a, command: {argv: ARGV}}
candidate: {label: b, command: {argv: [python, -m, mypackage.agent, --variant, b]}}
mcp_server: {argv: [python, -m, mypackage.env], snapshot: "m.world:snapshot"}
conditions:
  - id: clean
n_per_arm: 6
prior_runs: [run-c, run-a, run-b]
"""


def _error(text: str) -> DescriptorError:
    with pytest.raises(DescriptorError) as caught:
        compile_descriptor_text(text, "arci.yaml")
    assert type(caught.value) is DescriptorError
    assert "\n" not in str(caught.value)
    return caught.value


def _where(text: str) -> str:
    """`path: message` of the reported error."""
    return str(_error(text)).removeprefix("descriptor arci.yaml:")


# --- 1. unordered and non-JSON YAML collections ---------------------------------------------------


def test_argv_as_a_set_is_rejected_before_any_coercion() -> None:
    text = COMMAND.replace("ARGV", '!!set {python: null, "-m": null, mypackage.agent: null}')
    assert _where(text) == (
        "baseline.command.argv: not a JSON value: YAML tag !!set is not allowed; use a mapping, "
        "a list, a number, true/false, null or a quoted string"
    )


@pytest.mark.parametrize(
    ("value", "tag"),
    [
        ("!!set {run-a: null, run-b: null}", "!!set"),
        ("!!omap [{a: 1}, {b: 2}]", "!!omap"),
        ("!!pairs [{a: 1}, {a: 2}]", "!!pairs"),
        ("!!binary aGVsbG8=", "!!binary"),
        ("!!timestamp 2026-10-13", "!!timestamp"),
        ("!custom x", "!custom"),
        ("!!python/name:os.system x", "!!python/name:os.system"),
        ("!!str [a]", "!!str"),
        ("!!map [a]", "!!map"),
    ],
)
def test_every_tag_but_plain_json_is_rejected_with_its_path(value: str, tag: str) -> None:
    message = _where(SMALL + f"prior_runs: {value}\n")
    assert message.startswith(f"prior_runs: not a JSON value: YAML tag {tag} is not allowed")


def test_a_non_json_tag_deep_in_task_names_its_true_path() -> None:
    # Astra's case: a task key spelled like a pydantic union tag is still a key.
    text = SMALL + "task: {foo: {dict: {}, list: [1, {bad: !!timestamp 2026-10-13}]}}\n"
    assert _where(text).startswith("task.foo.list[1].bad: not a JSON value: YAML tag !!timestamp")


def test_the_same_text_seals_identically_under_three_hash_seeds() -> None:
    text = COMMAND.replace("ARGV", "[python, -m, mypackage.agent, --variant, a]")
    script = (
        "import sys\n"
        "from arci.descriptor import compile_descriptor_text\n"
        "m = compile_descriptor_text(sys.stdin.read())\n"
        "print(m.record_sha256, ' '.join(m.baseline.command.argv), ' '.join(m.prior_runs))\n"
    )
    outputs: set[str] = set()
    for seed in ("1", "2", "3"):
        done = subprocess.run(
            [sys.executable, "-c", script],
            input=text,
            capture_output=True,
            text=True,
            cwd=REPO,
            env={**os.environ, "PYTHONHASHSEED": seed},
            check=True,
        )
        outputs.add(done.stdout)
    (line,) = outputs
    seal, rest = line.split(" ", 1)
    assert seal == compile_descriptor_text(text).record_sha256
    assert rest == "python -m mypackage.agent --variant a run-c run-a run-b\n"


# --- 2. malformed or unsealable values ---------------------------------------------------------


@pytest.mark.parametrize("value", [".nan", ".NaN", ".inf", "-.inf", "+.inf", "!!float inf"])
@pytest.mark.parametrize(
    ("template", "path"),
    [
        ("task: {x: {y: [1, VALUE]}}\n", "task.x.y[1]"),
        ("alpha: VALUE\n", "alpha"),
    ],
)
def test_non_finite_numbers_are_rejected_at_their_path(
    value: str, template: str, path: str
) -> None:
    message = _where(SMALL + template.replace("VALUE", value))
    assert message.startswith(f"{path}: not a finite number: ")
    assert message.endswith("; JSON has no NaN or infinity")


def test_a_non_finite_fault_param_is_rejected_at_its_path() -> None:
    text = SMALL.replace("occurrence: 0}", "occurrence: 0, params: {p: .nan}}")
    assert _where(text).startswith("conditions[0].fault.params.p: not a finite number: .nan")


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ('!!bool "WHAT"', 'invalid boolean "WHAT"; write true or false'),
        ("!!bool yes", 'invalid boolean "yes"; write true or false'),
        ('!!float "abc"', 'invalid number "abc"'),
        ("!!int 1.5", 'invalid integer "1.5"'),
    ],
)
def test_explicit_scalar_tags_that_cannot_construct_name_their_path(
    value: str, message: str
) -> None:
    assert _where(SMALL + f"task: {{x: {value}}}\n") == f"task.x: {message}"


@pytest.mark.parametrize(
    ("task", "expected"),
    [
        ("{1: a}", "task: key 1 is not a string; quote it"),
        ("{null: a}", "task: key null is not a string; quote it"),
        ("{true: a}", "task: key true is not a string; quote it"),
        ("{1.5: a}", "task: key 1.5 is not a string; quote it"),
        ("{? [a]\n  : b}", "task: key a collection is not a string; quote it"),
    ],
)
def test_keys_must_be_strings(task: str, expected: str) -> None:
    assert _where(SMALL + f"task: {task}\n") == expected


def test_quoted_keys_are_strings() -> None:
    assert compile_descriptor_text(SMALL + 'task: {"1": a, "null": b}\n').task == {
        "1": "a",
        "null": "b",
    }


def test_a_self_referencing_alias_is_rejected() -> None:
    assert _where(SMALL + "task: &t {x: [*t]}\n") == (
        "task.x[0]: a YAML alias contains itself; recursive values are not JSON"
    )


def test_a_shared_alias_is_fine() -> None:
    text = SMALL + "task: {a: &v [1, 2], b: *v}\n"
    assert compile_descriptor_text(text).task == {"a": [1, 2], "b": [1, 2]}


def test_nesting_is_bounded_with_a_path() -> None:
    deep = "task: {a: " + "[" * MAX_DEPTH + "]" * MAX_DEPTH + "}\n"
    path = "task.a" + "[0]" * (MAX_DEPTH - 1)
    assert _where(SMALL + deep) == f"{path}: nested more than {MAX_DEPTH} levels deep"
    abyss = "task: " + "[" * 5000 + "]" * 5000 + "\n"
    assert str(_error(SMALL + abyss)) == (
        f"descriptor arci.yaml: nested more than {MAX_DEPTH} levels deep"
    )


def test_deep_but_bounded_task_nesting_seals() -> None:
    value = "[" * (MAX_DEPTH - 2) + "1" + "]" * (MAX_DEPTH - 2)
    manifest = compile_descriptor_text(SMALL + f"task: {{a: {value}}}\n")
    assert manifest.validate_seal()


def test_a_seal_failure_is_a_descriptor_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(**_data: object) -> Manifest:
        raise ValueError("Out of range float values are not JSON compliant")

    monkeypatch.setattr(Manifest, "create", refuse)
    error = _error(SMALL)
    assert str(error) == (
        "descriptor arci.yaml: cannot seal the manifest: "
        "Out of range float values are not JSON compliant"
    )


@pytest.mark.parametrize(
    "extra",
    [
        "task: {x: .nan}\n",
        'task: {x: !!bool "WHAT"}\n',
        "prior_runs: !!set {a: null}\n",
        "task: {1: a}\n",
        "base_seed: true\n",
    ],
)
def test_the_cli_reports_file_and_path_with_exit_three(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    extra: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("arci.yaml").write_text(SMALL + extra, encoding="utf-8")
    assert main(["run", "arci.yaml", "--out", "runs"]) == 3
    err = capsys.readouterr().err
    assert err.startswith("error: CliError: descriptor arci.yaml:")
    assert err.count("\n") == 1
    with pytest.raises(DescriptorError):
        compile_descriptor(Path("arci.yaml"))


# --- 3. structural path mapping ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("arm", "expected"),
    [
        (
            '{"arm mapping": {}, label: a, agent: "m.a:f"}',
            'baseline["arm mapping"]: unknown key "arm mapping"',
        ),
        (
            '{"module:function": {}, label: 5, agent: "m.a:f"}',
            "baseline.label: Input should be a valid string, got 5",
        ),
        (
            '{"module:function": 1, label: a, agent: "m.a:f"}',
            'baseline["module:function"]: unknown key "module:function"',
        ),
        ('{label: a, agent: "m.a:f", command: {argv: [x], dict: 1}}', "baseline.command.dict: "),
        ("pkg/run", 'baseline: invalid reference "pkg/run"; expected module:function'),
        ("5", "baseline: must be a mapping"),
    ],
)
def test_arm_union_tags_are_never_mistaken_for_keys(arm: str, expected: str) -> None:
    assert _where(SMALL.replace(f"baseline: {MOD}:good_agent", f"baseline: {arm}")).startswith(
        expected
    )


def test_every_error_under_a_tag_named_key_has_its_true_path() -> None:
    data = parse_yaml(
        SMALL.replace(
            f"baseline: {MOD}:good_agent",
            'baseline: {"arm mapping": {label: 1}, label: 5, agent: "m.a:f"}',
        )
    )
    assert isinstance(data, dict)
    with pytest.raises(ValidationError) as caught:
        Descriptor.model_validate_json(json.dumps(data), strict=True)
    assert sorted(path for path, _ in validation_problems(caught.value, data)) == [
        ("baseline", "arm mapping"),
        ("baseline", "label"),
    ]


def _python_mode_problem(task: dict[str, object]) -> tuple[tuple[str | int, ...], str]:
    base = parse_yaml(SMALL)
    assert isinstance(base, dict)
    data: dict[str, object] = {**cast(dict[str, object], base), "task": task}
    with pytest.raises(ValidationError) as caught:
        Descriptor.model_validate(data)
    (problem,) = validation_problems(caught.value, data)
    return problem


@pytest.mark.parametrize(
    ("task", "path"),
    [
        ({"foo": {"dict": {}, "bad": datetime.date(2026, 10, 13)}}, ("task", "foo", "bad")),
        ({"dict": {"list": [1, datetime.date(2026, 10, 13)]}}, ("task", "dict", "list", 1)),
        ({"list": [{"dict": [datetime.date(2026, 10, 13)]}]}, ("task", "list", 0, "dict", 0)),
        (
            {"module:function": {"arm mapping": datetime.date(2026, 10, 13)}},
            ("task", "module:function", "arm mapping"),
        ),
    ],
)
def test_json_value_tags_are_skipped_structurally(
    task: dict[str, object], path: tuple[str | int, ...]
) -> None:
    # Python-mode validation (the loader never lets a date through) still maps every tag away.
    assert _python_mode_problem(task)[0] == path


def test_source_path_keeps_a_missing_key_and_drops_unknown_segments() -> None:
    data = {"conditions": [{"fault": {}}]}
    loc = ("conditions", 0, "fault", "name")
    assert source_path(loc, data, keep_last=True) == loc
    assert source_path(("task", "x", "[key]"), {"task": {"x": 1}}) == ("task", "x")


# --- 4. alias conflicts join field errors: first by sorted source path -------------------------

TOP_CONFLICT = "contract: {oracle: 'a:b'}\n"


@pytest.mark.parametrize("conflict_first", [True, False])
def test_an_alias_conflict_sorting_first_wins_over_a_later_unknown_key(
    conflict_first: bool,
) -> None:
    parts = [TOP_CONFLICT, "zzz: 1\n"]
    text = SMALL + "".join(parts if conflict_first else parts[::-1])
    assert _where(text) == 'oracle: "oracle" and "contract" both given; give one, not both'


@pytest.mark.parametrize("conflict_first", [True, False])
def test_an_unknown_key_sorting_first_wins_over_an_alias_conflict(conflict_first: bool) -> None:
    parts = [TOP_CONFLICT, "aaa: 1\n"]
    text = SMALL + "".join(parts if conflict_first else parts[::-1])
    assert _where(text) == 'aaa: unknown key "aaa"'


@pytest.mark.parametrize("conflict_first", [True, False])
def test_nested_alias_conflicts_join_field_errors(conflict_first: bool) -> None:
    conflict = "    condition_id: other\n"
    unknown = "    zz: 1\n"
    block = conflict + unknown if conflict_first else unknown + conflict
    text = SMALL.replace("  - id: fetch_timeout\n", "  - id: fetch_timeout\n" + block)
    assert (
        _where(text)
        == 'conditions[0].id: "id" and "condition_id" are the same key; give one, not both'
    )
    text = text.replace("zz: 1", "a: 1")
    assert _where(text) == 'conditions[0].a: unknown key "a"'


@pytest.mark.parametrize("unknown", ["prior_runs: [true]\n", "zzz: 1\n"])
def test_fault_alias_conflicts_join_field_errors(unknown: str) -> None:
    text = SMALL.replace("occurrence: 0}", "occurrence: 0, at_occurrence: 1}") + unknown
    assert _where(text) == (
        'conditions[0].fault.occurrence: "occurrence" and "at_occurrence" are the same key; '
        "give one, not both"
    )
    faults = text.replace(
        "    fault: {name: tool_timeout, tool: fetch, occurrence: 0, at_occurrence: 1}",
        "    faults: [{name: tool_timeout}, {name: empty_result, occurrence: 0, at_occurrence: 0}]",
    )
    assert _where(faults).startswith('conditions[0].faults[1].occurrence: "occurrence" and')


def test_fault_and_faults_conflict_joins_field_errors() -> None:
    text = SMALL.replace("occurrence: 0}", "occurrence: 0}\n    faults: []") + "zzz: 1\n"
    assert (
        _where(text) == 'conditions[0].fault: "fault" and "faults" both given; give one, not both'
    )


def test_a_missing_oracle_joins_field_errors() -> None:
    text = SMALL.replace(f"oracle: {MOD}:oracle\n", "") + "zzz: 1\n"
    assert _where(text) == 'oracle: missing required key "oracle" (or "contract")'


# --- 5. strict numbers --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (
            ("n_per_arm: 6", "n_per_arm: true"),
            "n_per_arm: Input should be a valid integer, got true",
        ),
        (("n_per_arm: 6", 'n_per_arm: "6"'), 'n_per_arm: Input should be a valid integer, got "6"'),
        (("n_per_arm: 6", "n_per_arm: 6.0"), "n_per_arm: Input should be a valid integer, got 6.0"),
        (
            ("n_per_arm: 6", "n_per_arm: 6\nbase_seed: '7'"),
            'base_seed: Input should be a valid integer, got "7"',
        ),
        (
            ("n_per_arm: 6", "n_per_arm: 6\nalpha: '0.05'"),
            'alpha: Input should be a valid number, got "0.05"',
        ),
        (
            ("n_per_arm: 6", "n_per_arm: 6\ndelta: false"),
            "delta: Input should be a valid number, got false",
        ),
        (
            ("n_per_arm: 6", "n_per_arm: 6\nlooks: [3, true]"),
            "looks[1]: Input should be a valid integer, got true",
        ),
        (
            ("occurrence: 0", "occurrence: true"),
            "conditions[0].fault.occurrence: Input should be a valid integer, got true",
        ),
        (
            ("n_per_arm: 6", "n_per_arm: 6\nbudgets: {max_tool_calls: true}"),
            "budgets.max_tool_calls: Input should be a valid integer, got true",
        ),
        (
            ("n_per_arm: 6", "n_per_arm: 6\nbudgets: {max_seconds: '15'}"),
            'budgets.max_seconds: Input should be a valid number, got "15"',
        ),
    ],
)
def test_booleans_and_strings_never_become_numbers(change: tuple[str, str], expected: str) -> None:
    assert _where(SMALL.replace(*change)) == expected


def test_yaml_numbers_still_work_where_numbers_belong() -> None:
    text = (
        SMALL
        + "alpha: 5.0e-2\ndelta: .1\nbase_seed: -3\n"
        + "budgets: {max_seconds: 1.0e+3, grader_seconds: 15}\n"
    )
    manifest = compile_descriptor_text(text)
    assert (manifest.alpha, manifest.delta, manifest.base_seed) == (0.05, 0.1, -3)
    assert (manifest.budgets.max_seconds, manifest.budgets.grader_seconds) == (1000.0, 15.0)


# --- 6. the float rule --------------------------------------------------------------------------


def test_the_float_rule() -> None:
    parsed = parse_yaml(
        "a: 1.5\nb: -0.25\nc: +1.5\nd: 2.\ne: .5\nf: 1.0e+3\ng: 1.0e-3\nh: 1:30.5\ni: 1_000.5\n"
        "j: 1.0e3\nk: 1e3\nl: -.5\nm: 190:20:30.15\nn: '1.5'\n"
    )
    assert parsed == {
        "a": 1.5,
        "b": -0.25,
        "c": 1.5,
        "d": 2.0,
        "e": 0.5,
        "f": 1000.0,
        "g": 0.001,
        "h": "1:30.5",
        "i": "1_000.5",
        "j": "1.0e3",
        "k": "1e3",
        "l": "-.5",
        "m": "190:20:30.15",
        "n": "1.5",
    }


def test_loads_descriptor_is_the_same_gate() -> None:
    with pytest.raises(DescriptorError) as caught:
        loads_descriptor("prior_runs: !!set {a: null}\n", "x.yaml")
    assert (caught.value.source, caught.value.path) == ("x.yaml", ("prior_runs",))
