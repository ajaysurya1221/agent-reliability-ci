"""Tests for the cohort receipt builder's text helpers and its persisted-store fallback.

.venv/bin/pytest plan/exec/scripts/test_cohort_receipts.py -q -p no:cacheprovider
"""

from __future__ import annotations

import json
from pathlib import Path

import cohort_receipts as cr
import pytest


def _trial(wall: float) -> str:
    return json.dumps({"trial_id": "t", "usage": {"wall_seconds": wall}})


# --- scrub -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        (None, ""),
        ("", ""),
        ("no paths here", "no paths here"),
        (cr.REPO + "README.md", "README.md"),
        ("/var/folders/2k/b4x5/T/tmp.7Qzi7C36lY/python_agent/runs", "<tmp>/python_agent/runs"),
        ("/private/var/folders/2k/b4x5/T/tmp.7Qzi7C36lY/demo.log", "<tmp>/demo.log"),
        ("log at /tmp/ttfv-a.XYZ123/demo.log, done", "log at <tmp>/demo.log, done"),
        ("[/tmp/abcdef]", "[<tmp>]"),
        ("('/tmp/abcdef')", "('<tmp>')"),
        ("cd /var/folders/.../T/x && ls", "cd <tmp> && ls"),
        ("venv tmp.AbCdEf12 made", "venv <tmp> made"),
        ("store arci-demo-ab12cd34", "store <tmp>"),
        ("uvcache.abcdef and ttfv-b.Qw3rTy", "<tmp> and <tmp>"),
        ("tmp.abc stays", "tmp.abc stays"),
    ],
)
def test_scrub(raw: str | None, want: str) -> None:
    assert cr.scrub(raw) == want


# --- sentence --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        (None, ""),
        ("", ""),
        ("   ", ""),
        ("ok", "ok."),
        ("ok.", "ok."),
        ("ok  ", "ok."),
        ("ok..", "ok.."),
        ('said "stop"', 'said "stop".'),
        ('said "stop."', 'said "stop."'),
        ('see (it said "stop.")', 'see (it said "stop.")'),
        ('{"notes": "done."}', '{"notes": "done."}'),
        ("it said 'stop.'", "it said 'stop.'"),
        ("(an aside.)", "(an aside.)"),
        ("why?", "why?"),
        ("wow!", "wow!"),
        ("exit ${PIPESTATUS[0]}", "exit ${PIPESTATUS[0]}."),
        ("log in /tmp/abcdef/x", "log in <tmp>/x."),
    ],
)
def test_sentence(raw: str | None, want: str) -> None:
    assert cr.sentence(raw) == want


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("ok", "ok."),
        ("ok.", "ok."),
        ('said "stop."', 'said "stop.".'),
        ('{"notes": "done."}', '{"notes": "done."}.'),
        ("why?", "why?."),
        ("", ""),
    ],
)
def test_sentence_legacy_keeps_v080_punctuation(raw: str, want: str) -> None:
    assert cr.sentence(raw, legacy=True) == want


# --- verdict_of ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "want"),
    [
        (None, "ERROR"),
        ("", "ERROR"),
        ("no verdict printed", "ERROR"),
        ("VERDICT: PASS (exit 0)", "PASS"),
        ("VERDICT: BLOCK (exit 1)", "BLOCK"),
        ("VERDICT: INCONCLUSIVE (exit 2)", "INCONCLUSIVE"),
        ("VERDICT: ERROR (exit 3)", "ERROR"),
        ("BLOCK for agent B; agent A got PASS", "BLOCK"),
        ("PASSING tests, then VERDICT: INCONCLUSIVE", "INCONCLUSIVE"),
        ("verdict: pass", "ERROR"),
    ],
)
def test_verdict_of(line: str | None, want: str) -> None:
    assert cr.verdict_of(line) == want


# --- clean_failure ---------------------------------------------------------------------------


def test_clean_failure_keeps_iso_at() -> None:
    f = {"at": "2026-10-13T17:37:02Z", "milestone": "run", "what": "ERROR: x"}
    assert cr.clean_failure(f) == f


def test_clean_failure_moves_timestamp_remark_into_what() -> None:
    got = cr.clean_failure(
        {"at": "2026-10-13T17:37:02Z (approx.)", "milestone": "run", "what": "x"}
    )
    assert got == {"at": "2026-10-13T17:37:02Z", "milestone": "run", "what": "[at: approx.] x"}


def test_clean_failure_non_iso_at_becomes_empty() -> None:
    got = cr.clean_failure({"at": "before readme_opened", "milestone": "install", "what": "denied"})
    assert got == {"at": "", "milestone": "install", "what": "[at: before readme_opened] denied"}


