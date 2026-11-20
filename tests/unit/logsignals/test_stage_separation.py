"""Stage 1 pairs nothing: it cannot reach `describe` and it reads no outcome it does not need."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bench.logsignals import analyze
from tests.unit.logsignals import reachability, tables


def _reachable(roots: list[str]) -> set[str]:
    """Every name reachable from these functions of `analyze`, across the sibling modules too."""
    return reachability.reachable(analyze.__file__, roots)


def test_stage_one_cannot_reach_describe() -> None:
    reached = _reachable(["stage_one", "_run_stage_one"])
    assert "stage_one" in reached
    assert "describe" not in reached
    assert "aggregate" not in reached
    assert "rho_of_block" not in reached
    assert "midranks" not in reached
    # MINOR 9 of review 3: the walk follows calls into the sibling modules by name, so a forbidden
    # call added inside a helper of another module of `bench/logsignals` is reached as well. It
    # does cross: `analyze` defines no `check`, and the helper of `check_result`'s one is reached
    # through that name.
    assert "_found_counts" in _reachable(["check"])
    # The same walk does reach the pairing code from stage 2, so the check is not vacuous.
    assert "describe" in _reachable(["_run_stage_two"])


def test_stage_one_runs_with_describe_replaced_by_a_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _refuse(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("stage 1 called describe")

    monkeypatch.setattr(analyze, "describe", _refuse)
    signal, outcome = tables.write_tables(tmp_path, tables.both_halves())
    code = analyze.main(
        [
            "--stage",
            "1",
            "--signal",
            str(signal),
            "--outcome",
            str(outcome),
            "--half",
            "confirmation",
            "--out-dir",
            str(tmp_path),
        ]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["all_same"] is True


def test_stage_one_ignores_the_outcome_of_a_path_it_does_not_read(tmp_path: Path) -> None:
    sessions = tables.both_halves()
    garbled = [
        session
        if session.half == "confirmation"
        else tables.with_outcome(session, f"{tables.CANARY}-not-a-number")
        for session in sessions
    ]
    signal, outcome = tables.write_tables(tmp_path, sessions, garbled)
    counts = analyze.stage_one(signal, outcome, "confirmation")
    assert counts["all_same"] is True

    # The same table stops the half that does read those paths.
    with pytest.raises(analyze.TableInvalid):
        _ = analyze.stage_one(signal, outcome, "discovery")


def test_stage_one_writes_and_refuses_to_overwrite_its_counts(tmp_path: Path) -> None:
    signal, outcome = tables.write_tables(tmp_path, tables.both_halves())
    arguments = [
        "--stage",
        "1",
        "--signal",
        str(signal),
        "--outcome",
        str(outcome),
        "--half",
        "confirmation",
        "--out-dir",
        str(tmp_path),
    ]
    assert analyze.main(arguments) == 0
    written = (tmp_path / "checks_confirmation.json").read_bytes()
    assert analyze.main(arguments) == 2
    assert (tmp_path / "checks_confirmation.json").read_bytes() == written


def test_a_check_that_differs_is_printed_and_exits_three(tmp_path: Path) -> None:
    # The table holds both halves; only the half under test is short.
    signal, outcome = tables.write_tables(tmp_path, tables.both_halves_short("confirmation"))
    code = analyze.main(
        [
            "--stage",
            "1",
            "--signal",
            str(signal),
            "--outcome",
            str(outcome),
            "--half",
            "confirmation",
            "--out-dir",
            str(tmp_path),
        ]
    )
    assert code == 3
    counts = json.loads((tmp_path / "checks_confirmation.json").read_text(encoding="utf-8"))
    assert counts["all_same"] is False
    different = {
        check["name"]: check for check in counts["checks"] if check["verdict"] == "different"
    }
    assert different["sessions"] == {
        "name": "sessions",
        "found": 422,
        "registered": 423,
        "verdict": "different",
    }
    assert different["month_2026-06"]["found"] == 108


def test_the_checks_file_prints_only_the_two_counts_the_registration_names(tmp_path: Path) -> None:
    # Decision 7 (finding 7): `outcome_missing` is a count over this half's outcome values and
    # the registration does not name it. It stays in the full-precision object of `describe`.
    sessions = tables.both_halves()
    gapped = [tables.with_outcome(sessions[0], ""), *sessions[1:]]
    signal, outcome = tables.write_tables(tmp_path, gapped)
    counts = analyze.stage_one(signal, outcome, "confirmation")
    also = counts["also_printed"]
    assert isinstance(also, dict)
    assert set(also) == {"month_unknown", "model_unknown"}
    assert "outcome_missing" not in json.dumps(counts)

    description = analyze.describe(signal, outcome, "confirmation")
    checks = description["checks"]
    assert isinstance(checks, dict)
    assert checks["outcome_missing"] == 1


def test_a_month_outside_the_six_is_a_difference(tmp_path: Path) -> None:
    sessions = tables.registered_sessions("confirmation")
    sessions = [tables.with_month(sessions[0], "2026-03"), *sessions[1:]]
    signal, outcome = tables.write_tables(tmp_path, sessions)
    counts = analyze.stage_one(signal, outcome, "confirmation")
    assert counts["all_same"] is False
    reported = counts["checks"]
    assert isinstance(reported, list)
    names = {
        str(check["name"]): check
        for check in reported
        if isinstance(check, dict) and check["verdict"] == "different"
    }
    assert names["month_2026-03"]["found"] == 1
    assert names["month_2026-03"]["registered"] == 0
