"""Suite schema: rationals, construction rules, records and seals. FROZEN.

Every test names the section of plan/exec/v2/tasks/P1-CONTRACT.md it pins.
"""

from __future__ import annotations

import subprocess
import sys
from fractions import Fraction

import pytest
from pydantic import TypeAdapter, ValidationError

from arci.schema import (
    EXIT_CODES,
    ArmSpec,
    Bucket,
    Budgets,
    CommandSpec,
    Condition,
    FaultSpec,
    McpServerSpec,
    Model,
    Sealed,
    Verdict,
)
from arci.suite_schema import (
    SUITE_MAX_PAIRS,
    SUITE_SCHEMA_VERSION,
    SUITE_SEED_DERIVATION,
    Rational,
    SuiteCellStats,
    SuiteCounts,
    SuiteDecision,
    SuiteId,
    SuiteManifest,
    SuiteRoundDecision,
    SuiteTask,
    format_rational,
    parse_rational,
)
from tests.acceptance.helpers import DEAD, MOD, TIMEOUT, contract
from tests.acceptance.suite_helpers import CONDITIONS, suite_manifest, tasks

pytestmark = pytest.mark.acceptance

PY_A = ArmSpec(label="A", agent=f"{MOD}:good_agent", candidate_id="a")
PY_B = ArmSpec(label="B", agent=f"{MOD}:fragile_agent", candidate_id="b")
CMD_A = ArmSpec(label="A", command=CommandSpec(argv=("agent-a", "{task_file}")), candidate_id="a")
CMD_B = ArmSpec(label="B", command=CommandSpec(argv=("agent-b", "{task_file}")), candidate_id="b")
SERVER = McpServerSpec(argv=("env-server", "{workdir}"), snapshot=f"{MOD}:snapshot")
TOOLSET = f"{MOD}:make_world"


WRONG_DIGEST = "0" * 64  # well formed (contract 8 item 2) but not the rule digest


def _fields(**overrides: object) -> dict[str, object]:
    """Fields of a structurally valid manifest: python arms, 20 cells, 20 rounds, 4 errored.

    `experiment_id` is a fixed, well-formed id (contract 8 item 2 fixes its shape) that is not
    the rule digest: construction checks structure only (contract section 2), so the schema
    does not compare it with the rule digest. The test-only keys `n_tasks` (default 5) and
    `n_conditions` (default 4) size the grid and are not manifest fields.
    """
    n_tasks = overrides.pop("n_tasks", 5)
    n_conditions = overrides.pop("n_conditions", 4)
    assert isinstance(n_tasks, int)
    assert isinstance(n_conditions, int)
    fields: dict[str, object] = {
        "experiment_id": f"suite-acceptance@{WRONG_DIGEST}",
        "suite_id": "suite-acceptance",
        "tasks": tasks(n_tasks),
        "conditions": CONDITIONS[:n_conditions],
        "toolset": TOOLSET,
        "contract": contract(),
        "baseline": PY_A,
        "candidate": PY_B,
        "max_rounds": 20,
        "max_errored_pairs": 4,
    }
    fields.update(overrides)
    return fields


def _build(**overrides: object) -> SuiteManifest:
    return SuiteManifest.create(**_fields(**overrides))


def _decision(**overrides: object) -> SuiteDecision:
    """A minimal SuiteDecision: the fixed ERROR template of contract section 5."""
    fields: dict[str, object] = {
        "experiment_id": "",
        "manifest_sha256": "",
        "trials_sha256": "",
        "alpha": "",
        "delta": "",
        "stakes": (),
        "threshold": "",
        "n_cells": 0,
        "max_rounds": 0,
        "scenario_seeds": "",
        "max_errored_pairs": 0,
        "verdict": Verdict.ERROR,
        "exit_code": EXIT_CODES[Verdict.ERROR],
        "reasons": ("gate computation failed",),
    }
    fields.update(overrides)
    return SuiteDecision.create(**fields)


def _counts(minus: int = 0, zero: int = 0, plus: int = 0, errored: int = 0) -> SuiteCounts:
    return SuiteCounts(minus=minus, zero=zero, plus=plus, errored=errored)


def _round_decision(**overrides: object) -> SuiteRoundDecision:
    fields: dict[str, object] = {
        "round": 1,
        "pairs": 20,
        "trials_sha256": "a" * 64,
        "counts": _counts(zero=19, errored=1),
        "candidate_hard_violations": 0,
        "pass_wealth": "1.00000e+00",
        "block_wealth": "1.00000e+00",
        "pass_crossed": False,
        "block_crossed": False,
        "verdict": Verdict.INCONCLUSIVE,
        "reasons": ("no test crossed",),
    }
    fields.update(overrides)
    return SuiteRoundDecision(**fields)  # pyright: ignore[reportArgumentType]


def _cell_stats(**overrides: object) -> SuiteCellStats:
    fields: dict[str, object] = {
        "task_id": "t0",
        "condition_id": "clean",
        "pairs": 1,
        "baseline_successes": 1,
        "candidate_successes": 1,
        "counts": _counts(zero=1),
        "candidate_hard_violations": 0,
    }
    fields.update(overrides)
    return SuiteCellStats(**fields)  # pyright: ignore[reportArgumentType]