def test_clean_failure_missing_keys_and_scrubbed_paths() -> None:
    assert cr.clean_failure({}) == {"at": "", "milestone": "", "what": ""}
    got = cr.clean_failure({"at": "", "milestone": "store", "what": "ls /tmp/abcdef/runs failed"})
    assert got == {"at": "", "milestone": "store", "what": "ls <tmp>/runs failed"}


# --- agent_execution and --persist -----------------------------------------------------------


def _store(tmp_path: Path, walls: list[float]) -> Path:
    store = tmp_path / "store"
    store.mkdir()
    lines = [_trial(w) for w in walls]
    (store / "trials.jsonl").write_text("\n".join(lines) + "\n\n", encoding="utf-8")
    return store


def test_agent_execution_from_live_store(tmp_path: Path) -> None:
    store = _store(tmp_path, [0.1, 0.2, 0.30049])
    assert cr.agent_execution({"store_dir": str(store)}) == 0.6


def test_agent_execution_gone_store_without_persisted_is_none(tmp_path: Path) -> None:
    assert cr.agent_execution({"store_dir": str(tmp_path / "gone")}) is None
    assert cr.agent_execution({}) is None


def test_agent_execution_reads_persisted_lines_when_store_gone(tmp_path: Path) -> None:
    b = {
        "store_dir": str(tmp_path / "gone"),
        cr.PERSISTED: {"agent_execution": 0.6, "trials_jsonl": [_trial(0.1), "", _trial(0.5)]},
    }
    assert cr.agent_execution(b) == 0.6
    assert cr.agent_execution({"store_dir": "", cr.PERSISTED: {"agent_execution": 1.25}}) == 1.25


def test_agent_execution_refuses_disagreeing_values(tmp_path: Path) -> None:
    bad_sum = {cr.PERSISTED: {"agent_execution": 9.0, "trials_jsonl": [_trial(0.1)]}}
    with pytest.raises(ValueError, match="persisted agent_execution"):
        cr.agent_execution(bad_sum)
    store = _store(tmp_path, [1.0])
    live_vs_persisted = {"store_dir": str(store), cr.PERSISTED: {"trials_jsonl": [_trial(2.0)]}}
    with pytest.raises(ValueError, match="live"):
        cr.agent_execution(live_vs_persisted)


def test_persist_round_trip_survives_store_removal(tmp_path: Path) -> None:
    store = _store(tmp_path, [1.5, 2.25])
    result = {
        "results": [
            {"reader": {"id": "r1"}, "out": {"track_b": {"store_dir": str(store)}}},
            {"reader": {"id": "r2"}, "out": {"track_b": {"store_dir": str(tmp_path / "gone")}}},
            {"reader": {"id": "r3"}, "out": None},
        ],
        "scores": [],
    }
    src = tmp_path / "result.json"
    src.write_text(json.dumps(result), encoding="utf-8")
    original = src.read_bytes()
    out = tmp_path / "result.persisted.json"
    cr.main([str(src), "--persist", str(out)])
    assert src.read_bytes() == original
    data = json.loads(out.read_text(encoding="utf-8"))
    b1 = data["results"][0]["out"]["track_b"]
    assert b1[cr.PERSISTED]["agent_execution"] == 3.75
    assert b1[cr.PERSISTED]["trials_jsonl"] == [_trial(1.5), _trial(2.25), ""]
    assert cr.PERSISTED not in data["results"][1]["out"]["track_b"]
    (store / "trials.jsonl").unlink()
    store.rmdir()
    assert cr.agent_execution(b1) == 3.75
    # Persisting again after the store is gone keeps what was persisted.
    again = tmp_path / "again.json"
    cr.main([str(out), "--persist", str(again)])
    assert json.loads(again.read_text(encoding="utf-8"))["results"][0] == data["results"][0]


def test_persist_refuses_to_overwrite_its_input(tmp_path: Path) -> None:
    src = tmp_path / "result.json"
    src.write_text('{"results": []}', encoding="utf-8")
    with pytest.raises(SystemExit):
        cr.main([str(src), "--persist", str(src)])


# --- build: overwrite refusal and all-or-nothing writes ---------------------------------------

TEMPLATE = Path(__file__).resolve().parents[3] / "docs" / "measurement" / "receipt.template.json"
QUESTIONS = (
    "q1_what_is_it",
    "q2_who_for",
    "q3_pass_means",
    "q4_does_not_do",
    "q5_first_three_commands",
)


def _reader(rid: str, track_b: dict[str, object] | None = None) -> dict[str, object]:
    answers = {k: f"{k} answer" for k in QUESTIONS}
    answers |= {"interpretation_demo_block": "blocks", "interpretation_own_run": "own"}
    return {
        "reader": {"id": rid, "persona": "tester", "model": "sonnet"},
        "out": {"track_a": {}, "track_b": track_b or {}, "answers": answers},
    }


