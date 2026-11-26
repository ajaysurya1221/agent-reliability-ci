"""Board-0: exact projections of the registered rule from the released `arci plan` (2.4.1).

Study code, standard library only. No model, no server, no network.

    PYTHONDONTWRITEBYTECODE=1 python3 -B project.py /path/to/python-with-arci-2.4.1

Writes plan-16xR.yaml descriptors (16 tasks, R rounds), runs `arci plan` on each with the two
arms of a pair taken as independent (agreement = B*C + (1-B)*(1-C)), and writes
registered-rows.json. Projections under stated assumptions (the same joint law in every task and
round, no errored pair, no hard violation), not measurements.
"""

from __future__ import annotations

import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROUNDS = (20, 26)
GRID = (
    (100, 100), (95, 95), (90, 90), (75, 75), (60, 60), (50, 50),
    (95, 85), (90, 80), (90, 70), (90, 60), (90, 40), (75, 55), (75, 45), (60, 30),
    (100, 25), (100, 0),
)  # fmt: skip


def descriptor(rounds: int) -> Path:
    document = {
        "suite_id": f"board0-plan-16x{rounds}",
        "tasks": [{"id": f"t{i:02d}", "key_id": f"t{i:02d}"} for i in range(1, 17)],
        "oracle": "board0_plan_stub:passed",
        "baseline": {
            "label": "stock-sentence",
            "command": {"argv": ["/usr/bin/true", "{mcp_config}", "{task_file}"]},
        },
        "candidate": {
            "label": "empty-as-given",
            "command": {"argv": ["/usr/bin/true", "{mcp_config}", "{task_file}"]},
        },
        "mcp_server": {
            "name": "srv",
            "argv": ["/usr/bin/true"],
            "env": {},
            "snapshot": "board0_plan_stub:snapshot",
        },
        "conditions": [{"id": "clean"}],
        "rule": {
            "alpha": "1/20",
            "delta": "1/10",
            "stakes": ["1/4", "1/2"],
            "max_rounds": rounds,
            "max_errored_pairs": 4,
            "scenario_seeds": "per_round",
        },
        "budgets": {
            "max_tool_calls": 12,
            "max_model_steps": 12,
            "max_seconds": 120,
            "grader_seconds": 20,
        },
    }
    path = HERE / f"plan-16x{rounds}.yaml"
    path.write_text(json.dumps(document, indent=2) + "\n")
    return path


def main() -> None:
    python = sys.argv[1]
    rows: list[dict[str, object]] = []
    for rounds in ROUNDS:
        path = descriptor(rounds)
        print(f"16 tasks x {rounds} rounds: baseline/candidate  PASS  BLOCK  CANNOT TELL  pairs")
        for base, cand in GRID:
            b, c = Fraction(base, 100), Fraction(cand, 100)
            agreement = b * c + (1 - b) * (1 - c)
            done = subprocess.run(
                [
                    python, "-m", "arci", "plan", str(path),
                    "--baseline-rate", str(b), "--candidate-rate", str(c),
                    "--agreement", str(agreement), "--format", "json",
                ],
                capture_output=True, text=True, check=False, cwd=HERE,
            )  # fmt: skip
            if done.returncode != 0:
                raise SystemExit(f"arci plan failed {rounds} {base} {cand}: {done.stderr.strip()}")
            document = json.loads(done.stdout)
            projection = document["projection"]
            if projection is None:
                # The released planner declines to enumerate some laws at this size.
                projection = {"status": document["status"]}
            rows.append({"rounds": rounds, "baseline": base, "candidate": cand, **projection})
            print(f"  {base}/{cand}", json.dumps(projection)[:300])
    (HERE / "registered-rows.json").write_text(json.dumps(rows, indent=1) + "\n")


if __name__ == "__main__":
    main()
