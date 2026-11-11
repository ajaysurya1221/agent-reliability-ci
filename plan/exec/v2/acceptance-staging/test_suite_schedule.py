"""The suite schedule: cells, rule digest, experiment id, seeds, arm order, ids. FROZEN.

Every expected value here is recomputed from `plan/exec/v2/tasks/P1-CONTRACT.md` sections 1
and 3 with `hashlib`, `arci.hashing.hash_record` and `arci.schema.digest_payload`, never
taken from the code under test. Golden vectors were computed from the contract's formulas
with `hashlib` and cross-checked with `openssl dgst -sha256`.
"""

from __future__ import annotations

import ast
import re
import sys
from fractions import Fraction
from functools import cache
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

import arci.suite_schedule as suite_schedule_module
from arci.hashing import hash_record
from arci.schedule import spec_sha256
from arci.schema import (
    ArmSpec,
    Bucket,
    Budgets,
    CommandSpec,
    Condition,
    FaultSpec,
    McpServerSpec,
    TrialSpec,
    digest_payload,
)
from arci.suite_schedule import (
    arm_order,
    build_suite_round,
    build_suite_schedule,
    cell_seed,
    create_suite_manifest,
    pair_round,
    suite_cells,
    suite_experiment_id,
    suite_pair_id,
    suite_rule_sha256,
)
from arci.suite_schema import SuiteManifest, SuiteTask
from tests.acceptance.helpers import EMPTY_LOG, MOD, TIMEOUT, contract
from tests.acceptance.suite_helpers import CONDITIONS, cell_keys, suite_manifest, tasks

pytestmark = pytest.mark.acceptance

KEY = "ab" * 32  # a fixed, valid rule digest for the golden vectors
MASK53 = 2**53 - 1
EXPERIMENT_ID = re.compile(r"^suite-acceptance@[0-9a-f]{64}$")
# Well-formed digests (contract 8 item 2) that are not any manifest's rule digest.
STALE_DIGEST = "0" * 64
OTHER_DIGEST = "1" * 64


# --- the tests' own oracle, written from the contract ------------------------------------


def _ref_rule_sha256(m: SuiteManifest) -> str:
    """Contract 3, rule digest: digest_payload, drop experiment_id, sort tasks and conditions."""
    payload: dict[str, Any] = dict(digest_payload(m))
    del payload["experiment_id"]
    payload["tasks"] = sorted(payload["tasks"], key=lambda t: t["task_id"])
    payload["conditions"] = sorted(payload["conditions"], key=lambda c: c["condition_id"])
    return hash_record({"domain": "arci-suite/1 rule", "content": payload})


def _ref_seed(key_hex: str, cell_index: int, r: int) -> int:
    """Contract 3, seed, with `r` already chosen (0 for fixed, the round for per_round)."""
    digest = sha256(
        b"arci-suite/1 seed"
        + bytes.fromhex(key_hex)
        + cell_index.to_bytes(4, "big")
        + r.to_bytes(4, "big")
    ).digest()
    return int.from_bytes(digest[:8], "big") & MASK53


def _ref_mode_seed(key_hex: str, cell_index: int, round: int, mode: str) -> int:
    return _ref_seed(key_hex, cell_index, 0 if mode == "fixed" else round)


def _ref_arm_order(key_hex: str, cell_index: int, round: int) -> tuple[str, str]:
    """Contract 3, arm order: the low bit of the first digest byte, with the real round."""
    bit = (
        sha256(
            b"arci-suite/1 order"
            + bytes.fromhex(key_hex)
            + cell_index.to_bytes(4, "big")
            + round.to_bytes(4, "big")
        ).digest()[0]
        & 1
    )
    return ("baseline", "candidate") if bit == 0 else ("candidate", "baseline")


@cache
def _base() -> SuiteManifest:
    return suite_manifest()


def _refields(m: SuiteManifest) -> dict[str, Any]:
    """The manifest's fields without the generated ones, for rebuilding it."""
    return m.model_dump(exclude={"record_sha256", "experiment_id"})


def _command_manifest(**overrides: object) -> SuiteManifest:
    fields: dict[str, object] = {
        "toolset": None,
        "mcp_server": McpServerSpec(argv=("python", "server.py"), snapshot=f"{MOD}:snapshot"),
        "baseline": ArmSpec(label="A", command=CommandSpec(argv=("python", "a.py"))),
        "candidate": ArmSpec(label="B", command=CommandSpec(argv=("python", "b.py"))),
        "n_tasks": 2,
        "n_conditions": 2,
        "max_rounds": 3,
        "max_errored_pairs": 1,
    }
    fields.update(overrides)
    return suite_manifest(**fields)  # pyright: ignore[reportArgumentType]


# --- cells (contract 1) -------------------------------------------------------------------