def _build_setup(tmp_path: Path, readers: list[dict[str, object]]) -> tuple[Path, Path]:
    (tmp_path / "receipt.template.json").write_bytes(TEMPLATE.read_bytes())
    out_dir = tmp_path / "receipts"
    out_dir.mkdir()
    result = tmp_path / "result.json"
    result.write_text(json.dumps({"results": readers, "scores": []}), encoding="utf-8")
    return result, out_dir


def _snapshot(out_dir: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(out_dir.iterdir())}


NAMES = [f"2026-10-13-ai-r{i}-{t}.json" for i in (1, 2) for t in ("demo", "own-agent")]


def test_build_writes_every_receipt(tmp_path: Path) -> None:
    result, out_dir = _build_setup(tmp_path, [_reader("r1"), _reader("r2")])
    cr.main([str(result), str(out_dir), "abc1234"])
    snap = _snapshot(out_dir)
    assert sorted(snap) == sorted(NAMES)  # no staging directory left behind
    rec = json.loads(snap["2026-10-13-ai-r1-demo.json"])
    assert rec["reader"]["handle"] == "ai-r1"
    assert rec["package"]["readme_url"].endswith("/blob/abc1234/README.md")


def test_build_refuses_to_overwrite_and_names_the_files(tmp_path: Path) -> None:
    result, out_dir = _build_setup(tmp_path, [_reader("r1"), _reader("r2")])
    (out_dir / NAMES[1]).write_text("committed\n", encoding="utf-8")
    (out_dir / NAMES[3]).write_text("committed\n", encoding="utf-8")
    before = _snapshot(out_dir)
    with pytest.raises(SystemExit) as exc:
        cr.main([str(result), str(out_dir), "abc1234"])
    msg = str(exc.value.code)
    assert "--overwrite" in msg
    assert NAMES[1] in msg
    assert NAMES[3] in msg
    assert NAMES[0] not in msg
    assert _snapshot(out_dir) == before  # nothing written, not even the new files


def test_build_overwrite_replaces_existing_receipts(tmp_path: Path) -> None:
    result, out_dir = _build_setup(tmp_path, [_reader("r1"), _reader("r2")])
    cr.main([str(result), str(out_dir), "abc1234"])
    fresh = _snapshot(out_dir)
    (out_dir / NAMES[0]).write_text("stale\n", encoding="utf-8")
    cr.main([str(result), str(out_dir), "abc1234", "--overwrite"])
    assert _snapshot(out_dir) == fresh


def test_build_validation_error_leaves_receipts_dir_untouched(tmp_path: Path) -> None:
    bad: dict[str, object] = {cr.PERSISTED: {"agent_execution": 9.0, "trials_jsonl": [_trial(0.1)]}}
    result, out_dir = _build_setup(tmp_path, [_reader("r1"), _reader("r2", bad)])
    (out_dir / NAMES[0]).write_text("committed\n", encoding="utf-8")
    before = _snapshot(out_dir)
    with pytest.raises(ValueError, match="persisted agent_execution"):
        cr.main([str(result), str(out_dir), "abc1234", "--overwrite"])
    assert _snapshot(out_dir) == before  # r1's receipts, built first, were not written


def test_build_refuses_two_readers_with_one_id(tmp_path: Path) -> None:
    result, out_dir = _build_setup(tmp_path, [_reader("r1"), _reader("r1")])
    with pytest.raises(ValueError, match="two readers"):
        cr.main([str(result), str(out_dir), "abc1234"])
    assert _snapshot(out_dir) == {}


def test_build_staging_write_failure_leaves_receipts_dir_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, out_dir = _build_setup(tmp_path, [_reader("r1"), _reader("r2")])
    (out_dir / NAMES[0]).write_text("committed\n", encoding="utf-8")
    before = _snapshot(out_dir)
    real_write_text = Path.write_text
    calls: list[str] = []

    def failing_write_text(
        self: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        calls.append(self.name)
        if len(calls) == 3:
            raise OSError(28, "No space left on device")
        return real_write_text(self, data, encoding, errors, newline)

    monkeypatch.setattr(Path, "write_text", failing_write_text)
    with pytest.raises(OSError, match="No space"):
        cr.main([str(result), str(out_dir), "abc1234", "--overwrite"])
    monkeypatch.undo()
    assert _snapshot(out_dir) == before  # staging removed, nothing moved into place


def test_build_needs_an_existing_receipts_dir(tmp_path: Path) -> None:
    result, _ = _build_setup(tmp_path, [_reader("r1")])
    with pytest.raises(SystemExit, match="does not exist"):
        cr.main([str(result), str(tmp_path / "missing"), "abc1234"])
