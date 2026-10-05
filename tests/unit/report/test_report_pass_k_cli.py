"""`arci report --pass-k` on committed stores: opt-in, read-only, default output unchanged.

`default_report_sha256.json` holds the SHA-256 of `arci report STORE --format md|junit` for every
committed store under `docs/results/`, recorded with the code before `--pass-k` existed. Without
the flag the report must stay byte-identical to those recordings.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from arci.cli import main
from arci.reliability import UNAVAILABLE_INVALID

RESULTS = Path(__file__).resolve().parents[3] / "docs" / "results"
RECORDED: dict[str, str] = json.loads(
    Path(__file__).with_name("default_report_sha256.json").read_text(encoding="utf-8")
)
VALID_STORE = "guardrail/2026-10-05/guardrail-live-c-ask-clean-50"
INVALID_STORE = "jev/2026-10-03/attempt-1-invalid/jev-live-b-low_confidence-200"
SECTION = "## Descriptive pass^k (not part of the verdict)"


def _report(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(["report", *argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_every_committed_store_is_recorded() -> None:
    stores = {p.parent.relative_to(RESULTS).as_posix() for p in RESULTS.rglob("manifest.json")}
    recorded = {key.split("|", 1)[0] for key in RECORDED}
    assert stores <= recorded
    assert {VALID_STORE, INVALID_STORE} <= recorded


@pytest.mark.parametrize("key", sorted(RECORDED))
def test_default_report_is_byte_identical(capsys: pytest.CaptureFixture[str], key: str) -> None:
    store, report_format = key.split("|", 1)
    code, out, err = _report(capsys, str(RESULTS / store), "--format", report_format)
    assert (code, err) == (0, "")
    assert hashlib.sha256(out.encode("utf-8")).hexdigest() == RECORDED[key]


def _snapshot(directory: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in sorted(directory.iterdir())}


def test_pass_k_is_read_only_and_only_adds_its_section(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    store = tmp_path / "store"
    shutil.copytree(RESULTS / VALID_STORE, store)
    before = _snapshot(store)
    assert "decision.json" in before

    code, default, _ = _report(capsys, str(store))
    assert code == 0
    code, with_pass_k, err = _report(capsys, str(store), "--pass-k", "1,2,4")
    assert (code, err) == (0, "")

    assert _snapshot(store) == before  # decision.json and the records are never touched
    lines = with_pass_k.splitlines()
    start = lines.index(SECTION)
    end = lines.index("## Candidate failure clusters")
    assert "| `clean` | baseline | Gating | 50 | 50 | 1.0000 | 1.0000 | 1.0000 |" in lines
    assert "| `clean` | candidate | Gating | 50 | 50 | 1.0000 | 1.0000 | 1.0000 |" in lines
    assert lines[-1] == default.splitlines()[-1] == "VERDICT: PASS (exit 0)"
    assert "\n".join(lines[:start] + lines[end:]) + "\n" == default


def test_pass_k_on_an_invalid_committed_store_is_unavailable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, out, err = _report(capsys, str(RESULTS / INVALID_STORE), "--pass-k", "1,2")
    assert (code, err) == (0, "")
    lines = out.splitlines()
    assert SECTION in lines
    assert f"Unavailable: {UNAVAILABLE_INVALID}." in lines
    assert lines[-1] == "VERDICT: ERROR (exit 3)"


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (("--pass-k", "1,2", "--format", "junit"), "--pass-k is reported in the md format only"),
        (("--pass-k", "0"), "positive integer"),
        (("--pass-k", "2,1"), "strictly increasing"),
        (("--pass-k", "1,x"), "--pass-k must be comma-separated integers"),
    ],
)
def test_bad_pass_k_requests_exit_three(
    capsys: pytest.CaptureFixture[str], extra: tuple[str, ...], message: str
) -> None:
    code, out, err = _report(capsys, str(RESULTS / VALID_STORE), *extra)
    assert code == 3
    assert out == ""
    assert message in err