def test_cells_are_the_full_grid_in_python_string_order() -> None:
    """Contract 1, cell: N = T * K, sorted by (task_id, condition_id) in Python string order."""
    ids = ("b", "a", "B", "a.1", "a-1", "a_1", "10", "9")
    m = suite_manifest(
        tasks=tuple(SuiteTask(task_id=i, task={"input": i}) for i in ids),
        n_conditions=4,
        max_rounds=2,
        max_errored_pairs=1,
    )
    cells = suite_cells(m)
    assert isinstance(cells, tuple)
    assert len(cells) == 8 * 4 == m.n_cells
    task_order = [t.task_id for t, _ in cells[::4]]
    assert task_order == ["10", "9", "B", "a", "a-1", "a.1", "a_1", "b"]
    assert [c.condition_id for _, c in cells[:4]] == [
        "clean",
        "empty_log",
        "fetch_timeout",
        "store_error_late",
    ]
    assert [(t.task_id, c.condition_id) for t, c in cells] == list(cell_keys(m))


def test_cells_carry_the_manifest_task_and_condition_objects() -> None:
    """Contract 1, cell: one (task, fault condition); contract 3, suite_cells."""
    m = suite_manifest(tasks=tuple(reversed(tasks(3))), max_rounds=2, max_errored_pairs=1)
    by_task = {t.task_id: t for t in m.tasks}
    by_condition = {c.condition_id: c for c in m.conditions}
    for task, condition in suite_cells(m):
        assert task == by_task[task.task_id]
        assert condition == by_condition[condition.condition_id]


# --- rule digest and experiment id (contract 3) --------------------------------------------


def test_payload_already_lacks_seal_and_created_at() -> None:
    """Contract 3, rule digest: digest_payload has no record_sha256 and no created_at."""
    m = suite_manifest(created_at="2026-11-11T00:00:00Z")
    payload = digest_payload(m)
    assert "record_sha256" not in payload
    assert "created_at" not in payload
    assert "experiment_id" in payload


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"tasks": tuple(reversed(tasks(5)))},
        {"conditions": tuple(reversed(CONDITIONS))},
        {"scenario_seeds": "per_round", "alpha": "1/40", "delta": "1/8"},
    ],
    ids=["default", "reversed-tasks", "reversed-conditions", "other-rule"],
)
def test_rule_digest_matches_the_contract_formula(overrides: dict[str, object]) -> None:
    """Contract 3, rule digest: hash_record({"domain": "arci-suite/1 rule", "content": ...})."""
    m = suite_manifest(**overrides)
    digest = suite_rule_sha256(m)
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert digest == _ref_rule_sha256(m)


def test_experiment_id_is_suite_id_at_full_digest() -> None:
    """Contract 3, experiment id: f"{suite_id}@{suite_rule_sha256(m)}"; D-03 item 3."""
    m = _base()
    assert EXPERIMENT_ID.fullmatch(m.experiment_id)
    assert m.experiment_id == f"suite-acceptance@{_ref_rule_sha256(m)}"
    assert suite_experiment_id(m) == m.experiment_id


def test_suite_experiment_id_recomputes_rather_than_reading_the_stored_id() -> None:
    """Contract 3, experiment id: computed from suite_id and the recomputed digest. The stored
    id is well formed but holds the wrong digest (contract 8 item 2 fixes its shape)."""
    stale_id = f"suite-acceptance@{STALE_DIGEST}"
    stale = SuiteManifest.create(**_refields(_base()), experiment_id=stale_id)
    assert stale.experiment_id == stale_id
    assert suite_experiment_id(stale) == f"suite-acceptance@{_ref_rule_sha256(stale)}"
    assert suite_experiment_id(stale) == _base().experiment_id


def test_create_suite_manifest_seals_with_the_right_experiment_id() -> None:
    """Contract 3, create_suite_manifest: builds with the right experiment_id and seals it."""
    m = _base()
    assert isinstance(m, SuiteManifest)
    assert m.validate_seal()
    assert m.record_sha256 == hash_record(digest_payload(m))
    assert m.experiment_id == f"{m.suite_id}@{_ref_rule_sha256(m)}"


@pytest.mark.parametrize("field", ["experiment_id", "record_sha256"])
def test_create_suite_manifest_refuses_generated_fields(field: str) -> None:
    """Contract 3, create_suite_manifest: passing experiment_id or record_sha256 is TypeError."""
    fields = _refields(_base())
    value = _base().experiment_id if field == "experiment_id" else _base().record_sha256
    with pytest.raises(TypeError):
        create_suite_manifest(**fields, **{field: value})


def test_create_suite_manifest_builds_a_well_formed_id_for_every_suite_id() -> None:
    """Contract 8 item 2: the sealed experiment_id always matches
    ^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}@[0-9a-f]{64}$, so create_suite_manifest (whose draft uses
    a placeholder of that shape) builds for every SuiteId, the 64-character one included."""
    shape = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}@[0-9a-f]{64}$")
    for suite_id in ("a", "0", "a" * 64, "suite_1.2-x"):
        m = suite_manifest(suite_id=suite_id)
        assert shape.fullmatch(m.experiment_id)
        assert m.experiment_id == f"{suite_id}@{_ref_rule_sha256(m)}"
        assert m.validate_seal()