# --- constants and type aliases ------------------------------------------------------------


def test_module_constants() -> None:
    """Contract 2, module constants."""
    assert SUITE_SCHEMA_VERSION == "arci-suite/1"
    assert SUITE_SEED_DERIVATION == "sha256-v1"
    assert SUITE_MAX_PAIRS == 100_000


@pytest.mark.parametrize("text", ["a", "Z", "0", "a0_.-", "suite-1.2_x", "a" * 64, "9" * 64])
def test_suite_id_accepts(text: str) -> None:
    """Contract 2, SuiteId pattern ^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$."""
    assert TypeAdapter(SuiteId).validate_python(text) == text


@pytest.mark.parametrize("text", ["", "_a", ".a", "-a", "a b", "a:b", "a/b", "a" * 65, "caf\xe9"])
def test_suite_id_rejects(text: str) -> None:
    """Contract 2, SuiteId pattern ^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$."""
    with pytest.raises(ValidationError):
        TypeAdapter(SuiteId).validate_python(text)


@pytest.mark.parametrize(
    "text",
    [
        "1/20",
        "40/1",
        "1/1",
        "2/40",
        "10/100",
        "123/4567",
        # Contract 8 item 1: at most 7 digits each side, so 7 digits is the largest accepted.
        "1234567/7654321",
        "9999999/9999998",
        "9999999/1",
        "1/9999999",
        "2000000/1",
    ],
)
def test_rational_pattern_accepts(text: str) -> None:
    """Contract 8 item 1, Rational pattern ^[1-9][0-9]{0,6}/[1-9][0-9]{0,6}$ (format only,
    not lowest terms)."""
    assert TypeAdapter(Rational).validate_python(text) == text


@pytest.mark.parametrize(
    "text",
    [
        "",
        "1",
        "0/1",
        "1/0",
        "01/2",
        "1/02",
        "-1/2",
        "+1/2",
        "1.5/2",
        "1/2/3",
        " 1/2",
        "1/2 ",
        # Contract 8 item 1: 8 digits on either side is too long.
        "12345678/1",
        "1/12345678",
        "12345678/12345678",
        "10000000/1",
        "1/10000000",
        "123456789/1000000007",
    ],
)
def test_rational_pattern_rejects(text: str) -> None:
    """Contract 8 item 1, Rational pattern ^[1-9][0-9]{0,6}/[1-9][0-9]{0,6}$."""
    with pytest.raises(ValidationError):
        TypeAdapter(Rational).validate_python(text)


# --- parse_rational / format_rational ------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("1/20", Fraction(1, 20)),
        ("1/10", Fraction(1, 10)),
        ("40/1", Fraction(40)),
        ("1/1", Fraction(1)),
        ("3/7", Fraction(3, 7)),
        ("1/1000000", Fraction(1, 1_000_000)),
        # Contract 8 item 1: 7 digits each side is still accepted.
        ("9999999/9999998", Fraction(9_999_999, 9_999_998)),
        ("1/9999999", Fraction(1, 9_999_999)),
        ("9999999/1", Fraction(9_999_999)),
        ("2000000/1", Fraction(2_000_000)),
    ],
)
def test_parse_rational_reads_lowest_terms(text: str, value: Fraction) -> None:
    """Contract 2, parse_rational: "n/d" in lowest terms gives that Fraction."""
    parsed = parse_rational(text)
    assert isinstance(parsed, Fraction)
    assert parsed == value


@pytest.mark.parametrize(
    "text",
    [
        "2/40",
        "4/2",
        "6/4",
        "10/100",
        "2/2",
        "",
        "abc",
        "1",
        "1/",
        "/2",
        "1/2/3",
        # Contract 8 item 1: parse_rational rejects anything longer than 7 digits a side,
        # whether or not it is in lowest terms.
        "10000000/1",
        "1/10000000",
        "9999999/10000000",
        "10000000/9999999",
        "123456789/1000000007",
        "12345678/12345679",
    ],
)
def test_parse_rational_rejects(text: str) -> None:
    """Contract 2 and 8 item 1, parse_rational: ValueError unless "n/d" in lowest terms with
    at most 7 digits on each side."""
    with pytest.raises(ValueError):
        parse_rational(text)


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (Fraction(1, 20), "1/20"),
        (Fraction(2, 40), "1/20"),
        (Fraction(40), "40/1"),
        (Fraction(1), "1/1"),
        (Fraction(7, 3), "7/3"),
        (2 / Fraction(1, 20), "40/1"),
        (2 / Fraction(1, 1_000_000), "2000000/1"),
    ],
)
def test_format_rational_writes_lowest_terms(value: Fraction, text: str) -> None:
    """Contract 2, format_rational: "n/d", lowest terms (and 2 / alpha example "40/1")."""
    assert format_rational(value) == text
    assert parse_rational(format_rational(value)) == value


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (2 / Fraction(1, 1_000_000), "2000000/1"),  # the largest threshold: alpha >= 1/1000000
        (Fraction(1, 10**8), "1/100000000"),
        (Fraction(10**9 + 1), "1000000001/1"),
    ],
)
def test_format_rational_is_unchanged_by_the_digit_bound(value: Fraction, text: str) -> None:
    """Contract 8 item 1: format_rational is unchanged, so it still writes "n/d" in lowest
    terms for values whose numerator or denominator has more than 7 digits (contract 2),
    even though parse_rational and the Rational type now reject that text."""
    assert format_rational(value) == text


