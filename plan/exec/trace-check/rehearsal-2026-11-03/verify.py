"""Read-only reproduction of the three stored rehearsal comparisons."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    evidence = Path(__file__).resolve().parent
    repo = evidence.parents[3]
    hashes = json.loads((evidence / "source-hashes-before.json").read_text())

    def verify_sources() -> None:
        for relative, expected in hashes.items():
            actual = hashlib.sha256((repo / relative).read_bytes()).hexdigest()
            if actual != expected:
                raise AssertionError(f"Source changed: {relative}")

    verify_sources()
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    # An existing or absent summary path must not be written by the comparator.
    env.pop("GITHUB_STEP_SUMMARY", None)
    cases = json.loads((evidence / "cases.json").read_text())
    for case, expected_exit in zip(cases, (1, 1, 0), strict=True):
        completed = subprocess.run(
            [
                sys.executable,
                "-P",
                "-m",
                "arci",
                "trace-check",
                str(repo / case["base_run"]),
                case["base_trial"],
                str(repo / case["candidate_run"]),
                case["candidate_trial"],
                "--format",
                "json",
            ],
            cwd=evidence,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert completed.returncode == expected_exit, completed.stderr
        assert not completed.stderr
        expected_text = (evidence / "results" / f"{case['case']}.json").read_text()
        expected = json.loads(expected_text)
        assert completed.stdout == expected_text, case["case"]
        print(f"{case['case']}: {expected['status']}/{expected_exit}, receipt matches")
    verify_sources()
    print(f"All {len(hashes)} source-file hashes unchanged")


if __name__ == "__main__":
    main()