def test_rule_digest_ignores_task_order() -> None:
    """Contract 3, rule digest: manifests differing only in task order have the same digest."""
    shuffled = suite_manifest(tasks=(tasks(5)[3], tasks(5)[0], tasks(5)[4], *tasks(5)[1:3]))
    assert shuffled.tasks != _base().tasks
    assert suite_rule_sha256(shuffled) == suite_rule_sha256(_base())
    assert shuffled.experiment_id == _base().experiment_id


def test_rule_digest_ignores_condition_order() -> None:
    """Contract 3, rule digest: manifests differing only in condition order have one digest."""
    shuffled = suite_manifest(
        conditions=(CONDITIONS[2], CONDITIONS[0], CONDITIONS[3], CONDITIONS[1])
    )
    assert shuffled.conditions != _base().conditions
    assert suite_rule_sha256(shuffled) == suite_rule_sha256(_base())
    assert shuffled.experiment_id == _base().experiment_id


def test_rule_digest_ignores_created_at() -> None:
    """Contract 3, rule digest: created_at does not enter the digest."""
    dated = suite_manifest(created_at="2026-11-11T09:30:00Z")
    assert dated.created_at != _base().created_at
    assert suite_rule_sha256(dated) == suite_rule_sha256(_base())
    assert dated.experiment_id == _base().experiment_id


def test_rule_digest_ignores_stored_experiment_id_and_seal() -> None:
    """Contract 3, rule digest: experiment_id and record_sha256 do not enter the digest. The
    other id is well formed (contract 8 item 2) and holds a different suite part and digest."""
    other_id = SuiteManifest.create(
        **_refields(_base()), experiment_id=f"anything-else@{OTHER_DIGEST}"
    )
    assert other_id.experiment_id != _base().experiment_id
    other_seal = _base().model_copy(update={"record_sha256": "0" * 64})
    assert suite_rule_sha256(other_id) == suite_rule_sha256(_base())
    assert suite_rule_sha256(other_seal) == suite_rule_sha256(_base())


_FAULT = TIMEOUT  # the fetch_timeout condition's only fault


def _with_condition(condition_id: str, *faults: FaultSpec) -> tuple[Condition, ...]:
    return tuple(
        Condition(condition_id=c.condition_id, faults=faults)
        if c.condition_id == condition_id
        else c
        for c in CONDITIONS
    )


def _with_task(index: int, task: SuiteTask) -> tuple[SuiteTask, ...]:
    return tuple(task if i == index else t for i, t in enumerate(tasks(5)))


CHANGES: list[tuple[str, dict[str, object]]] = [
    ("suite_id", {"suite_id": "suite-other"}),
    ("alpha", {"alpha": "1/40"}),
    ("delta", {"delta": "1/20"}),
    ("stakes-values", {"stakes": ("1/4", "1/3")}),
    ("stakes-count", {"stakes": ("1/2",)}),
    ("max_rounds", {"max_rounds": 21}),
    ("scenario_seeds", {"scenario_seeds": "per_round"}),
    ("max_errored_pairs", {"max_errored_pairs": 5}),
    ("max_errored_pairs-zero", {"max_errored_pairs": 0}),
    ("task-content", {"tasks": _with_task(0, SuiteTask(task_id="t0", task={"input": "x"}))}),
    ("task-content-empty", {"tasks": _with_task(2, SuiteTask(task_id="t2"))}),
    ("task-id", {"tasks": _with_task(4, SuiteTask(task_id="u4", task={"input": "store 42 (4)"}))}),
    ("task-added", {"n_tasks": 6}),
    ("task-removed", {"n_tasks": 4}),
    ("condition-removed", {"n_conditions": 3}),
    (
        "condition-id",
        {
            "conditions": (
                *CONDITIONS[:3],
                Condition(condition_id="late", faults=CONDITIONS[3].faults),
            )
        },
    ),
    (
        "fault-at_occurrence",
        {
            "conditions": _with_condition(
                "fetch_timeout", _FAULT.model_copy(update={"at_occurrence": 1})
            )
        },
    ),
    (
        "fault-params",
        {
            "conditions": _with_condition(
                "fetch_timeout", _FAULT.model_copy(update={"params": {"s": 2}})
            )
        },
    ),
    (
        "fault-tool",
        {
            "conditions": _with_condition(
                "fetch_timeout", _FAULT.model_copy(update={"tool": "store"})
            )
        },
    ),
    (
        "fault-bucket",
        {
            "conditions": _with_condition(
                "fetch_timeout", _FAULT.model_copy(update={"bucket": Bucket.BENIGN})
            )
        },
    ),
    ("fault-added", {"conditions": _with_condition("clean", EMPTY_LOG)}),
    ("contract-oracle", {"contract": contract("other_oracle")}),
    ("contract-forbidden", {"contract": contract(forbidden_tools=("rm",))}),
    ("budgets-tool-calls", {"budgets": Budgets(max_tool_calls=29)}),
    ("budgets-grader", {"budgets": Budgets(grader_seconds=19.0)}),
    ("prior_runs", {"prior_runs": ("suite-acceptance@" + "0" * 64,)}),
    ("toolset", {"toolset": f"{MOD}:other_world"}),
    ("fixtures_sha256", {"fixtures_sha256": "a" * 64}),
    (
        "baseline-label",
        {"baseline": ArmSpec(label="A2", agent=f"{MOD}:good_agent", candidate_id="a")},
    ),
    (
        "baseline-agent",
        {"baseline": ArmSpec(label="A", agent=f"{MOD}:other_agent", candidate_id="a")},
    ),
    (
        "baseline-candidate_id",
        {"baseline": ArmSpec(label="A", agent=f"{MOD}:good_agent", candidate_id="a2")},
    ),
    (
        "candidate-label",
        {"candidate": ArmSpec(label="B2", agent=f"{MOD}:fragile_agent", candidate_id="b")},
    ),
    (
        "candidate-agent",
        {"candidate": ArmSpec(label="B", agent=f"{MOD}:good_agent", candidate_id="b")},
    ),
    (
        "candidate-candidate_id",
        {"candidate": ArmSpec(label="B", agent=f"{MOD}:fragile_agent", candidate_id="b2")},
    ),
    (
        "arms-swapped",
        {
            "baseline": ArmSpec(label="B", agent=f"{MOD}:fragile_agent", candidate_id="b"),
            "candidate": ArmSpec(label="A", agent=f"{MOD}:good_agent", candidate_id="a"),
        },
    ),
]