@pytest.mark.parametrize("value", [Fraction(0), Fraction(-1, 2), Fraction(-40)])
def test_format_rational_rejects_non_positive(value: Fraction) -> None:
    """Contract 2, format_rational: ValueError unless > 0."""
    with pytest.raises(ValueError):
        format_rational(value)


# --- a passing manifest and its defaults -----------------------------------------------------


def test_passing_manifest_and_defaults() -> None:
    """Contract 2, SuiteManifest fields and defaults."""
    m = _build()
    assert isinstance(m, SuiteManifest)
    assert m.validate_seal()
    assert m.schema_version == "arci-suite/1"
    assert m.created_at == ""
    assert m.mcp_server is None
    assert m.alpha == "1/20"
    assert m.delta == "1/10"
    assert m.stakes == ("1/4", "1/2")
    assert m.scenario_seeds == "fixed"
    assert m.seed_derivation == "sha256-v1"
    assert m.acknowledge_single_round is False
    assert m.budgets == Budgets()
    assert m.fixtures_sha256 == ""
    assert m.prior_runs == ()
    assert SuiteTask(task_id="t").task == {}


def test_manifest_from_shared_helper_constructs() -> None:
    """Contract 2, a passing manifest (built through the shared helper)."""
    m = suite_manifest()
    assert isinstance(m, SuiteManifest)
    assert m.validate_seal()


def test_manifest_field_set() -> None:
    """Contract 2, SuiteManifest has exactly the stated fields (no `decisions`, no v1 knobs)."""
    assert set(SuiteManifest.model_fields) == {
        "record_sha256",
        "schema_version",
        "experiment_id",
        "created_at",
        "suite_id",
        "tasks",
        "conditions",
        "toolset",
        "mcp_server",
        "contract",
        "baseline",
        "candidate",
        "alpha",
        "delta",
        "stakes",
        "max_rounds",
        "scenario_seeds",
        "max_errored_pairs",
        "seed_derivation",
        "acknowledge_single_round",
        "budgets",
        "fixtures_sha256",
        "prior_runs",
    }
    assert set(SuiteTask.model_fields) == {"task_id", "task"}


def test_records_use_v1_base_classes() -> None:
    """Contract 2, base classes: v1 Model for records, v1 Sealed for manifest and decision."""
    assert issubclass(SuiteTask, Model)
    assert issubclass(SuiteManifest, Sealed)
    assert issubclass(SuiteCounts, Model)
    assert issubclass(SuiteRoundDecision, Model)
    assert issubclass(SuiteCellStats, Model)
    assert issubclass(SuiteDecision, Sealed)


@pytest.mark.parametrize(
    "missing",
    [
        "max_rounds",
        "max_errored_pairs",
        "experiment_id",
        "suite_id",
        "tasks",
        "conditions",
        "contract",
        "baseline",
        "candidate",
    ],
)
def test_explicit_numbers_have_no_default(missing: str) -> None:
    """Contract 2, SuiteManifest fields with no stated default (max_rounds and max_errored_pairs
    explicitly, plus experiment_id, suite_id, tasks, conditions, contract, baseline, candidate)
    are required."""
    fields = _fields()
    del fields[missing]
    with pytest.raises(ValidationError):
        SuiteManifest.create(**fields)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"tasks": ()}, id="no-tasks"),
        pytest.param({"conditions": ()}, id="no-conditions"),
    ],
)
def test_tasks_and_conditions_are_non_empty(overrides: dict[str, object]) -> None:
    """Contract 2, SuiteManifest: tasks at least 1, conditions at least 1."""
    with pytest.raises(ValidationError):
        _build(**overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({}, id="defaults"),
        pytest.param({"tasks": tuple(reversed(tasks(5)))}, id="tasks-unsorted"),
        pytest.param({"conditions": tuple(reversed(CONDITIONS))}, id="conditions-unsorted"),
        pytest.param({"suite_id": "a" * 64}, id="suite-id-64-chars"),
        pytest.param({"scenario_seeds": "per_round"}, id="per-round"),
        pytest.param({"alpha": "1/1000000"}, id="alpha-lowest-bound"),
        pytest.param({"alpha": "1/2"}, id="alpha-highest-bound"),
        pytest.param({"delta": "1/1000000"}, id="delta-small"),
        pytest.param({"delta": "999999/1000000"}, id="delta-large"),
        # Contract 8 item 1: 7 digits a side is accepted on every Rational manifest field.
        pytest.param({"alpha": "499999/1000000"}, id="alpha-seven-digit-denominator"),
        pytest.param({"delta": "9999998/9999999"}, id="delta-seven-digits-both-sides"),
        pytest.param({"stakes": ("1/9999999", "9999998/9999999")}, id="stakes-seven-digits"),
        pytest.param({"stakes": ("1/2",)}, id="one-stake"),
        pytest.param({"stakes": ("999/1000",)}, id="stake-near-one"),
        pytest.param(
            {"stakes": ("1/9", "1/8", "1/7", "1/6", "1/5", "1/4", "1/3", "1/2")},
            id="eight-stakes",
        ),
        pytest.param({"max_rounds": 5000}, id="pairs-at-cap-20-cells"),
        pytest.param(
            {"n_tasks": 1, "n_conditions": 1, "max_rounds": 100_000}, id="pairs-at-cap-1-cell"
        ),
        pytest.param({"max_errored_pairs": 0}, id="no-errored-pairs"),
        pytest.param({"max_errored_pairs": 400}, id="errored-equals-registered"),
        pytest.param({"max_rounds": 1, "acknowledge_single_round": True}, id="one-round-ack"),
        pytest.param(
            {"toolset": None, "mcp_server": SERVER, "baseline": CMD_A, "candidate": CMD_B},
            id="command-arms",
        ),
    ],
)
def test_structurally_valid_manifests_construct(overrides: dict[str, object]) -> None:
    """Contract 2, construction rules 1 to 7: each boundary case that satisfies them constructs."""
    m = _build(**overrides)
    assert m.validate_seal()


