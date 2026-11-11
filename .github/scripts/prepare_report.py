"""Best-effort Action reports; summaries contain structured evidence only."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from tempfile import mkdtemp

from arci.cli import main
from arci.gate import decide
from arci.html_report import stored_suite_status, suite_meaning, visible_text
from arci.report import fault_accounting
from arci.schema import Condition, Outcome, TrialEnvelope
from arci.storage import load_run
from arci.suite_gate import decide_suite
from arci.suite_report import ASSUMPTIONS, CELL_WARNING, SEED_LIMITATION, guarantee
from arci.suite_storage import load_suite_run, manifest_schema_version


def identifier(value: str) -> str:
    """An inert Markdown code span, even for hostile v1 names and labels."""
    return (
        "`"
        + visible_text(value).replace("`", "[backtick]").replace("@", "@\u200b").replace("|", "¦")
        + "`"
    )


def arm_counts(trials: Sequence[TrialEnvelope]) -> str:
    lines: list[str] = []
    for arm in ("baseline", "candidate"):
        selected = [t for t in trials if t.arm == arm]
        lines.append(
            f"{arm}: {sum(t.outcome is Outcome.PASS for t in selected)}/{len(selected)} passed"
        )
    return "\n".join(lines)


def faults(conditions: Sequence[Condition], trials: Sequence[TrialEnvelope]) -> str:
    rows = fault_accounting(conditions, trials)
    lines = ["## Fault accounting", "", "Counts are descriptive.", ""]
    if not rows:
        return "\n".join([*lines, "No faults declared."])
    lines += [
        "| Condition | Fault | Arm | Trials | Injections | Trials fired | Status |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    lines.extend(
        f"| {identifier(r['condition_id'])} | {identifier(r['fault'])} | {r['arm']} | "
        f"{r['trials']} | {r['injections']} | {r['trials_fired']} | {r['status']} |"
        for r in rows
    )
    return "\n".join(lines)


def prepare(stderr: Path, output: Path) -> None:
    stores = [
        line[11:] for line in stderr.read_text().splitlines() if line.startswith("run store: ")
    ]
    if not stores:
        raise ValueError("run did not produce a store")
    store = Path(stores[-1])
    output.mkdir(parents=True, exist_ok=True)
    main(["report", str(store), "--format", "html", "--out", str(output / "report.html")])
    if not (output / "report.html").is_file():
        raise ValueError("HTML report unavailable")
    if manifest_schema_version(store) == "arci-suite/1":
        manifest, trials = load_suite_run(store)
        decision = decide_suite(manifest, trials)
        mismatch = stored_suite_status(str(store), manifest, trials) == "mismatch"
        verdict, code = ("ERROR", 3) if mismatch else (decision.verdict.value, decision.exit_code)
        reason = "stored decision mismatch" if mismatch else "; ".join(decision.reasons)
        summary = [
            f"VERDICT: {verdict} (exit {code})",
            "Reason: " + identifier(reason),
            suite_meaning(decision, mismatch=mismatch),
            arm_counts(trials),
        ]
        if decision.history:
            last = decision.history[-1]
            c = last.counts
            summary.append(
                f"Pairs: {last.pairs}; minus {c.minus}, zero {c.zero}, "
                f"plus {c.plus}, errored {c.errored} / tolerance {decision.max_errored_pairs}.\n"
                f"Candidate hard violations: {last.candidate_hard_violations}."
            )
        else:
            summary.append(
                "Pairs: no validated complete round.\nCandidate hard violations: unavailable."
            )
        summary += [guarantee(manifest.scenario_seeds), ASSUMPTIONS, CELL_WARNING]
        if manifest.scenario_seeds == "per_round":
            summary.append(SEED_LIMITATION)
        summary += [
            "## Arm labels\n\nbaseline: "
            + identifier(manifest.baseline.label)
            + "\ncandidate: "
            + identifier(manifest.candidate.label),
            faults(manifest.conditions, trials),
        ]
    else:
        v1, observed = load_run(store)
        d = decide(v1, observed)
        summary = [
            f"VERDICT: {d.verdict.value} (exit {d.exit_code})",
            "Reason: " + identifier("; ".join(d.reasons) or "see condition reasons below"),
            arm_counts(observed),
            f"Observed pair ids: {len({t.pair_id for t in observed})} (descriptive).",
            f"Candidate hard violations: {sum(c.candidate_hard_violations for c in d.conditions)}.",
            "## Arm labels\n\nbaseline: "
            + identifier(v1.baseline.label)
            + "\ncandidate: "
            + identifier(v1.candidate.label),
        ]
        for c in d.conditions:
            summary.append(
                f"## Condition {identifier(c.condition_id)}\n\n"
                f"VERDICT: {c.verdict.value}; reason: {identifier('; '.join(c.reasons))}.\n"
                f"baseline: {c.baseline.successes}/{c.baseline.n}; "
                f"candidate: {c.candidate.successes}/{c.candidate.n}; "
                f"candidate hard violations: {c.candidate_hard_violations}."
            )
        summary.append(faults(v1.conditions, observed))
    # Blank lines delimit sections for bounded publication; identifiers cannot add lines.
    (output / "summary.md").write_text("\n\n".join(summary) + "\n", encoding="utf-8")
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
        stream.write(f"report_dir={output}\nartifact_name={output.name}\n")


if __name__ == "__main__":
    try:
        prepare(
            Path("arci-run.stderr"),
            Path(mkdtemp(prefix="arci-report-", dir=os.environ["RUNNER_TEMP"])),
        )
    except (OSError, ValueError, KeyError):
        print("ARCI report unavailable; gate result unchanged.")