@pytest.mark.parametrize("overrides", [c[1] for c in CHANGES], ids=[c[0] for c in CHANGES])
def test_rule_digest_changes_with_any_other_field(overrides: dict[str, object]) -> None:
    """Contract 3, rule digest: any difference but order, created_at, ids or seal changes it."""
    changed = suite_manifest(**overrides)
    assert suite_rule_sha256(changed) == _ref_rule_sha256(changed)
    assert suite_rule_sha256(changed) != suite_rule_sha256(_base())
    assert changed.experiment_id != _base().experiment_id
    # Contract 3, experiment id and create_suite_manifest: stored id is suite_id@rule digest.
    assert changed.experiment_id == f"{changed.suite_id}@{_ref_rule_sha256(changed)}"
    assert suite_experiment_id(changed) == changed.experiment_id


def test_rule_digest_changes_with_fault_order_inside_a_condition() -> None:
    """Contract 3, rule digest: only tasks and conditions are sorted; fault order is content."""
    one = suite_manifest(conditions=(Condition(condition_id="noisy", faults=(EMPTY_LOG, TIMEOUT)),))
    two = suite_manifest(conditions=(Condition(condition_id="noisy", faults=(TIMEOUT, EMPTY_LOG)),))
    assert suite_rule_sha256(one) == _ref_rule_sha256(one)
    assert suite_rule_sha256(two) == _ref_rule_sha256(two)
    assert suite_rule_sha256(one) != suite_rule_sha256(two)


def test_rule_digest_changes_with_the_mcp_server() -> None:
    """Contract 3, rule digest: the mcp_server of a command-agent suite is registered content."""
    one = _command_manifest()
    two = _command_manifest(
        mcp_server=McpServerSpec(argv=("python", "server2.py"), snapshot=f"{MOD}:snapshot")
    )
    assert suite_rule_sha256(one) == _ref_rule_sha256(one)
    assert suite_rule_sha256(two) == _ref_rule_sha256(two)
    assert suite_rule_sha256(one) != suite_rule_sha256(two)
    assert one.experiment_id != two.experiment_id
    assert two.experiment_id == f"{two.suite_id}@{_ref_rule_sha256(two)}"


# --- seeds (contract 3) --------------------------------------------------------------------


# (cell_index, r) -> seed for KEY, from the contract formula; r = 0 is the fixed-mode value.
SEED_GOLDEN: dict[tuple[int, int], int] = {
    (0, 0): 7745997076764697,
    (0, 1): 6173883320097022,
    (0, 2): 3268818503444547,
    (0, 2**32 - 1): 3400451472438760,
    (1, 0): 1024471786534229,
    (1, 1): 2988387906586976,
    (1, 2): 4543964975579693,
    (7, 0): 8762126976647915,
    (7, 1): 8295370069104048,
    (7, 2): 5907340520951977,
    (2**32 - 1, 0): 1876799351316680,
    (2**32 - 1, 1): 3573866932771022,
    (2**32 - 1, 2**32 - 1): 8908314805122393,
}


@pytest.mark.parametrize(("cell_index", "r"), sorted(SEED_GOLDEN))
def test_seed_golden_vectors(cell_index: int, r: int) -> None:
    """Contract 3, seed: golden vectors of the sha256-v1 formula for key "ab" * 32."""
    assert _ref_seed(KEY, cell_index, r) == SEED_GOLDEN[(cell_index, r)]
    if r == 0:
        for round in (1, 2, 2**32 - 1):
            assert cell_seed(KEY, cell_index, round, "fixed") == SEED_GOLDEN[(cell_index, 0)]
    else:
        assert cell_seed(KEY, cell_index, r, "per_round") == SEED_GOLDEN[(cell_index, r)]


