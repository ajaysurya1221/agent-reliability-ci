"""The signal-side counts: hand-computed tables, the separation, and its silence.

Every count below is computed by hand from the small table this file writes. The table is
synthetic and every path, key and model name in it carries a token that no output may hold.
"""

from __future__ import annotations

import ast
import json
import random
from pathlib import Path
from typing import Any

import pytest

from bench.logsignals import analyze, signal_counts
from tests.unit.logsignals import reachability, tables

FORBIDDEN: tuple[str, ...] = ("describe", "aggregate", "rho_of_block", "read_outcome")

# One repository of the first half with three sessions, one with a single session, and one
# repository of the second half with two sessions.
ROWS: tuple[str, ...] = (
    # path, repo, half, month, user, model, d, first_time, zero, num, den
    "transcripts0/CANARY-1.jsonl\tc0de000000000001\tconfirmation\t2026-04\t"
    "c0de000000000a01\tCANARY-model-1\t20\t2026-05-03T14:07:09+00:00\t0\t10\t1",
    "transcripts0/CANARY-2.jsonl\tc0de000000000001\tconfirmation\t2026-04\t"
    "\tCANARY-model-1\t21\t2026-05-03T14:07:10+00:00\t5\t10\t1",
    "transcripts0/CANARY-3.jsonl\tc0de000000000001\tconfirmation\t2026-05\t"
    "c0de000000000a01\tCANARY-model-2\t22\t2026-05-03T14:07:11+00:00\t5\t11\t1",
    "transcripts0/CANARY-4.jsonl\tc0de000000000002\tconfirmation\t\t"
    "\tunknown\t20\t2026-05-03T14:07:12+00:00\t3\t12\t1",
    "transcripts0/CANARY-5.jsonl\tc0de000000000003\tdiscovery\t2026-06\t"
    "c0de000000000a01\tCANARY-model-1\t20\t2026-05-03T14:07:13+00:00\t0\t10\t1",
    "transcripts0/CANARY-6.jsonl\tc0de000000000003\tdiscovery\t2026-06\t"
    "c0de000000000a02\tCANARY-model-2\t20\t2026-05-03T14:07:14+00:00\t1\t10\t1",
)


def _write(tmp_path: Path, rows: tuple[str, ...] = ROWS) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    signal = tmp_path / "signal.tsv"
    _ = signal.write_text(
        tables.SIGNAL_HEADER + "\n" + "".join(row + "\n" for row in rows), encoding="utf-8"
    )
    return signal


def _run(signal: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, Any, str]:
    code = signal_counts.main(["--signal", str(signal)])
    captured = capsys.readouterr()
    printed: Any = json.loads(captured.out) if captured.out else None
    return code, printed, captured.err


# --- the counts of the hand table ---------------------------------------------


def test_the_registered_signal_side_of_the_hand_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, printed, err = _run(_write(tmp_path), capsys)
    assert code == 3
    assert err == ""
    side = printed["confirmation"]["registered_signal_side"]
    assert side["all_same"] is False
    assert set(side["checks"]) == set(analyze.SIGNAL_SIDE_CHECKS)
    assert side["checks"]["sessions"] == {"found": 4, "registered": 423, "verdict": "different"}
    assert side["checks"]["repositories"] == {"found": 2, "registered": 33, "verdict": "different"}
    assert side["checks"]["first_measure_exactly_0"]["found"] == 1
    assert side["checks"]["month_2026-04"]["found"] == 2
    assert side["checks"]["month_2026-05"]["found"] == 1
    assert side["checks"]["month_2026-09"]["found"] == 0
    assert printed["discovery"]["registered_signal_side"]["checks"]["sessions"]["found"] == 2


def test_the_labels_and_the_names_of_the_hand_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _code, printed, _err = _run(_write(tmp_path), capsys)
    first = printed["confirmation"]
    assert first["month_unknown"] == 1
    assert first["model_unknown"] == 1
    # One repository shows two names, the other shows `unknown` alone, which counts as a name.
    assert first["model_names_per_repository"] == {"one": 1, "two": 1, "three_or_more": 0}
    assert printed["discovery"]["model_names_per_repository"] == {
        "one": 0,
        "two": 1,
        "three_or_more": 0,
    }


