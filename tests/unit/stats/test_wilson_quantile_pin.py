"""The 95% Wilson quantile is pinned so stored decisions re-derive on every platform.

CPython's C accelerator for ``NormalDist.inv_cdf`` returns 1.9599639845400534 for 0.975 on
some arm64 builds; the pure-Python fallback (and Linux) returns 1.9599639845400536. Decision
files carry Wilson display bounds under a seal, so a one-ulp difference changes their bytes.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import statistics
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from arci.stats import wilson

PINNED_Z_95 = 1.9599639845400536
NATIVE_ARM64_Z_95 = 1.9599639845400534

REPO_ROOT = Path(__file__).resolve().parents[3]
JEV_RESULTS = REPO_ROOT / "docs" / "results" / "jev"
JEV_DECISIONS = sorted(JEV_RESULTS.rglob("decision.json"))
EXPECTED_JEV_DECISIONS = 12
EXPECTED_INVALID_ATTEMPT_DECISIONS = 5
SCRUBBED_ENV = ("TYPESAFE_API_KEY", "jev_key", "GITHUB_STEP_SUMMARY")

COUNTS = ((0, 1), (1, 1), (0, 200), (130, 200), (200, 200), (38, 50), (50, 50), (7, 13))


def _wilson_with(z: float, successes: int, n: int) -> tuple[float, float]:
    rate = successes / n
    z_squared = z * z
    denominator = 1.0 + z_squared / n
    centre = (rate + z_squared / (2.0 * n)) / denominator
    radius = z * math.sqrt(rate * (1.0 - rate) / n + z_squared / (4.0 * n * n)) / denominator
    return centre - radius, centre + radius


@pytest.mark.parametrize(("successes", "n"), COUNTS)
def test_wilson_95_uses_the_pinned_quantile_exactly(successes: int, n: int) -> None:
    assert wilson(successes, n, 0.95) == _wilson_with(PINNED_Z_95, successes, n)
    assert wilson(successes, n) == _wilson_with(PINNED_Z_95, successes, n)


def test_wilson_95_ignores_the_platform_quantile(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = {counts: wilson(*counts, 0.95) for counts in COUNTS}
    calls: list[float] = []

    def native_inv_cdf(self: statistics.NormalDist, p: float) -> float:
        del self
        calls.append(p)
        return NATIVE_ARM64_Z_95

    monkeypatch.setattr(statistics.NormalDist, "inv_cdf", native_inv_cdf)

    assert {counts: wilson(*counts, 0.95) for counts in COUNTS} == expected
    assert calls == []

    assert wilson(5, 10, 0.9) == _wilson_with(NATIVE_ARM64_Z_95, 5, 10)
    assert calls == [(1.0 + 0.9) / 2.0]


def test_jev_decision_inventory_is_complete() -> None:
    invalid = [path for path in JEV_DECISIONS if "attempt-1-invalid" in path.parts]
    assert len(JEV_DECISIONS) == EXPECTED_JEV_DECISIONS
    assert len(invalid) == EXPECTED_INVALID_ATTEMPT_DECISIONS


@pytest.mark.parametrize(
    "committed",
    JEV_DECISIONS,
    ids=[path.parent.relative_to(JEV_RESULTS).as_posix() for path in JEV_DECISIONS],
)
def test_committed_jev_decision_rederives_byte_for_byte(committed: Path, tmp_path: Path) -> None:
    store = committed.parent
    for name in ("manifest.json", "trials.jsonl"):
        shutil.copyfile(store / name, tmp_path / name)
    env = {key: value for key, value in os.environ.items() if key not in SCRUBBED_ENV}
    expected_exit = cast(dict[str, object], json.loads(committed.read_bytes()))["exit_code"]

    completed = subprocess.run(
        [sys.executable, "-m", "arci.cli", "gate", str(tmp_path)],
        capture_output=True,
        env=env,
        timeout=30,
        check=False,
    )

    assert completed.returncode == expected_exit
    assert (tmp_path / "decision.json").read_bytes() == committed.read_bytes()