def test_fixed_seed_is_the_same_in_every_round() -> None:
    """Contract 3, seed: r = 0 when scenario_seeds == "fixed", whatever the round."""
    for cell_index in (0, 3, 19, 1000):
        seeds = {cell_seed(KEY, cell_index, round, "fixed") for round in range(1, 30)}
        assert seeds == {_ref_seed(KEY, cell_index, 0)}


def test_per_round_seed_differs_between_rounds() -> None:
    """Contract 3, seed: r = round when scenario_seeds == "per_round"."""
    for cell_index in (0, 3, 19):
        seeds = [cell_seed(KEY, cell_index, round, "per_round") for round in range(1, 30)]
        assert seeds == [_ref_seed(KEY, cell_index, round) for round in range(1, 30)]
        assert len(set(seeds)) == len(seeds)
        assert _ref_seed(KEY, cell_index, 0) not in seeds


def test_seed_fits_in_53_bits() -> None:
    """Contract 3, seed: masked to 53 bits so JSON readers using doubles keep it exact."""
    keys = (KEY, "0" * 64, "f" * 64, sha256(b"x").hexdigest())
    for key in keys:
        for cell_index in range(40):
            for mode, round in (("fixed", 1), ("per_round", 1), ("per_round", 7)):
                seed = cell_seed(key, cell_index, round, mode)
                assert isinstance(seed, int)
                assert 0 <= seed <= MASK53
                assert seed == _ref_mode_seed(key, cell_index, round, mode)


@pytest.mark.parametrize(
    ("key", "cell_index", "round", "mode"),
    [
        ("AB" * 32, 0, 1, "fixed"),  # upper case
        ("ab" * 31, 0, 1, "fixed"),  # 62 characters
        ("ab" * 33, 0, 1, "fixed"),  # 66 characters
        ("ab" * 32 + "a", 0, 1, "fixed"),  # 65 characters
        ("ab" * 31 + "ag", 0, 1, "fixed"),  # not hex
        ("", 0, 1, "fixed"),
        (KEY, -1, 1, "fixed"),
        (KEY, 2**32, 1, "fixed"),
        (KEY, 0, 0, "fixed"),  # round < 1 even though fixed mode ignores the round
        (KEY, 0, 0, "per_round"),
        (KEY, 0, -1, "per_round"),
        (KEY, 0, 2**32, "fixed"),
        (KEY, 0, 2**32, "per_round"),
        (KEY, 0, 1, "random"),
        (KEY, 0, 1, "FIXED"),
        (KEY, 0, 1, ""),
    ],
)
def test_cell_seed_domain_errors(key: str, cell_index: int, round: int, mode: str) -> None:
    """Contract 3, seed: ValueError for a bad key, index, round or mode."""
    with pytest.raises(ValueError):
        cell_seed(key, cell_index, round, mode)


# --- arm order (contract 3) ----------------------------------------------------------------


# (cell_index, round) -> low bit of the first order-digest byte for KEY.
ORDER_GOLDEN: dict[tuple[int, int], int] = {
    (0, 1): 0,
    (0, 2): 0,
    (0, 3): 1,
    (0, 4): 0,
    (0, 5): 1,
    (1, 4): 1,
    (7, 1): 1,
    (7, 4): 0,
    (2**32 - 1, 1): 0,
    (2**32 - 1, 2): 1,
    (2**32 - 1, 2**32 - 1): 0,
}


@pytest.mark.parametrize(("cell_index", "round"), sorted(ORDER_GOLDEN))
def test_arm_order_golden_vectors(cell_index: int, round: int) -> None:
    """Contract 3, arm order: ("baseline", "candidate") when the bit is 0, else reversed."""
    bit = ORDER_GOLDEN[(cell_index, round)]
    expected = ("baseline", "candidate") if bit == 0 else ("candidate", "baseline")
    assert _ref_arm_order(KEY, cell_index, round) == expected
    assert tuple(arm_order(KEY, cell_index, round)) == expected


def test_arm_order_uses_the_real_round() -> None:
    """Contract 3, arm order: the real round is always used, in both seed modes."""
    for cell_index in range(8):
        orders = [tuple(arm_order(KEY, cell_index, round)) for round in range(1, 25)]
        assert orders == [_ref_arm_order(KEY, cell_index, round) for round in range(1, 25)]
    # Cell 0 of KEY: rounds 1 and 3 differ, so a mode that froze the round would be caught.
    assert tuple(arm_order(KEY, 0, 1)) != tuple(arm_order(KEY, 0, 3))