# --- the seven construction rules, one failing case per rule and sub-rule ----------------


def _cond(condition_id: str, *faults: FaultSpec) -> Condition:
    return Condition(condition_id=condition_id, faults=faults)


RULE_FAILURES = [
    # Rule 1: task_id unique; condition_id unique and a SuiteId.
    pytest.param(
        {"tasks": (SuiteTask(task_id="t0"), SuiteTask(task_id="t0", task={"x": 1}))},
        id="r1-duplicate-task-id",
    ),
    pytest.param(
        {"conditions": (_cond("clean"), _cond("clean", TIMEOUT))},
        id="r1-duplicate-condition-id",
    ),
    pytest.param({"conditions": (_cond("a b"),)}, id="r1-condition-id-space"),
    pytest.param({"conditions": (_cond("a:b"),)}, id="r1-condition-id-colon"),
    pytest.param({"conditions": (_cond(""),)}, id="r1-condition-id-empty"),
    pytest.param({"conditions": (_cond("-clean"),)}, id="r1-condition-id-leading-dash"),
    pytest.param({"conditions": (_cond("c" * 65),)}, id="r1-condition-id-65-chars"),
    # Rule 2: no ceiling fault; no decision perturbation; no decision tool.
    pytest.param({"conditions": (*CONDITIONS, _cond("dead_backend", DEAD))}, id="r2-ceiling"),
    pytest.param(
        {
            "conditions": (
                _cond(
                    "low_conf",
                    FaultSpec(
                        name="decision_low_confidence",
                        bucket=Bucket.FALSIFY,
                        params={"confidence_max": 0.2},
                    ),
                ),
            )
        },
        id="r2-decision-low-confidence",
    ),
    pytest.param(
        {
            "conditions": (
                _cond(
                    "unavailable",
                    FaultSpec(name="decision_unavailable", bucket=Bucket.FALSIFY, tool="fetch"),
                ),
            )
        },
        id="r2-decision-unavailable",
    ),
    pytest.param(
        {
            "conditions": (
                _cond(
                    "decision_timeout",
                    FaultSpec(name="tool_timeout", bucket=Bucket.FALSIFY, tool="decision:models"),
                ),
            )
        },
        id="r2-decision-tool-prefix",
    ),
    # Rule 3: both python with toolset and no mcp_server, or both command with the reverse.
    pytest.param({"toolset": None}, id="r3-python-without-toolset"),
    pytest.param({"mcp_server": SERVER}, id="r3-python-with-mcp-server"),
    pytest.param(
        {"toolset": None, "mcp_server": None, "baseline": CMD_A, "candidate": CMD_B},
        id="r3-command-without-mcp-server",
    ),
    pytest.param(
        {"mcp_server": SERVER, "baseline": CMD_A, "candidate": CMD_B},
        id="r3-command-with-toolset",
    ),
    pytest.param({"candidate": CMD_B}, id="r3-mixed-python-command-toolset"),
    pytest.param(
        {"toolset": None, "mcp_server": SERVER, "baseline": CMD_A},
        id="r3-mixed-command-python-mcp",
    ),
    # Rule 4: lowest terms; alpha range; delta range; stakes count, range, order.
    pytest.param({"alpha": "2/40"}, id="r4-alpha-not-lowest"),
    pytest.param({"delta": "2/20"}, id="r4-delta-not-lowest"),
    pytest.param({"stakes": ("2/8", "1/2")}, id="r4-stake-not-lowest"),
    pytest.param({"alpha": "1/1000001"}, id="r4-alpha-too-small"),
    pytest.param({"alpha": "501/1000"}, id="r4-alpha-too-large"),
    pytest.param({"alpha": "1/1"}, id="r4-alpha-one"),
    pytest.param({"alpha": "0.05"}, id="alpha-not-rational-pattern"),
    pytest.param({"delta": "1/1"}, id="r4-delta-one"),
    pytest.param({"delta": "3/2"}, id="r4-delta-above-one"),
    pytest.param({"stakes": ()}, id="r4-no-stakes"),
    pytest.param(
        {"stakes": ("1/10", "1/9", "1/8", "1/7", "1/6", "1/5", "1/4", "1/3", "1/2")},
        id="r4-nine-stakes",
    ),
    pytest.param({"stakes": ("1/4", "1/1")}, id="r4-stake-one"),
    pytest.param({"stakes": ("1/4", "3/2")}, id="r4-stake-above-one"),
    pytest.param({"stakes": ("1/2", "1/4")}, id="r4-stakes-decreasing"),
    pytest.param({"stakes": ("1/4", "1/4")}, id="r4-stakes-repeated"),
    # Contract 8 item 1: 8 digits a side is too long. Each value below satisfies rule 4
    # (lowest terms, in range, increasing), so the length bound is the only reason to refuse.
    pytest.param({"alpha": "4999999/10000000"}, id="item1-alpha-eight-digit-denominator"),
    pytest.param({"delta": "9999999/10000000"}, id="item1-delta-eight-digit-denominator"),
    pytest.param({"delta": "10000001/20000003"}, id="item1-delta-eight-digits-both-sides"),
    pytest.param({"stakes": ("1/10000000",)}, id="item1-stake-eight-digit-denominator"),
    pytest.param({"stakes": ("1/4", "10000001/20000000")}, id="item1-second-stake-too-long"),
    # Rule 5: max_rounds >= 1 and n_cells * max_rounds <= SUITE_MAX_PAIRS.
    pytest.param({"max_rounds": 0, "max_errored_pairs": 0}, id="r5-zero-rounds"),
    # Not isolated: a negative max_rounds also fails rule 6 (0 <= 0 <= -20 is false). Only
    # r5-zero-rounds pins the lower bound of rule 5 on its own.
    pytest.param({"max_rounds": -1, "max_errored_pairs": 0}, id="r5-r6-negative-rounds"),
    pytest.param({"max_rounds": 5001}, id="r5-over-cap-20-cells"),
    pytest.param({"n_tasks": 1, "n_conditions": 1, "max_rounds": 100_001}, id="r5-over-cap-1-cell"),
    # Rule 6: 0 <= max_errored_pairs <= n_cells * max_rounds.
    pytest.param({"max_errored_pairs": -1}, id="r6-negative"),
    pytest.param({"max_errored_pairs": 401}, id="r6-above-registered"),
    # Rule 7: acknowledge_single_round iff max_rounds == 1.
    pytest.param({"max_rounds": 1}, id="r7-one-round-unacknowledged"),
    pytest.param({"max_rounds": 2, "acknowledge_single_round": True}, id="r7-two-rounds-ack"),
    pytest.param({"acknowledge_single_round": True}, id="r7-twenty-rounds-ack"),
]