def test_the_user_ids_of_the_hand_table(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _code, printed, _err = _run(_write(tmp_path), capsys)
    assert printed["confirmation"]["user_ids"] == {
        "sessions_with_user_id": 2,
        "distinct_user_ids": 1,
        "shared_user_ids": 1,
    }
    assert printed["discovery"]["user_ids"] == {
        "sessions_with_user_id": 2,
        "distinct_user_ids": 2,
        "shared_user_ids": 1,
    }


def test_the_potential_weight_of_the_hand_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _code, printed, _err = _run(_write(tmp_path), capsys)
    weight = printed["confirmation"]["potential_weight"]
    # One repository block of 3 sessions carries 2 units; the single-session repository none.
    assert weight["repository"]["blocks_of_two_or_more"] == {"weight": 2, "repositories": 1}
    assert weight["repository"]["signal_not_constant"]["no_reasoning_share"] == {
        "weight": 2,
        "repositories": 1,
    }
    assert weight["repository"]["signal_not_constant"]["reasoning_tokens"] == {
        "weight": 2,
        "repositories": 1,
    }
    # One repository-and-month block of 2 sessions; its second measure is constant (10 and 10).
    assert weight["repository_month"]["blocks_of_two_or_more"] == {"weight": 1, "repositories": 1}
    assert weight["repository_month"]["signal_not_constant"]["no_reasoning_share"] == {
        "weight": 1,
        "repositories": 1,
    }
    assert weight["repository_month"]["signal_not_constant"]["reasoning_tokens"] == {
        "weight": 0,
        "repositories": 0,
    }
    # The thirds cut the two sessions of one repository-and-model group apart, so no block of
    # the third definition holds two sessions.
    assert weight["repository_model_length"]["blocks_of_two_or_more"] == {
        "weight": 0,
        "repositories": 0,
    }
    for measure in analyze.MEASURES:
        assert weight["repository_model_length"]["signal_not_constant"][measure] == {
            "weight": 0,
            "repositories": 0,
        }


def test_the_thirds_are_the_ones_analyze_cuts(tmp_path: Path) -> None:
    # The block keys and the thirds come from `analyze.block_keys` and from nowhere else.
    rows = [row for row in analyze.read_signal(_write(tmp_path)) if row.half == "confirmation"]
    keys = analyze.block_keys(rows, "repository_model_length")
    assert {key[2] for key in keys.values()} == {"middle", "high"}
    sizes: dict[tuple[str, ...], int] = {}
    for key in keys.values():
        sizes[key] = sizes.get(key, 0) + 1
    assert max(sizes.values()) == 1
    assert signal_counts.potential_weight(rows)["repository_model_length"] == {
        "blocks_of_two_or_more": {"weight": 0, "repositories": 0},
        "signal_not_constant": {
            measure: {"weight": 0, "repositories": 0} for measure in analyze.MEASURES
        },
    }


def test_a_repository_of_three_model_names_is_counted_as_such(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = (*ROWS[:3], ROWS[3].replace("\tc0de000000000002\t", "\tc0de000000000001\t"), *ROWS[4:])
    _code, printed, _err = _run(_write(tmp_path, rows), capsys)
    assert printed["confirmation"]["model_names_per_repository"] == {
        "one": 0,
        "two": 0,
        "three_or_more": 1,
    }


# --- the registered halves ----------------------------------------------------


def test_both_registered_halves_exit_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    signal, _outcome = tables.write_tables(tmp_path / "tables", tables.both_halves())
    code, printed, err = _run(signal, capsys)
    assert code == 0
    assert err == ""
    for half in analyze.HALVES:
        side = printed[half]["registered_signal_side"]
        assert side["all_same"] is True
        assert {entry["verdict"] for entry in side["checks"].values()} == {"same"}


def test_a_half_one_session_short_exits_three(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    signal, _outcome = tables.write_tables(
        tmp_path / "tables", tables.both_halves_short("discovery")
    )
    code, printed, _err = _run(signal, capsys)
    assert code == 3
    assert printed["confirmation"]["registered_signal_side"]["all_same"] is True
    second = printed["discovery"]["registered_signal_side"]
    assert second["all_same"] is False
    assert second["checks"]["sessions"] == {"found": 431, "registered": 432, "verdict": "different"}


def test_a_month_outside_the_six_is_a_difference_of_its_own(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = (ROWS[0].replace("\t2026-04\t", "\t2026-03\t"), *ROWS[1:])
    _code, printed, _err = _run(_write(tmp_path, rows), capsys)
    checks = printed["confirmation"]["registered_signal_side"]["checks"]
    assert checks["month_2026-03"] == {"found": 1, "registered": 0, "verdict": "different"}


# --- hostile tables, silence and order ----------------------------------------


@pytest.mark.parametrize(
    "rows",
    [
        (ROWS[0] + "\textra",),
        (ROWS[0].replace("\t10\t1", "\t\t"),),
        (ROWS[0].replace("\tconfirmation\t", "\tneither\t"),),
        (ROWS[0], ROWS[0]),
        (ROWS[0].replace("\t20\t", "\t19\t"),),
    ],
)
def test_a_hostile_table_prints_one_word_and_no_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], rows: tuple[str, ...]
) -> None:
    code, printed, err = _run(_write(tmp_path, rows), capsys)
    assert code == 2
    assert printed is None
    assert err == "table-invalid\n"


def test_an_absent_table_prints_one_word(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, printed, err = _run(tmp_path / "absent.tsv", capsys)
    assert code == 2
    assert printed is None
    assert err == "table-invalid\n"


def test_no_token_reaches_the_output_streams(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sessions = tables.both_halves()
    signal, _outcome = tables.write_tables(tmp_path / "tables", sessions)
    code = signal_counts.main(["--signal", str(signal)])
    captured = capsys.readouterr()
    assert code == 0
    tokens = {tables.CANARY, "transcripts0"}
    for session in sessions:
        tokens.update({session.path, session.repo_key, session.model})
        if session.user_key:
            tokens.add(session.user_key)
    assert len(tokens) > 100
    for text in (captured.out, captured.err):
        for token in tokens:
            assert token not in text
    # The private table does hold them; that is its purpose.
    assert tables.CANARY in signal.read_text(encoding="utf-8")


def test_only_integers_and_fixed_words_are_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _code, printed, _err = _run(_write(tmp_path), capsys)

    def _leaves(value: Any) -> list[Any]:
        if isinstance(value, dict):
            found: list[Any] = []
            for item in value.values():
                found.extend(_leaves(item))
            return found
        return [value]

    for leaf in _leaves(printed):
        assert isinstance(leaf, bool | int) or leaf in ("same", "different")


def test_the_row_order_changes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    shuffled = list(ROWS)
    random.Random(20261119).shuffle(shuffled)
    assert shuffled != list(ROWS)
    _code, plain, _err = _run(_write(tmp_path / "plain", ROWS), capsys)
    _code, mixed, _err = _run(_write(tmp_path / "mixed", tuple(shuffled)), capsys)
    assert plain == mixed


def test_bad_arguments_print_one_word(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert signal_counts.main([]) == 2
    assert capsys.readouterr().err == "arguments-invalid\n"


# --- the separation -----------------------------------------------------------


def test_the_signal_counts_cannot_reach_the_pairing_code() -> None:
    file = signal_counts.__file__
    reached = reachability.reachable(file, ["main", "counts", "counts_of_half"])
    assert "read_signal" in reached
    assert "block_keys" in reached
    for name in FORBIDDEN:
        assert name not in reached
    # MINOR 9 of review 3: the walk follows the calls into `analyze` by name, so the bodies of
    # `read_signal`, `block_keys` and `signal_side_counts` are inside it: a forbidden call added
    # inside one of their helpers fails this test. The names below are theirs, not this module's.
    own = reachability.functions_of(file)
    for inside_analyze in ("_body_lines", "_read_text", "_parse_time", "_third_label"):
        assert inside_analyze not in own
        assert inside_analyze in reached
    # It names none of them anywhere, its imports included.
    source = Path(file).read_text(encoding="utf-8")
    named: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name):
            named.add(node.id)
        elif isinstance(node, ast.Attribute):
            named.add(node.attr)
        elif isinstance(node, ast.ImportFrom | ast.Import):
            named.update(alias.name for alias in node.names)
    assert named.isdisjoint(FORBIDDEN)
    for word in ("outcome.tsv", "agent_percentage", "pyarrow"):
        assert word not in source
    # The same walk does reach the pairing code from stage 2 of `analyze`, so it is not vacuous.
    assert "describe" in reachability.reachable(analyze.__file__, ["_run_stage_two"])