def test_arm_order_for_suite_digests_in_both_modes() -> None:
    """Contract 3, arm order: same formula for a fixed-seed and a per-round-seed suite."""
    for mode in ("fixed", "per_round"):
        m = suite_manifest(scenario_seeds=mode, max_rounds=4, max_errored_pairs=1)
        digest = _ref_rule_sha256(m)
        for cell_index in range(m.n_cells):
            for round in range(1, 5):
                got = tuple(arm_order(suite_rule_sha256(m), cell_index, round))
                assert got == _ref_arm_order(digest, cell_index, round)


@pytest.mark.parametrize(
    ("key", "cell_index", "round"),
    [
        ("AB" * 32, 0, 1),
        ("ab" * 31, 0, 1),
        ("ab" * 33, 0, 1),
        ("ab" * 31 + "zz", 0, 1),
        ("", 0, 1),
        (KEY, -1, 1),
        (KEY, 2**32, 1),
        (KEY, 0, 0),
        (KEY, 0, -1),
        (KEY, 0, 2**32),
    ],
)
def test_arm_order_domain_errors(key: str, cell_index: int, round: int) -> None:
    """Contract 3, domains: bad key, cell_index outside [0, 2**32), round outside [1, 2**32)."""
    with pytest.raises(ValueError):
        arm_order(key, cell_index, round)


# --- ids (contract 3) ----------------------------------------------------------------------


def test_suite_pair_id_format() -> None:
    """Contract 3, ids: suite_pair_id(r, t, c) = f"r{r:06d}:{t}:{c}"."""
    assert suite_pair_id(1, "t0", "clean") == "r000001:t0:clean"
    assert suite_pair_id(42, "a.b-c", "x_y") == "r000042:a.b-c:x_y"
    assert suite_pair_id(999999, "t", "c") == "r999999:t:c"


@pytest.mark.parametrize(
    ("pair_id", "expected"),
    [
        ("r000001:t0:clean", 1),
        ("r000042:a.b-c:x_y", 42),
        ("r100000:t:c", 100000),
        ("r999999:t:c", 999999),
        ("r000003:task with spaces:cond", 3),
    ],
)
def test_pair_round_accepts_pair_ids(pair_id: str, expected: int) -> None:
    """Contract 3, ids: pair_round returns the round of a matching pair id."""
    assert pair_round(pair_id) == expected


def test_pair_round_inverts_suite_pair_id() -> None:
    """Contract 3, ids: pair_round(suite_pair_id(r, t, c)) == r."""
    for r in (1, 2, 17, 4096, 999999):
        assert pair_round(suite_pair_id(r, "t3", "fetch_timeout")) == r


@pytest.mark.parametrize(
    "pair_id",
    [
        "",
        "r000000:t0:clean",  # number below 1
        "r00001:t0:clean",  # five digits
        "r0000001:t0:clean",  # seven digits
        "r000001:t0",  # no condition
        "r000001",
        "r000001:t0:clean:baseline",  # a trial id, not a pair id
        "r000001::clean",  # empty task
        "r000001:t0:",  # empty condition
        "R000001:t0:clean",
        "x000001:t0:clean",
        "000001:t0:clean",
        "r00000a:t0:clean",
        "r-00001:t0:clean",
        "r+00001:t0:clean",
        " r000001:t0:clean",
        "r" + chr(0x0660) * 5 + chr(0x0661) + ":t0:clean",  # Arabic-Indic digits, not [0-9]
        "clean:00000",  # a v1 pair id
    ],
)
def test_pair_round_rejects_everything_else(pair_id: str) -> None:
    """Contract 3, ids: ValueError for anything not matching the pattern with a number >= 1."""
    with pytest.raises(ValueError):
        pair_round(pair_id)


# --- build_suite_round (contract 3) --------------------------------------------------------


def test_round_has_two_specs_per_cell_in_cell_order_baseline_first() -> None:
    """Contract 3, build_suite_round: 2 * N specs, cell order, baseline then candidate."""
    m = suite_manifest(tasks=tuple(reversed(tasks(5))))
    specs = build_suite_round(m, 3)
    assert len(specs) == 2 * m.n_cells == 40
    assert [s.arm for s in specs] == ["baseline", "candidate"] * m.n_cells
    keys = cell_keys(m)
    for i, (task_id, condition_id) in enumerate(keys):
        for spec in specs[2 * i : 2 * i + 2]:
            assert (spec.task_id, spec.condition.condition_id) == (task_id, condition_id)


def test_round_ids() -> None:
    """Contract 3, ids: pair_id = f"r{r:06d}:{t}:{c}", trial_id = f"{pair_id}:{arm}"."""
    m = _base()
    first = build_suite_round(m, 1)
    assert [s.trial_id for s in first[:3]] == [
        "r000001:t0:clean:baseline",
        "r000001:t0:clean:candidate",
        "r000001:t0:empty_log:baseline",
    ]
    last = build_suite_round(m, 20)
    assert last[-1].trial_id == "r000020:t4:store_error_late:candidate"
    for r, specs in ((1, first), (20, last)):
        for s in specs:
            assert s.pair_id == f"r{r:06d}:{s.task_id}:{s.condition.condition_id}"
            assert s.pair_id == suite_pair_id(r, s.task_id, s.condition.condition_id)
            assert s.trial_id == f"{s.pair_id}:{s.arm}"
            assert pair_round(s.pair_id) == r


