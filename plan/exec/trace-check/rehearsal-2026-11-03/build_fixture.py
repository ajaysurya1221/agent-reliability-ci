"""Create one predeclared N=1 offline rehearsal; never overwrite an existing output."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from arci.demo.experiment import clean_manifest
from arci.schema import ArmSpec, Manifest


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python build_fixture.py NEW_OUTPUT_DIRECTORY")
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=False)
    data = clean_manifest().model_dump(exclude={"record_sha256"})
    data["experiment_id"] = "arci-trace-rehearsal-2026-11-03"
    data["candidate"] = ArmSpec(
        label="variant", agent="rehearsal_fixture:variant", candidate_id="rehearsal-candidate"
    )
    manifest = Manifest.create(**data)
    manifest_path = output / "input-manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n")
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("GITHUB_STEP_SUMMARY", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "arci",
            "run",
            str(manifest_path),
            "--out",
            str(output / "stores"),
            "--workers",
            "1",
        ],
        cwd=Path(__file__).resolve().parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    (output / "run.stdout.txt").write_text(completed.stdout)
    (output / "run.stderr.txt").write_text(completed.stderr)
    (output / "run.exit.txt").write_text(f"{completed.returncode}\n")
    print(f"Recorded run exit {completed.returncode}; retained at {output}")
    if completed.returncode != 2:
        raise SystemExit("Expected the predeclared N=1 experiment to remain INCONCLUSIVE")


if __name__ == "__main__":
    main()