@pytest.mark.parametrize("overrides", RULE_FAILURES)
def test_construction_rule_violations_raise(overrides: dict[str, object]) -> None:
    """Contract 2, construction rules 1 to 7: each violation raises pydantic.ValidationError."""
    with pytest.raises(ValidationError):
        _build(**overrides)


@pytest.mark.parametrize("bad", ["", "_t", "t 0", "t:0", "t" * 65])
def test_task_id_must_be_suite_id(bad: str) -> None:
    """Contract 2, SuiteTask.task_id is a SuiteId."""
    with pytest.raises(ValidationError):
        SuiteTask(task_id=bad)


@pytest.mark.parametrize("bad", ["", "_suite", "my suite", "s:1", "s" * 65])
def test_suite_id_field_is_suite_id(bad: str) -> None:
    """Contract 2, SuiteManifest.suite_id is a SuiteId."""
    with pytest.raises(ValidationError):
        _build(suite_id=bad)


# --- experiment_id has a fixed shape (contract 8 item 2) -----------------------------------

HEX64 = "0123456789abcdef" * 4
EXPERIMENT_ID_OK = [
    f"a@{'0' * 64}",
    f"0@{HEX64}",
    f"suite-acceptance@{'f' * 64}",
    f"Z9_.-@{'ab' * 32}",
    f"{'a' * 64}@{HEX64}",  # local part at its 64-character limit
]
EXPERIMENT_ID_BAD = [
    pytest.param("", id="empty"),
    pytest.param("suite-acceptance", id="no-digest"),
    pytest.param("suite-acceptance@", id="empty-digest"),
    pytest.param(f"@{'0' * 64}", id="empty-suite-part"),
    pytest.param(f"_suite@{'0' * 64}", id="leading-underscore"),
    pytest.param(f"suite/acceptance@{'0' * 64}", id="forward-slash"),
    pytest.param(f"suite\\acceptance@{'0' * 64}", id="backslash"),
    pytest.param(f"..@{'0' * 64}", id="parent-directory"),
    pytest.param(f"../suite@{'0' * 64}", id="parent-directory-path"),
    pytest.param(f"suite acceptance@{'0' * 64}", id="space"),
    pytest.param(f"suite:acceptance@{'0' * 64}", id="colon"),
    pytest.param(f"{'a' * 65}@{'0' * 64}", id="suite-part-65-chars"),
    pytest.param(f"suite-acceptance@{'0' * 63}", id="63-hex-digits"),
    pytest.param(f"suite-acceptance@{'0' * 65}", id="65-hex-digits"),
    pytest.param(f"suite-acceptance@{'A' * 64}", id="uppercase-hex"),
    pytest.param(f"suite-acceptance@{'0' * 62}AB", id="uppercase-hex-tail"),
    pytest.param(f"suite-acceptance@{'0' * 63}g", id="not-hex"),
    pytest.param(f"suite@acceptance@{'0' * 64}", id="two-at-signs"),
    pytest.param(f"suite-acceptance@{'0' * 64}/..", id="trailing-path"),
    pytest.param(f"{'0' * 64}", id="digest-alone"),
]