@pytest.mark.parametrize("mode", ["fixed", "per_round"])
def test_round_specs_equal_the_contract_field_list(mode: str) -> None:
    """Contract 3, build_suite_round: every TrialSpec field, defaults for the rest."""
    budgets = Budgets(max_tool_calls=20, max_seconds=10.0)
    m = suite_manifest(
        tasks=(tasks(3)[2], tasks(3)[0], tasks(3)[1]),
        alpha="1/40",
        delta="1/8",
        scenario_seeds=mode,
        budgets=budgets,
        max_rounds=3,
        max_errored_pairs=1,
    )
    digest = _ref_rule_sha256(m)
    task_of = {t.task_id: t.task for t in m.tasks}
    condition_of = {c.condition_id: c for c in m.conditions}
    arms = (("baseline", m.baseline), ("candidate", m.candidate))
    for round in (1, 2, 3):
        specs = build_suite_round(m, round)
        expected: list[TrialSpec] = []
        for i, (task_id, condition_id) in enumerate(cell_keys(m)):
            pair_id = f"r{round:06d}:{task_id}:{condition_id}"
            for arm, arm_spec in arms:
                expected.append(
                    TrialSpec(
                        experiment_id=m.experiment_id,
                        trial_id=f"{pair_id}:{arm}",
                        pair_id=pair_id,
                        arm=arm,  # pyright: ignore[reportArgumentType]
                        variant=arm_spec.label,
                        agent=arm_spec.agent,
                        command=arm_spec.command,
                        toolset=m.toolset,
                        mcp_server=m.mcp_server,
                        decisions=None,
                        task_id=task_id,
                        task=task_of[task_id],
                        condition=condition_of[condition_id],
                        seed=_ref_mode_seed(digest, i, round, mode),
                        budgets=budgets,
                        alpha=float(Fraction(1, 40)),
                        delta=float(Fraction(1, 8)),
                    )
                )
        assert [spec_sha256(s) for s in specs] == [spec_sha256(s) for s in expected]
        assert list(specs) == expected


def test_round_spec_rule_mirrors_and_defaults() -> None:
    """Contract 3, build_suite_round: alpha/delta as floats of the fractions, v1 defaults."""
    m = suite_manifest(alpha="1/40", delta="1/8", max_rounds=2, max_errored_pairs=1)
    defaults = TrialSpec.model_fields
    for s in build_suite_round(m, 2):
        assert s.alpha == 0.025
        assert s.delta == 0.125
        assert s.decisions is None
        assert s.variant == ("A" if s.arm == "baseline" else "B")
        assert s.agent == (m.baseline.agent if s.arm == "baseline" else m.candidate.agent)
        assert s.command is None
        assert s.toolset == m.toolset
        assert s.mcp_server is None
        for name in ("interval_method", "looks", "tool_mode", "recording", "replay_final_state"):
            assert getattr(s, name) == defaults[name].default


def test_round_specs_of_command_agents() -> None:
    """Contract 3, build_suite_round: command, mcp_server and toolset come from the manifest."""
    m = _command_manifest()
    for s in build_suite_round(m, 1):
        arm_spec = m.baseline if s.arm == "baseline" else m.candidate
        assert s.agent is None
        assert s.command == arm_spec.command
        assert s.variant == arm_spec.label
        assert s.toolset is None
        assert s.mcp_server == m.mcp_server


@pytest.mark.parametrize("mode", ["fixed", "per_round"])
def test_round_seeds_shared_by_arms_distinct_across_cells(mode: str) -> None:
    """Contract 3, seed: both arms share the seed; no two cells of a round share one."""
    m = suite_manifest(scenario_seeds=mode)
    digest = _ref_rule_sha256(m)
    for round in (1, 2, 20):
        specs = build_suite_round(m, round)
        baseline = [s.seed for s in specs[0::2]]
        candidate = [s.seed for s in specs[1::2]]
        assert baseline == candidate
        assert len(set(baseline)) == m.n_cells
        assert baseline == [_ref_mode_seed(digest, i, round, mode) for i in range(m.n_cells)]
        assert baseline == [
            cell_seed(suite_rule_sha256(m), i, round, mode) for i in range(m.n_cells)
        ]
        assert all(0 <= seed <= MASK53 for seed in baseline)


def test_fixed_mode_cell_keeps_its_seed_and_per_round_does_not() -> None:
    """Contract 3, seed: fixed uses r = 0 in every round; per_round uses r = round."""
    fixed = suite_manifest(max_rounds=3, max_errored_pairs=1)
    rounds = [[s.seed for s in build_suite_round(fixed, r)[0::2]] for r in (1, 2, 3)]
    assert rounds[0] == rounds[1] == rounds[2]
    per_round = suite_manifest(scenario_seeds="per_round", max_rounds=3, max_errored_pairs=1)
    rows = [[s.seed for s in build_suite_round(per_round, r)[0::2]] for r in (1, 2, 3)]
    for i in range(per_round.n_cells):
        assert len({rows[0][i], rows[1][i], rows[2][i]}) == 3


