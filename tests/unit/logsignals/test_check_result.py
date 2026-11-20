"""The result file against the registered disclosure rules and formats."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from bench.logsignals import check_result
from tests.unit.logsignals import pipeline, tables


def _result(tmp_path: Path, half: str = "confirmation") -> Any:
    _signal, _outcome, out_dir = pipeline.run_both_stages(tmp_path, half)
    return pipeline.read_json(out_dir / f"result_{half}.json")


def _run(tmp_path: Path, result: Any, name: str = "doctored.json") -> tuple[int, str]:
    path = tmp_path / name
    _ = path.write_text(json.dumps(result), encoding="utf-8")
    code = check_result.main(["--result", str(path)])
    return code, ""


def test_every_result_the_tests_produce_is_accepted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for half in ("confirmation", "discovery"):
        result = _result(tmp_path / half, half)
        check_result.check(result)
        code, _ = _run(tmp_path, result, f"{half}.json")
        assert code == 0
    assert capsys.readouterr().err == ""


def test_the_not_formed_forms_are_accepted(tmp_path: Path) -> None:
    from bench.logsignals import analyze

    # The result file records the start time (decision 6), so the provenance carries it.
    provenance = pipeline.provenance()
    signal, outcome = tables.write_tables(
        tmp_path / "small", tables.make_sessions(repositories=9, per_repository=20)
    )
    below = analyze.printed_result(analyze.describe(signal, outcome, "confirmation"), provenance)
    check_result.check(below)

    signal, outcome = tables.write_tables(
        tmp_path / "ten", tables.make_sessions(repositories=10, per_repository=16)
    )
    at_ten = analyze.printed_result(analyze.describe(signal, outcome, "confirmation"), provenance)
    check_result.check(at_ten)
    extra = at_ten["first_measure_repository"]
    assert isinstance(extra, dict)
    assert extra["loo_range"] == "not formed"


def _failure(result: Any) -> str:
    with pytest.raises(check_result.RuleFailed) as raised:
        check_result.check(result)
    return raised.value.rule


def test_an_extra_key_is_refused(tmp_path: Path) -> None:
    result = _result(tmp_path)
    doctored = copy.deepcopy(result)
    doctored["note"] = "anything"
    assert _failure(doctored) == "allowed-keys"
    assert _run(tmp_path, doctored)[0] == 4


def test_a_per_repository_value_is_refused(tmp_path: Path) -> None:
    result = _result(tmp_path)
    doctored = copy.deepcopy(result)
    doctored["first_measure_repository"]["largest_repository_weight"] = 71
    assert _failure(doctored) == "allowed-keys"

    doctored = copy.deepcopy(result)
    doctored["measures"]["no_reasoning_share"]["repository"]["per_repository"] = [0.1, -0.2]
    assert _failure(doctored) == "allowed-keys"


def test_a_rho_under_the_floor_is_refused(tmp_path: Path) -> None:
    result = _result(tmp_path)
    doctored = copy.deepcopy(result)
    doctored["measures"]["no_reasoning_share"]["repository_month"]["m"] = 9
    assert _failure(doctored) == "rho-floor"

    doctored = copy.deepcopy(result)
    doctored["measures"]["reasoning_tokens"]["repository"]["W"] = 149
    assert _failure(doctored) == "rho-floor"


def test_a_range_over_ten_repositories_is_refused(tmp_path: Path) -> None:
    result = _result(tmp_path)
    doctored = copy.deepcopy(result)
    doctored["measures"]["no_reasoning_share"]["repository"]["m"] = 10
    assert _failure(doctored) == "range-floor"


def test_a_count_beside_the_number_without_shared_users_is_refused(tmp_path: Path) -> None:
    result = _result(tmp_path)
    doctored = copy.deepcopy(result)
    doctored["first_measure_repository"]["without_shared_m"] = 31
    assert _failure(doctored) == "without-shared-alone"


@pytest.mark.parametrize(
    ("where", "value"),
    [
        ("rho_bar", "1/3"),
        ("rho_bar", "0.036"),
        ("rho_bar", "+0.0356781"),
        ("rho_bar", 0.036),
    ],
)
def test_a_number_outside_its_registered_format_is_refused(
    tmp_path: Path, where: str, value: object
) -> None:
    result = _result(tmp_path)
    doctored = copy.deepcopy(result)
    doctored["measures"]["no_reasoning_share"]["repository"][where] = value
    assert _failure(doctored) == "value-format"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("positive_weight_share", "0.55"),
        ("positive_weight_share", 55),
        ("loo_min", "+0.023"),
        ("without_shared", "not yet"),
        ("above", -1),
        ("above", "18"),
    ],
)
def test_an_extra_number_outside_its_format_is_refused(
    tmp_path: Path, key: str, value: object
) -> None:
    result = _result(tmp_path)
    doctored = copy.deepcopy(result)
    doctored["first_measure_repository"][key] = value
    assert _failure(doctored) == "value-format"


def test_a_not_formed_first_measure_beside_a_printed_rho_is_refused(tmp_path: Path) -> None:
    result = _result(tmp_path)
    doctored = copy.deepcopy(result)
    doctored["first_measure_repository"] = {"not_formed": "not formed (9 repositories, 171 units)"}
    assert _failure(doctored) == "allowed-keys"


def test_a_printed_extra_beside_an_unformed_rho_is_refused(tmp_path: Path) -> None:
    result = _result(tmp_path)
    doctored = copy.deepcopy(result)
    doctored["measures"]["no_reasoning_share"]["repository"] = {
        "not_formed": "not formed (9 repositories, 171 units)"
    }
    assert _failure(doctored) == "rho-floor"


def test_a_broken_provenance_is_refused(tmp_path: Path) -> None:
    result = _result(tmp_path)
    doctored = copy.deepcopy(result)
    doctored["provenance"]["analyze_sha256"] = "short"
    assert _failure(doctored) == "value-format"

    doctored = copy.deepcopy(result)
    del doctored["provenance"]["record_commit"]
    assert _failure(doctored) == "allowed-keys"


def test_a_start_time_outside_its_registered_form_is_refused(tmp_path: Path) -> None:
    # Decision 6: the result file records the start time, UTC and whole seconds.
    result = _result(tmp_path)
    check_result.check(result)
    for value in ("2026-11-19T14:35:07.5+00:00", "2026-11-19 14:35:07+00:00", "later"):
        doctored = copy.deepcopy(result)
        doctored["provenance"]["start_time"] = value
        assert _failure(doctored) == "value-format"

    doctored = copy.deepcopy(result)
    del doctored["provenance"]["start_time"]
    assert _failure(doctored) == "allowed-keys"


def test_the_two_top_counts_are_checked_against_a_checks_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Decision 15 (finding 17): with a checks file, `sessions` and `repositories` must equal its
    # found counts.
    _signal, _outcome, out_dir = pipeline.run_both_stages(tmp_path)
    result_path = out_dir / "result_confirmation.json"
    checks_path = out_dir / "checks_confirmation.json"
    assert check_result.main(["--result", str(result_path), "--checks", str(checks_path)]) == 0
    _ = capsys.readouterr()

    result = pipeline.read_json(result_path)
    checks = pipeline.read_json(checks_path)
    doctored = copy.deepcopy(result)
    doctored["sessions"] = 422
    path = tmp_path / "doctored.json"
    _ = path.write_text(json.dumps(doctored), encoding="utf-8")
    assert check_result.main(["--result", str(path), "--checks", str(checks_path)]) == 4
    assert capsys.readouterr().err == "checks-mismatch\n"
    # Without the checks file the same result file passes: the cross-check is the new rule.
    assert check_result.main(["--result", str(path)]) == 0
    _ = capsys.readouterr()

    with pytest.raises(check_result.RuleFailed) as raised:
        check_result.check(result, {"checks": [{"name": "sessions", "found": 1}]})
    assert raised.value.rule == "checks-mismatch"
    check_result.check(result, checks)


def test_a_checks_file_with_a_duplicated_check_name_is_refused(tmp_path: Path) -> None:
    # Decision F (MINOR 4): a repeated name no longer wins by being last.
    _signal, _outcome, out_dir = pipeline.run_both_stages(tmp_path)
    result = pipeline.read_json(out_dir / "result_confirmation.json")
    checks = pipeline.read_json(out_dir / "checks_confirmation.json")
    check_result.check(result, checks)

    doctored = copy.deepcopy(checks)
    doctored["checks"].append({"name": "sessions", "found": 1, "registered": 423, "verdict": "x"})
    with pytest.raises(check_result.RuleFailed) as raised:
        check_result.check(result, doctored)
    assert raised.value.rule == "checks-mismatch"


def test_a_checks_file_with_a_month_outside_the_six_is_accepted(tmp_path: Path) -> None:
    # MAJOR 2 of review 3: stage 1 writes such an entry itself, so the file `render` accepts is
    # the file this module accepts where it reads one. The two top counts are still cross-checked.
    _signal, _outcome, out_dir = pipeline.run_both_stages(tmp_path)
    result = pipeline.read_json(out_dir / "result_confirmation.json")
    checks = pipeline.read_json(out_dir / "checks_confirmation.json")

    with_seventh = copy.deepcopy(checks)
    with_seventh["checks"].append(
        {"name": "month_2026-03", "found": 1, "registered": 0, "verdict": "different"}
    )
    with_seventh["all_same"] = False
    check_result.check(result, with_seventh)

    path = tmp_path / "checks-seventh.json"
    _ = path.write_text(json.dumps(with_seventh), encoding="utf-8")
    assert (
        check_result.main(
            ["--result", str(out_dir / "result_confirmation.json"), "--checks", str(path)]
        )
        == 0
    )


def test_an_unreadable_file_exits_four(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "broken.json"
    _ = path.write_text("{not json", encoding="utf-8")
    assert check_result.main(["--result", str(path)]) == 4
    assert capsys.readouterr().err == "unreadable\n"


def test_the_failed_rule_is_the_only_thing_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = _result(tmp_path)
    doctored = copy.deepcopy(result)
    doctored[f"{tables.CANARY}-key"] = f"{tables.CANARY}-value"
    path = tmp_path / "leaky.json"
    _ = path.write_text(json.dumps(doctored), encoding="utf-8")
    _ = capsys.readouterr()  # the check counts stage 1 printed
    assert check_result.main(["--result", str(path)]) == 4
    captured = capsys.readouterr()
    assert captured.err == "allowed-keys\n"
    assert captured.out == ""
    assert tables.CANARY not in captured.err