@pytest.mark.parametrize("experiment_id", EXPERIMENT_ID_OK)
def test_well_formed_experiment_ids_construct(experiment_id: str) -> None:
    """Contract 8 item 2: experiment_id matches ^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}@[0-9a-f]{64}$,
    whatever digest it holds (the schema never compares it with the rule digest)."""
    m = _build(experiment_id=experiment_id)
    assert m.experiment_id == experiment_id
    assert m.validate_seal()


@pytest.mark.parametrize("experiment_id", EXPERIMENT_ID_BAD)
def test_malformed_experiment_ids_are_a_validation_error(experiment_id: str) -> None:
    """Contract 8 item 2: anything else is a pydantic.ValidationError, so the id is always
    safe as a directory name."""
    with pytest.raises(ValidationError):
        _build(experiment_id=experiment_id)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "arci/0.5"),
        ("schema_version", "arci-suite/2"),
        ("seed_derivation", "sha256-v2"),
        ("scenario_seeds", "random"),
        ("scenario_seeds", "FIXED"),
    ],
)
def test_manifest_literals(field: str, value: str) -> None:
    """Contract 2, Literal fields schema_version, seed_derivation, scenario_seeds."""
    with pytest.raises(ValidationError):
        _build(**{field: value})


# --- n_cells and registered_pairs ----------------------------------------------------------


@pytest.mark.parametrize(
    ("n_tasks", "n_conditions", "max_rounds"),
    [(5, 4, 20), (1, 1, 1), (3, 2, 7), (7, 3, 5), (1, 4, 100), (40, 1, 10)],
)
def test_n_cells_and_registered_pairs(n_tasks: int, n_conditions: int, max_rounds: int) -> None:
    """Contract 2, n_cells = len(tasks) * len(conditions), registered_pairs = it * max_rounds."""
    m = _build(
        n_tasks=n_tasks,
        n_conditions=n_conditions,
        max_rounds=max_rounds,
        max_errored_pairs=0,
        acknowledge_single_round=max_rounds == 1,
    )
    assert m.n_cells == n_tasks * n_conditions
    assert m.registered_pairs == n_tasks * n_conditions * max_rounds


# --- extra fields and frozen records ------------------------------------------------------


@pytest.mark.parametrize(
    "extra",
    [
        {"surprise": 1},
        {"decisions": None},
        {"n_per_arm": 200},
        {"base_seed": 7},
        {"looks": ()},
        {"task_id": "store"},
    ],
)
def test_manifest_rejects_unknown_fields(extra: dict[str, object]) -> None:
    """Contract 2, records forbid extra fields (SuiteManifest has no decisions or v1 knobs)."""
    with pytest.raises(ValidationError):
        _build(**extra)


def test_records_reject_unknown_fields() -> None:
    """Contract 2, records forbid extra fields."""
    with pytest.raises(ValidationError):
        SuiteTask(task_id="t0", surprise=1)  # pyright: ignore[reportCallIssue]
    with pytest.raises(ValidationError):
        SuiteCounts(minus=0, zero=0, plus=0, errored=0, surprise=1)  # pyright: ignore[reportCallIssue]
    with pytest.raises(ValidationError):
        _round_decision(surprise=1)
    with pytest.raises(ValidationError):
        _cell_stats(surprise=1)
    with pytest.raises(ValidationError):
        _decision(surprise=1)


def test_records_are_frozen() -> None:
    """Contract 2, records are frozen (assignment raises, as for v1 Model)."""
    m = _build()
    with pytest.raises(ValidationError):
        m.max_rounds = 3
    task = SuiteTask(task_id="t0")
    with pytest.raises(ValidationError):
        task.task_id = "t1"
    counts = _counts()
    with pytest.raises(ValidationError):
        counts.plus = 1
    rd = _round_decision()
    with pytest.raises(ValidationError):
        rd.verdict = Verdict.PASS
    cell = _cell_stats()
    with pytest.raises(ValidationError):
        cell.pairs = 2
    d = _decision()
    with pytest.raises(ValidationError):
        d.verdict = Verdict.PASS


