from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from arci.schedule import spec_sha256
from arci.schema import ToolMode
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
from arci.suite_schema import SuiteManifest
from tests.unit.suite.helpers import manifest_fields


def test_digest_and_create() -> None:
    fields = manifest_fields()
    del fields["experiment_id"]
    m = create_suite_manifest(**fields)
    assert m.validate_seal()
    assert m.experiment_id == suite_experiment_id(m) == f"suite@{suite_rule_sha256(m)}"
    payload = m.model_dump(mode="json", exclude={"record_sha256", "created_at", "experiment_id"})
    payload["tasks"] = sorted(payload["tasks"], key=lambda t: t["task_id"])
    payload["conditions"] = sorted(payload["conditions"], key=lambda c: c["condition_id"])
    encoded = json.dumps(
        {"domain": "arci-suite/1 rule", "content": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    assert suite_rule_sha256(m) == hashlib.sha256(encoded).hexdigest()
    for update in (
        {"tasks": m.tasks[::-1]},
        {"conditions": m.conditions[::-1]},
        {"created_at": "later"},
        {"experiment_id": "another"},
        {"record_sha256": "corrupt"},
    ):
        assert suite_rule_sha256(m.model_copy(update=update)) == suite_rule_sha256(m)
    for field in ("experiment_id", "record_sha256"):
        with pytest.raises(TypeError):
            create_suite_manifest(**fields, **{field: "forbidden"})


# Include the literal version fields through model_copy: their invalid alternative
# values must still be hashed, rather than silently replaced by the current version.
DIGEST_CHANGES: dict[str, Any] = {
    "schema_version": "future",
    "suite_id": "other",
    "tasks": (),
    "conditions": (),
    "toolset": "other:tools",
    "mcp_server": {"name": "other"},
    "contract": {"oracle": "other:oracle"},
    "baseline": {"label": "other"},
    "candidate": {"label": "other"},
    "alpha": "1/10",
    "delta": "1/5",
    "stakes": ("1/3",),
    "max_rounds": 101,
    "scenario_seeds": "per_round",
    "max_errored_pairs": 3,
    "seed_derivation": "future",
    "acknowledge_single_round": True,
    "budgets": {"max_seconds": 5.5},
    "fixtures_sha256": "fixture",
    "prior_runs": ("earlier",),
}


@pytest.mark.parametrize("field", DIGEST_CHANGES)
def test_every_rule_field_changes_digest(field: str) -> None:
    m = SuiteManifest(**manifest_fields())
    assert suite_rule_sha256(
        m.model_copy(update={field: DIGEST_CHANGES[field]})
    ) != suite_rule_sha256(m)


def test_digest_field_coverage_and_task_metadata_is_not_volatile() -> None:
    assert set(DIGEST_CHANGES) == set(SuiteManifest.model_fields) - {
        "record_sha256",
        "experiment_id",
        "created_at",
    }
    m = SuiteManifest(**manifest_fields())
    for key in ("created_at", "record_sha256", "experiment_id", "duration_ms", "value"):
        task = m.tasks[0].model_copy(update={"task": m.tasks[0].task | {key: 1.25}})
        assert suite_rule_sha256(
            m.model_copy(update={"tasks": (task, *m.tasks[1:])})
        ) != suite_rule_sha256(m)


@pytest.mark.parametrize("mode", ["fixed", "per_round"])
def test_hash_seed_and_order_vectors(mode: str) -> None:
    key = "0123456789abcdef" * 4
    for index in (0, 1, 2**32 - 1):
        for round in (1, 2, 2**32 - 1):
            suffix = bytes.fromhex(key) + index.to_bytes(4, "big")
            r = 0 if mode == "fixed" else round
            expected = int.from_bytes(
                hashlib.sha256(b"arci-suite/1 seed" + suffix + r.to_bytes(4, "big")).digest()[:8],
                "big",
            ) & (2**53 - 1)
            assert cell_seed(key, index, round, mode) == expected
            bit = (
                hashlib.sha256(b"arci-suite/1 order" + suffix + round.to_bytes(4, "big")).digest()[
                    0
                ]
                & 1
            )
            assert arm_order(key, index, round) == (
                ("candidate", "baseline") if bit else ("baseline", "candidate")
            )


@pytest.mark.parametrize(
    "key,index,round",
    [
        ("", 0, 1),
        ("a" * 63, 0, 1),
        ("A" * 64, 0, 1),
        ("g" * 64, 0, 1),
        ("00 " * 32, 0, 1),
        ("0" * 64, -1, 1),
        ("0" * 64, 2**32, 1),
        ("0" * 64, 0, 0),
        ("0" * 64, 0, 2**32),
        ("0" * 64, 0.5, 1),
    ],
)
def test_hash_domains(key: str, index: Any, round: int) -> None:
    with pytest.raises(ValueError):
        cell_seed(key, index, round, "fixed")
    with pytest.raises(ValueError):
        arm_order(key, index, round)


def test_unknown_seed_mode() -> None:
    with pytest.raises(ValueError):
        cell_seed("0" * 64, 0, 1, "unknown")


@pytest.mark.parametrize(
    "bad",
    [
        "r000000:a:b",
        "r1:a:b",
        "r000001::b",
        "r000001:a:",
        "r000001:a:b:c",
        "r1000000:a:b",
        "x000001:a:b",
    ],
)
def test_pair_round_rejects_invalid_ids(bad: str) -> None:
    with pytest.raises(ValueError):
        pair_round(bad)


@pytest.mark.parametrize("mode", ["fixed", "per_round"])
def test_schedule_counts_order_identity_and_mirrors(mode: str) -> None:
    m = SuiteManifest(**manifest_fields(max_rounds=3, max_errored_pairs=1, scenario_seeds=mode))
    assert [(t.task_id, c.condition_id) for t, c in suite_cells(m)] == [
        ("a", "clean"),
        ("a", "z"),
        ("b", "clean"),
        ("b", "z"),
    ]
    schedule = build_suite_schedule(m)
    assert len(schedule) == 24
    assert len({spec_sha256(s) for s in schedule}) == len(schedule)
    assert schedule == tuple(s for r in (1, 2, 3) for s in build_suite_round(m, r))
    for r in (1, 2, 3):
        specs = build_suite_round(m, r)
        assert len({s.seed for s in specs}) == m.n_cells
        for i, (task, condition) in enumerate(suite_cells(m)):
            a, b = specs[2 * i : 2 * i + 2]
            assert (a.arm, b.arm) == ("baseline", "candidate")
            assert a.seed == b.seed == cell_seed(suite_rule_sha256(m), i, r, mode)
            assert a.pair_id == b.pair_id == suite_pair_id(r, task.task_id, condition.condition_id)
            assert pair_round(a.pair_id) == r
            for s in (a, b):
                arm = m.baseline if s.arm == "baseline" else m.candidate
                assert s.trial_id == f"{s.pair_id}:{s.arm}"
                assert s.experiment_id == "supplied-id@" + "0" * 64
                assert (s.variant, s.agent, s.command) == (arm.label, arm.agent, arm.command)
                assert (s.task, s.condition, s.budgets) == (task.task, condition, m.budgets)
                assert (s.toolset, s.mcp_server, s.decisions) == (m.toolset, m.mcp_server, None)
                assert (s.alpha, s.delta, s.looks) == (0.05, 0.1, ())
                assert s.interval_method == "clopper_pearson"
                assert (s.tool_mode, s.recording, s.replay_final_state) == (
                    ToolMode.RECORD,
                    (),
                    None,
                )
    seeds1 = [s.seed for s in build_suite_round(m, 1)]
    seeds2 = [s.seed for s in build_suite_round(m, 2)]
    assert (seeds1 == seeds2) == (mode == "fixed")
    changed = build_suite_schedule(m.model_copy(update={"stakes": ("1/3",)}))
    assert all(spec_sha256(a) != spec_sha256(b) for a, b in zip(schedule, changed, strict=True))


def test_round_domain_and_collision(monkeypatch: pytest.MonkeyPatch) -> None:
    m = SuiteManifest(**manifest_fields())
    for r in (0, 101):
        with pytest.raises(ValueError):
            build_suite_round(m, r)

    def colliding_seed(*args: object) -> int:
        return 1

    monkeypatch.setattr("arci.suite_schedule.cell_seed", colliding_seed)
    with pytest.raises(ValueError, match=r"^seed collision$"):
        build_suite_round(m, 1)


def test_pair_round_accepts_noncolon_components() -> None:
    assert pair_round("r000001:a:b\n") == 1
    assert pair_round("r999999: white space :é") == 999999
