"""Export recorded suite outcomes: python -m bench.export_outcomes STORE OUT_DIR."""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import yaml

from arci.outcome_schema import OUTCOMES_SCHEMA_VERSION, OutcomeRule
from arci.schema import Outcome
from arci.suite_gate import decide_suite
from arci.suite_schedule import pair_round, suite_cells
from arci.suite_schema import SuiteDecision
from arci.suite_storage import load_suite_run


def export_outcomes(store: Path, out_dir: Path) -> tuple[Path, ...]:
    """Write a descriptive rule and both arms through the last evaluated round."""
    manifest, trials = load_suite_run(store)
    decision = SuiteDecision.model_validate_json(
        (store / "decision.json").read_text(encoding="utf-8")
    )
    if not decision.validate_seal() or decision != decide_suite(manifest, trials):
        raise ValueError("stored suite decision does not match its recorded trials")
    if not decision.history:
        raise ValueError("stored suite decision evaluated no complete rounds")
    last_round = decision.history[-1].round
    rule = OutcomeRule(
        schema_version=OUTCOMES_SCHEMA_VERSION,
        suite_id=manifest.suite_id,
        tasks=tuple(
            f"{task.task_id}/{condition.condition_id}" for task, condition in suite_cells(manifest)
        ),
        alpha=manifest.alpha,
        margin=manifest.delta,
        stakes=manifest.stakes,
        max_rounds=manifest.max_rounds,
        max_errored_pairs=manifest.max_errored_pairs,
        fixed_before_runs=False,
    )
    content: dict[str, str] = {}
    for arm in ("baseline", "candidate"):
        rows: list[tuple[int, str, str]] = []
        for trial in trials:
            round_number = pair_round(trial.pair_id)
            if trial.arm != arm or round_number > last_round:
                continue
            outcome = (
                "pass"
                if trial.outcome is Outcome.PASS
                else "error"
                if trial.outcome is Outcome.ERROR
                else "fail"
            )
            rows.append((round_number, f"{trial.task_id}/{trial.condition_id}", outcome))
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("task_id", "outcome", "round"))
        for round_number, task_id, outcome in sorted(rows):
            writer.writerow((task_id, outcome, round_number))
        content[f"{arm}.csv"] = stream.getvalue()
    content["rule.yaml"] = (
        f"# Exported from suite store {manifest.experiment_id}.\n"
        "# This outcomes rule was written after the recorded outcomes existed.\n"
        "# Therefore fixed_before_runs is false.\n"
        + yaml.safe_dump(rule.model_dump(mode="json", exclude_none=True), sort_keys=False)
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = tuple(out_dir / name for name in content)
    for path, body in zip(paths, content.values(), strict=True):
        path.write_text(body, encoding="utf-8", newline="")
    return paths


def main(argv: list[str] | None = None) -> int:
    """Keep command failures to one diagnostic line and exit 3."""
    try:
        arguments = sys.argv[1:] if argv is None else argv
        if len(arguments) != 2:
            raise ValueError("usage: python -m bench.export_outcomes STORE OUT_DIR")
        paths = export_outcomes(Path(arguments[0]), Path(arguments[1]))
    except Exception as exc:
        reason = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {reason}", file=sys.stderr)
        return 3
    for path in paths:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