# --- seals ---------------------------------------------------------------------------------


def _manifest_variants() -> list[SuiteManifest]:
    return [
        suite_manifest(),
        _build(),
        _build(toolset=None, mcp_server=SERVER, baseline=CMD_A, candidate=CMD_B),
        _build(
            created_at="2026-11-11T00:00:00Z",
            scenario_seeds="per_round",
            stakes=("1/8", "1/4", "1/2"),
            tasks=(
                SuiteTask(task_id="b", task={"input": [1, 2.5, None, {"k": "v"}], "flag": True}),
                SuiteTask(task_id="a"),
            ),
            fixtures_sha256="0" * 64,
            prior_runs=("suite-acceptance@" + "1" * 64,),
            budgets=Budgets(max_tool_calls=7, max_seconds=12.5),
        ),
    ]


def test_manifest_seal_survives_json_round_trip() -> None:
    """Contract 2, SuiteManifest(Sealed): model_dump_json, model_validate_json keeps the seal."""
    for m in _manifest_variants():
        assert m.validate_seal()
        back = SuiteManifest.model_validate_json(m.model_dump_json())
        assert back.record_sha256 == m.record_sha256
        assert back.validate_seal()


def test_manifest_seal_is_tamper_evident() -> None:
    """Contract 2, SuiteManifest(Sealed): changed registered content breaks the seal."""
    m = _build()
    assert not m.model_copy(update={"max_rounds": 21}).validate_seal()
    assert not m.model_copy(update={"alpha": "1/40"}).validate_seal()
    assert not m.model_copy(update={"max_errored_pairs": 5}).validate_seal()
    assert not m.model_copy(update={"scenario_seeds": "per_round"}).validate_seal()


def test_created_at_is_volatile() -> None:
    """Contract 2, SuiteManifest.created_at is VOLATILE, like v1."""
    m = _build()
    stamped = m.model_copy(update={"created_at": "2026-11-11T12:00:00Z"})
    assert stamped.validate_seal()
    assert _build(created_at="2030-01-01T00:00:00Z").record_sha256 == m.record_sha256


def test_decision_seal_survives_json_round_trip() -> None:
    """Contract 2, SuiteDecision(Sealed): model_dump_json, model_validate_json keeps the seal."""
    # One cell, one round, one pair with d = 0, no test crossed (contract 5, last table row).
    # The records agree with each other: pairs = round * n_cells, the round digest covers the
    # same trials as the decision digest, and the wealth strings are wealth_text of the exact
    # wealths at the defaults: PASS 25/24, BLOCK 85/88 (contract 4, wealth and wealth_text).
    rd = _round_decision(
        round=1,
        pairs=1,
        trials_sha256="4" * 64,
        counts=_counts(zero=1),
        pass_wealth="1.04166e+00",
        block_wealth="9.65909e-01",
        verdict=Verdict.INCONCLUSIVE,
        reasons=("no test crossed",),
    )
    decision = _decision(
        experiment_id="suite-acceptance@" + "2" * 64,
        manifest_sha256="3" * 64,
        trials_sha256="4" * 64,
        alpha="1/20",
        delta="1/10",
        stakes=("1/4", "1/2"),
        threshold="40/1",
        n_cells=1,
        max_rounds=1,
        scenario_seeds="fixed",
        max_errored_pairs=0,
        history=(rd,),
        stopped_at_round=1,
        cells=(_cell_stats(),),
        verdict=Verdict.INCONCLUSIVE,
        exit_code=EXIT_CODES[Verdict.INCONCLUSIVE],
        reasons=("no test crossed",),
        prior_runs=("suite-acceptance@" + "5" * 64,),
    )
    for d in (decision, _decision()):
        assert d.validate_seal()
        back = SuiteDecision.model_validate_json(d.model_dump_json())
        assert back.record_sha256 == d.record_sha256
        assert back.validate_seal()
    assert not decision.model_copy(update={"verdict": Verdict.BLOCK}).validate_seal()


# --- import boundary -----------------------------------------------------------------------


def test_suite_schema_does_not_import_statistics() -> None:
    """Contract 2, suite_schema imports only stdlib, pydantic, arci.schema and arci.hashing."""
    code = (
        "import sys\n"
        "import arci.schema, arci.hashing\n"
        "before = {m for m in sys.modules if m == 'arci' or m.startswith('arci.')}\n"
        "import arci.suite_schema\n"
        "after = {m for m in sys.modules if m == 'arci' or m.startswith('arci.')}\n"
        "assert 'arci.suite_stats' not in sys.modules, sorted(after)\n"
        "assert after - before == {'arci.suite_schema'}, sorted(after - before)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60, check=False
    )
    assert proc.returncode == 0, proc.stderr


# --- decision records ---------------------------------------------------------------------