def test_round_seed_comes_from_content_and_experiment_id_as_stored() -> None:
    """Contract 3, build_suite_round: experiment_id as stored; seed from the recomputed digest."""
    old = _base()
    resealed = SuiteManifest.create(
        **{**_refields(old), "alpha": "1/40"}, experiment_id=old.experiment_id
    )
    assert resealed.experiment_id == old.experiment_id
    new_digest = _ref_rule_sha256(resealed)
    old_digest = _ref_rule_sha256(old)
    assert new_digest != old_digest
    specs = build_suite_round(resealed, 2)
    assert {s.experiment_id for s in specs} == {old.experiment_id}
    seeds = [s.seed for s in specs[0::2]]
    assert seeds == [_ref_seed(new_digest, i, 0) for i in range(resealed.n_cells)]
    assert seeds != [_ref_seed(old_digest, i, 0) for i in range(old.n_cells)]


def test_round_is_the_same_for_reordered_or_redated_manifests() -> None:
    """Contract 3: digest, cell order and specs do not depend on task/condition order or date."""
    other = suite_manifest(
        tasks=tuple(reversed(tasks(5))),
        conditions=tuple(reversed(CONDITIONS)),
        created_at="2026-11-11T00:00:00Z",
    )
    for round in (1, 7):
        assert build_suite_round(other, round) == build_suite_round(_base(), round)


@pytest.mark.parametrize("round", [0, -1, 21, 100])
def test_round_outside_registered_rounds_is_value_error(round: int) -> None:
    """Contract 3, build_suite_round: ValueError unless 1 <= round <= max_rounds."""
    with pytest.raises(ValueError):
        build_suite_round(_base(), round)


def test_single_round_suite_has_only_round_one() -> None:
    """Contract 3, build_suite_round: with max_rounds = 1, round 2 is a ValueError."""
    m = suite_manifest(max_rounds=1, acknowledge_single_round=True, max_errored_pairs=1)
    assert len(build_suite_round(m, 1)) == 2 * m.n_cells
    with pytest.raises(ValueError):
        build_suite_round(m, 2)
    assert build_suite_schedule(m) == build_suite_round(m, 1)


# --- build_suite_schedule (contract 3) -----------------------------------------------------


@pytest.mark.parametrize("mode", ["fixed", "per_round"])
def test_schedule_is_rounds_concatenated_with_unique_identities(mode: str) -> None:
    """Contract 3, build_suite_schedule: rounds 1..max_rounds; unique trial ids and spec_sha256."""
    m = suite_manifest(scenario_seeds=mode)
    schedule = build_suite_schedule(m)
    expected: tuple[TrialSpec, ...] = ()
    for round in range(1, m.max_rounds + 1):
        expected += build_suite_round(m, round)
    assert schedule == expected
    assert len(schedule) == 2 * m.n_cells * m.max_rounds == 800
    assert len({s.trial_id for s in schedule}) == len(schedule)
    assert len({s.pair_id for s in schedule}) == m.n_cells * m.max_rounds
    assert len({spec_sha256(s) for s in schedule}) == len(schedule)
    assert [pair_round(s.pair_id) for s in schedule[:: 2 * m.n_cells]] == list(
        range(1, m.max_rounds + 1)
    )


def test_schedule_is_deterministic() -> None:
    """Contract 3: the schedule derives from the manifest alone."""
    m = suite_manifest(n_tasks=2, n_conditions=2, max_rounds=3, max_errored_pairs=1)
    assert build_suite_schedule(m) == build_suite_schedule(m)
    assert len(build_suite_schedule(m)) == 2 * 4 * 3


# --- module discipline (contract 3) --------------------------------------------------------


def _imports() -> set[str]:
    source = Path(suite_schedule_module.__file__).read_text(encoding="utf-8")
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = "arci" + (f".{node.module}" if node.module else "")
                if node.module:
                    names.add(base)
                else:
                    names.update(f"{base}.{alias.name}" for alias in node.names)
            elif node.module == "arci":
                names.update(f"arci.{alias.name}" for alias in node.names)
            elif node.module:
                names.add(node.module)
    return names


def test_suite_schedule_does_not_use_random() -> None:
    """Contract 3: no `random` module anywhere in suite_schedule.py."""
    assert not any(name.split(".")[0] == "random" for name in _imports())


def test_suite_schedule_imports_only_allowed_modules() -> None:
    """Contract 3: imports only the standard library, arci.hashing, arci.schema, suite_schema."""
    allowed = {"arci.hashing", "arci.schema", "arci.suite_schema"}
    for name in _imports():
        top = name.split(".")[0]
        if top == "arci":
            assert name in allowed, name
        else:
            assert top in sys.stdlib_module_names, name