def test_decision_record_field_sets() -> None:
    """Contract 2, decision records have exactly the stated fields."""
    assert set(SuiteCounts.model_fields) == {"minus", "zero", "plus", "errored"}
    assert set(SuiteRoundDecision.model_fields) == {
        "round",
        "pairs",
        "trials_sha256",
        "counts",
        "candidate_hard_violations",
        "pass_wealth",
        "block_wealth",
        "pass_crossed",
        "block_crossed",
        "verdict",
        "reasons",
    }
    assert set(SuiteCellStats.model_fields) == {
        "task_id",
        "condition_id",
        "pairs",
        "baseline_successes",
        "candidate_successes",
        "counts",
        "candidate_hard_violations",
    }
    assert set(SuiteDecision.model_fields) == {
        "record_sha256",
        "schema_version",
        "experiment_id",
        "manifest_sha256",
        "trials_sha256",
        "alpha",
        "delta",
        "stakes",
        "threshold",
        "n_cells",
        "max_rounds",
        "scenario_seeds",
        "max_errored_pairs",
        "history",
        "stopped_at_round",
        "cells",
        "verdict",
        "exit_code",
        "reasons",
        "prior_runs",
    }


def test_suite_counts_accept_zero_and_positive() -> None:
    """Contract 2, SuiteCounts: every field ge=0."""
    assert _counts() == SuiteCounts(minus=0, zero=0, plus=0, errored=0)
    c = _counts(minus=1, zero=2, plus=3, errored=4)
    assert (c.minus, c.zero, c.plus, c.errored) == (1, 2, 3, 4)


@pytest.mark.parametrize("field", ["minus", "zero", "plus", "errored"])
def test_suite_counts_reject_negative(field: str) -> None:
    """Contract 2, SuiteCounts: every field ge=0."""
    values = {"minus": 0, "zero": 0, "plus": 0, "errored": 0, field: -1}
    with pytest.raises(ValidationError):
        SuiteCounts(**values)


def test_round_decision_and_cell_stats_construct() -> None:
    """Contract 2, SuiteRoundDecision and SuiteCellStats hold the stated fields."""
    rd = _round_decision()
    assert rd.round == 1
    assert rd.pairs == 20
    assert rd.counts == _counts(zero=19, errored=1)
    assert rd.verdict is Verdict.INCONCLUSIVE
    assert rd.reasons == ("no test crossed",)
    assert rd.pass_crossed is False
    assert rd.block_crossed is False
    cell = _cell_stats()
    assert (cell.task_id, cell.condition_id) == ("t0", "clean")
    assert cell.counts == _counts(zero=1)


def test_minimal_decision_defaults() -> None:
    """Contract 2, SuiteDecision.create with required fields only: defaults and seal."""
    d = _decision()
    assert isinstance(d, SuiteDecision)
    assert d.validate_seal()
    assert d.schema_version == "arci-suite/1"
    assert d.history == ()
    assert d.stopped_at_round == 0
    assert d.cells == ()
    assert d.prior_runs == ()
    assert d.verdict is Verdict.ERROR
    assert d.exit_code == 3


@pytest.mark.parametrize("verdict", list(Verdict))
def test_decision_exit_code_field(verdict: Verdict) -> None:
    """Contract 2, SuiteDecision.exit_code: int, EXIT_CODES[verdict]."""
    d = _decision(verdict=verdict, exit_code=EXIT_CODES[verdict])
    assert d.verdict is verdict
    assert isinstance(d.exit_code, int)
    assert d.exit_code == EXIT_CODES[verdict]
    assert d.validate_seal()


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"schema_version": "arci/0.5"}, id="v1-schema-version"),
        pytest.param({"schema_version": "arci-suite/2"}, id="unknown-schema-version"),
        pytest.param({"verdict": "MAYBE"}, id="unknown-verdict"),
    ],
)
def test_decision_literals(overrides: dict[str, object]) -> None:
    """Contract 2, SuiteDecision.schema_version is Literal["arci-suite/1"]; verdict is a Verdict."""
    with pytest.raises(ValidationError):
        _decision(**overrides)


@pytest.mark.parametrize(
    "missing",
    [
        "experiment_id",
        "manifest_sha256",
        "trials_sha256",
        "alpha",
        "delta",
        "stakes",
        "threshold",
        "n_cells",
        "max_rounds",
        "scenario_seeds",
        "max_errored_pairs",
        "verdict",
        "exit_code",
        "reasons",
    ],
)
def test_decision_required_fields(missing: str) -> None:
    """Contract 2, SuiteDecision fields without a stated default are required."""
    fields: dict[str, object] = {
        "experiment_id": "",
        "manifest_sha256": "",
        "trials_sha256": "",
        "alpha": "",
        "delta": "",
        "stakes": (),
        "threshold": "",
        "n_cells": 0,
        "max_rounds": 0,
        "scenario_seeds": "",
        "max_errored_pairs": 0,
        "verdict": Verdict.ERROR,
        "exit_code": 3,
        "reasons": (),
    }
    del fields[missing]
    with pytest.raises(ValidationError):
        SuiteDecision.create(**fields)
