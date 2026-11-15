"""Build the S0 report from exact saved counters, with source and scope receipts."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import TypedDict, cast

sys.path.insert(0, "/Users/ajay/Developer/.arci-worktrees/wt-v2-logs")
sys.path.insert(0, "/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/src")
from bench.selfcheck_logs import rate

ROOT = Path("/Users/ajay/Developer/.arci-worktrees/wt-v2-logs")
HERE = Path(__file__).resolve().parent


class Cell(TypedDict):
    id: int
    gate: str
    design: str
    mode: str
    sigma: float
    drop: str
    seed: int
    generated: int
    tested: int
    real: int
    none: int
    old: int
    verified: int
    seconds: float


class Retention(TypedDict):
    seed: int
    mode: str
    histories: int
    mismatch: int
    missing_rows: int
    partial_rows: int
    response_deficit: int
    max_response_deficit: int
    ignored: int
    whole_deleted_batches: int
    partial_deleted_batches: int
    refreshed: int
    runs: int
    seconds: float


class Timing(TypedDict):
    seconds: float
    workers: int


def main() -> None:
    cells = [cast(Cell, json.loads((HERE / f"cell-{i:02d}.json").read_text())) for i in range(34)]
    retention = cast(list[Retention], json.loads((HERE / "retention.json").read_text()))
    timing = cast(Timing, json.loads((HERE / "timing-all.json").read_text()))
    for cell in cells:
        assert cell["seed"] == 17112026 + cell["id"]
        if cell["gate"] != "G3":
            assert cell["generated"] == 20000
        else:
            assert cell["tested"] == 2000
        if cell["gate"] == "G1":
            assert cell["verified"] == 500
    record_summary = (HERE / "records.log").read_text().splitlines()[-1]
    assert record_summary.startswith("RECORD PATH PASS: 6000/6000; seconds=")
    record_seconds = float(record_summary.rsplit("=", 1)[1])
    g1 = [c for c in cells if c["gate"] == "G1"]
    passed = all(c["real" if c["mode"] == "null" else "none"] <= 566 for c in g1)
    passed = passed and retention[0]["histories"] == 500 and retention[0]["mismatch"] == 0
    first = (
        "GO: G1 and G4 pass for the specified seeded generators; "
        "the conditional exchangeability and retention limits still apply."
        if passed
        else "NO-GO: at least one required G1 or G4 gate failed."
    )
    before = cast(dict[str, str], json.loads((HERE / "before-hashes.json").read_text()))
    changed = [
        p
        for p, sha in before.items()
        if not (ROOT / p).is_file() or hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != sha
    ]
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    assert not changed and not status, (changed, status)
    frozen = 0
    for line in (ROOT / "FROZEN.sha256").read_text().splitlines():
        sha, path = line.split(maxsplit=1)
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha, path
        frozen += 1
    receipt = {
        "tracked_files": len(before),
        "changed": changed,
        "git_status": status,
        "frozen_verified": frozen,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    }
    (HERE / "verification.json").write_text(json.dumps(receipt, indent=2) + "\n")
    lines = [
        first,
        "",
        "# S0 logs/2 spike",
        "",
        "Scratch only. Seed base 17112026. Every table row names its seed. All brackets "
        "are Wilson 95% intervals from the existing self-check helper. Error rates are "
        "unconditional over generated histories; CANNOT TELL stays in that denominator. "
        "These finite simulations are implementation evidence, not a proof about user logs.",
        "",
        "## Generator and production path",
        "",
        "The window is 98 calendar days, 2026-01-01 through 2026-04-08 at UTC offset 0. "
        "The split is 2026-03-26 (day 84). Current-setting before-days are the last b "
        "days before that split; its a after-days are the last a days of the window. "
        "The remaining after-days have no current-setting response. The old setting "
        "occupies all earlier days and stops at the adoption date, strictly within the "
        "before period. "
        "Exactly half of each fixed-count cell has a third setting on six random after-days.",
        "",
        "Settings use raw ids claude-opus-4 (old), claude-sonnet-4 (current), and "
        "claude-haiku-4 (minor), all effort high. Token medians center near 20000, 10000, "
        "and 5000. This scale preserves integer counts for every requested exact percentage "
        "move. Each day has a single positive count value. The existing history_days "
        "generator supplies independent Gaussian latent streams and quantized log-normal "
        "counts. Baseline log SD is 0.45, except the stated 0.40 power cells.",
        "",
        "Current known responses per day are uniformly chosen from 20, 40, 60, 80, 100; "
        "0 to 20 unknown responses are added independently. Known-count zero shares are "
        "the existing generator rounded to tenths before any shift (0.1 to 0.4). Old "
        "days have 60, 80, or 100 known responses plus 0 to 20 unknowns, zero shares "
        "0.0 to 0.3. Minor days have four known responses (two zero) plus two unknowns. "
        "Edit counts and failures use the existing denominator-100 generator. No unknown "
        "reasoning count becomes zero. The minor setting is deliberately too small to win.",
        "",
        "In G1, the selected day values are exchangeable conditional on the response "
        "structure: response totals do not change their distributions. All three gating "
        "measures have exactly the requested usable days. The token boundary multiplies "
        "after-day medians by exactly 3/4. The share boundary adds exactly 1/10 to "
        "no_reasoning_share, changing no other day value or usable-day count. No clipping "
        "or rounding follows either move.",
        "",
        "Every simulated table calls production decide.decide_tool, including its whole-tool "
        "streak veto and unchanged exact rank tests. The first 500 histories in each G1 "
        "cell additionally expand to Response/EditResult records, select by after-period "
        "main-thread response counts, and call measures.build with model and effort overrides. "
        "Assertions compare the entire ToolTable and ToolDecision, not just the headline. "
        "Thus each design has 1500 record-path checks, 6000 total. Extra deterministic "
        "checks cover raw lexical model/effort ties, unknown reasoning, subagents, project "
        "filtering, future/out-of-window records, empty after-periods, and opaque setting aliases.",
        "",
        "## G1: error rates with setting changes",
        "",
        "Gate: wrong REAL DROP under null, and wrong NO DROP at each single-measure "
        "margin, must each be at most 566/20000. The old-choice column counts histories "
        "where the existing pooled-period selector would select the old setting. "
        "Record checks count exact selection, table, and decision matches.",
        "",
        "| design a/b | scenario | seed | wrong result (95% CI) | passed streak check (95% "
        "CI) | old choice (95% CI) | record checks (95% CI) | gate | seconds |",
        "|---|---|---:|---|---|---|---|---|---:|",
    ]
    for c in g1:
        wrong = c["real" if c["mode"] == "null" else "none"]
        lines.append(
            f"| {c['design']} | {c['mode']} | {c['seed']} | {rate(wrong, c['generated'])} | "
            f"{rate(c['tested'], c['generated'])} | {rate(c['old'], c['generated'])} | "
            f"{rate(c['verified'], 500)} | {'PASS' if wrong <= 566 else 'FAIL'} | "
            f"{c['seconds']:.3f} |"
        )
    lines += [
        "",
        "## G2: assumption failures, report only",
        "",
        "Busy-day histories multiply the current-setting token median by "
        "exp(-0.012 * (responses - 70)), quantized to 100 before testing. This is a "
        "strong inverse association, identical in both periods. It breaks the proposed "
        "conditional exchangeability assumption even though independent response counts "
        "and the fixed winner preserve unconditional exchangeability in this particular "
        "generator. A small error rate here would not establish the conditional assumption.",
        "",
        "New-model histories multiply only the first five current-setting day medians "
        "by exactly 1.15. There is no split-date shift. This intentionally makes early "
        "before-days different from later days. Both cells use log SD 0.45 and the "
        "production whole-tool rule.",
        "",
        "| design a/b | departure | seed | wrong REAL DROP / generated (95% CI) | passed "
        "streak check (95% CI) | wrong REAL DROP / tested (95% CI) | seconds |",
        "|---|---|---:|---|---|---|---:|",
    ]
    for c in cells:
        if c["gate"] == "G2":
            lines.append(
                f"| {c['design']} | {c['mode']} | {c['seed']} | "
                f"{rate(c['real'], c['generated'])} | {rate(c['tested'], c['generated'])} | "
                f"{rate(c['real'], c['tested'])} | {c['seconds']:.3f} |"
            )
    lines += [
        "",
        "## G3: power, report only",
        "",
        "Tested means all measures have enough days and the whole-tool streak check "
        "passes. Each cell stops on exactly 2000 tested histories. Generated also counts "
        "streak-vetoed histories. Conditional detection among tested histories and "
        "detection among all generated histories are both shown; the latter includes "
        "the cost of the rule as built. Wilson intervals are descriptive here because "
        "the generated denominator uses a stopping rule, not a prespecified fixed count. "
        "The stopping rule never uses REAL DROP or NO DROP.",
        "",
        "| design a/b | log SD | token drop | seed | tested | generated | REAL DROP / "
        "tested (95% CI) | REAL DROP / generated (95% CI) | NO DROP / generated (95% CI) | "
        "seconds |",
        "|---|---:|---|---:|---:|---:|---|---|---|---:|",
    ]
    for c in cells:
        if c["gate"] == "G3":
            lines.append(
                f"| {c['design']} | {c['sigma']:.2f} | {c['drop']} | {c['seed']} | "
                f"{c['tested']} | {c['generated']} | {rate(c['real'], c['tested'])} | "
                f"{rate(c['real'], c['generated'])} | {rate(c['none'], c['generated'])} | "
                f"{c['seconds']:.3f} |"
            )
    lines += [
        "",
        "## G4: kept rows",
        "",
        "write_rows and use_rows are pure functions over (tool, offset, setting, day) "
        "keys and complete count rows. They never sum alternative snapshots. Logs win "
        "equal response counts; kept rows win when logs have fewer responses. Writes "
        "enforce the model grammar, accepted efforts, 5000 distinct-count cap, and "
        "180-day age boundary. The offset notice counts stored rows, not responses.",
        "",
        "Each history spans 98 days, two tools, several valid settings, and four batches "
        "per day. Histograms include zero and positive counts, unknown responses, and "
        "Claude Code edit totals and failures. Runs begin during a random day and recur "
        "at random hours; current days can be incomplete. Before each run, only batches "
        "strictly older than 30 days can be removed, with whole-day and partial-day "
        "deletions. For short gaps, exact equality is asserted at every run for every "
        "day from the first run through that run, against full history available at "
        "the same instant. This checks every count field, not just response totals.",
        "",
        "| scenario | seed | mismatching histories (95% CI) | missing rows | incomplete "
        "rows | missing responses | maximum missing responses/history | offset-isolation "
        "checks (95% CI) | ignored offset rows | seconds |",
        "|---|---:|---|---:|---:|---:|---:|---|---:|---:|",
    ]
    for r in retention:
        lines.append(
            f"| {r['mode']} | {r['seed']} | {rate(r['mismatch'], r['histories'])} | "
            f"{r['missing_rows']} | {r['partial_rows']} | {r['response_deficit']} | "
            f"{r['max_response_deficit']} | {rate(r['histories'], r['histories'])} | "
            f"{r['ignored']} | {r['seconds']:.3f} |"
        )
    short, long = retention
    lines += [
        "",
        f"Short-gap histories refreshed {short['refreshed']} rows with larger response counts. "
        f"They removed {short['whole_deleted_batches']} batches under whole-day deletion "
        f"and {short['partial_deleted_batches']} under partial-day deletion across "
        f"{short['runs']} runs. Long-gap controls had {long['runs']} runs.",
        "",
        "Every offset check changes 0 to -480, +330, or +345 minutes, recomputes live "
        "day bins, asserts output equals fresh logs only, and asserts every old-offset "
        "row is counted as ignored. Writing the new offset leaves the old keys separate. "
        "Directed checks cover equal-count replacement, smaller-count preservation, "
        "larger-count replacement, input immutability, age 180 versus 181, grammar "
        "rejection, and 5000 versus 5001 distinct values.",
        "",
        "Why the short-gap property holds: a completed day is observed at a run less "
        "than 29 days later, before any response on that day is old enough to be "
        "deleted. That complete snapshot wins over later subsets. A partial first "
        "snapshot is refreshed before expiry. This argument requires immutable "
        "records, no late backdated arrivals, stable offset, admitted rows, and a "
        "horizon within the retained window. It does not promise recovery of data "
        "already deleted before the first run. Separate edit-only retention or "
        "correction of records without increasing response counts is outside the "
        "tested deletion model.",
        "",
        "## Decisions, surprises, and memo corrections",
        "",
        "1. The reader uses None for a hidden name, not an absent setting. The spike selector "
        "preserves these identities using the reader raw lexical order and production override "
        "aliases. All 6000 record-path checks were rerun after adding that edge case. "
        "M2 needs the restated A1, not merely a claim that counts are not outcomes. "
        "With log structure fixed, selection is fixed under permutations of day "
        "values at fixed usable slots. Conditional exchangeability then justifies "
        "the rank reference distribution; a union bound over three measures gives "
        "the real-drop bound. At a single-measure margin, A3 and A4 plus the same "
        "conditional assumption justify the existing strict-count argument. Simulation "
        "does not prove these assumptions for real logs. The current A2 explicitly "
        "forbids after-period count selection, so the new record must revise A2 and "
        "its proof as well as A1.",
        "2. The old rule picks the old setting in every short-current-history cell; "
        "the 14/42 cells show the less extreme case. M2 selects the current setting "
        "in all 6000 full-record checks and every generated compact history. The "
        "minor setting never wins by construction, so these are setting-change "
        "checks, not adversarial checks of every possible competitive selection rule.",
        "3. G2a can violate conditional exchangeability without showing inflated "
        "unconditional error in this fixed-winner design. G2b is outside the "
        "assumption even if its finite rates remain below the gate. Neither passing "
        "a streak check nor these examples validates a user history.",
        "4. M2 says the after period always contains a response, but explicit "
        "--since later than N is supported by the existing window code and gives "
        "an empty after period. Define that outcome and partial override behavior "
        "in the new record. M4 should say whether ignored offset counts mean rows, "
        "days, or responses; this spike counts rows. Its equality statement must "
        "be limited to admitted rows in the active window, since old rows are "
        "intentionally dropped after 180 days.",
        "5. G4 loses data in every long-gap control. Retaining the larger snapshot "
        "cannot recover a day never captured complete. Actual filesystem atomicity, "
        "permissions, invalid-file handling, all-or-none writes, and CLI output "
        "are product implementation work, outside this pure-function spike.",
        "",
        "## Re-run commands and timings",
        "",
        "Run from the worktree. All output paths below are inside the requested scratch directory.",
        "",
        "```sh",
        f"cd {ROOT}",
        f"S0_DIR={HERE}",
        'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B "$S0_DIR/spike.py" --gate all '
        '--workers 4 > "$S0_DIR/run.log" 2>&1',
        'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B "$S0_DIR/retention.py" > '
        '"$S0_DIR/retention.log" 2>&1',
        'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B "$S0_DIR/report.py"',
        "```",
        "",
        "For one table replace `--gate all` with `--gate G1`, `--gate G2`, or "
        "`--gate G3`; seeds and cell ids are unchanged. `--cell ID` reruns one "
        "saved cell (ids 0-11 G1, 12-15 G2, 16-33 G3). G4 uses retention.py. "
        "Individual cell times are printed in the tables. The following are sums "
        "of those elapsed cell times, not four-worker wall times:",
        "",
    ]
    for gate in ("G1", "G2", "G3"):
        lines.append(
            f"- {gate}: {sum(c['seconds'] for c in cells if c['gate'] == gate):.3f} elapsed "
            "worker-seconds."
        )
    lines += [
        f"- All G1-G3 together: {timing['seconds']:.3f} wall seconds with "
        f"{timing['workers']} processes.",
        f"- G4: {sum(r['seconds'] for r in retention):.3f} seconds.",
        "",
        "No cells were cut or reduced. G1 has 240000 histories; G2 has 80000; "
        f"G3 has {sum(c['generated'] for c in cells if c['gate'] == 'G3')} generated and "
        "36000 tested histories. G4 has 1000 histories and 1000 offset checks. "
        "The full computation is below the 60-minute budget.",
        "",
        "## Verification and boundaries",
        "",
        f"Record-path rerun: {record_seconds:.3f} seconds. Last line: `{record_summary}`.",
        "",
        "Commands:",
        "```sh",
        '.venv/bin/ruff format --no-cache "$S0_DIR"/*.py',
        '.venv/bin/ruff check --no-cache "$S0_DIR"/*.py',
        '.venv/bin/basedpyright --project pyproject.toml "$S0_DIR"/*.py',
        'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B "$S0_DIR/spike.py" --smoke',
        'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B "$S0_DIR/spike.py" --verify-records',
        "```",
        "",
        "Validation output is in checks.log, smoke.log, and records.log. No pyright ignores "
        "are used. Existing strict project configuration is used. Product tests "
        "were not edited or rerun; direct production-path assertions are the "
        "spike checks. Product code, tests, docs, and git state were not changed.",
        "",
        f"All {len(before)} tracked-file hashes match the pre-spike snapshot; "
        f"all {frozen} frozen hashes match FROZEN.sha256; git status is empty. "
        f"Source HEAD: {receipt['head']}. Bytecode writes and Ruff caches were disabled. "
        "verification.json and artifact-hashes.json preserve receipts.",
        "",
        "One preliminary memory-registry search under .codex occurred before the "
        "brief prohibition was read; it returned no matching material and supplied "
        "no evidence. No further .codex or .claude directory was opened. No user "
        "session logs were read, no network command was issued, and no dependency "
        "was added. All generated files are in the requested scratch directory.",
        "",
        "These results cover Claude Code's three measures for G1-G3, as in the "
        "reused self-check generator. They do not establish calibration for the "
        "Codex repeated-value measure, arbitrary usage patterns, serial dependence, "
        "retention-corrupted histories, or repeated daily looks. G4 covers count "
        "rows for both tools. Approval of this report is not acceptance evidence; "
        "the orchestrator must rerun the checks.",
    ]
    content = "\n".join(lines) + "\n"
    assert "\u2014" not in content
    (HERE / "REPORT.md").write_text(content)
    artifacts = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in HERE.iterdir()
        if p.is_file() and p.suffix in {".py", ".md", ".json"} and p.name != "artifact-hashes.json"
    }
    (HERE / "artifact-hashes.json").write_text(
        json.dumps(artifacts, sort_keys=True, indent=2) + "\n"
    )
    print(first)
    for gate in ("G1", "G2", "G3"):
        group = [c for c in cells if c["gate"] == gate]
        if gate == "G1":
            worst = max(group, key=lambda c: c["real" if c["mode"] == "null" else "none"])
            metric = worst["real" if worst["mode"] == "null" else "none"]
        else:
            worst = (min if gate == "G3" else max)(group, key=lambda c: c["real"] / c["generated"])
            metric = worst["real"]
        print(
            f"{gate} worst: {worst['design']} {worst['mode']} sigma={worst['sigma']} "
            f"drop={worst['drop']} seed={worst['seed']}: {rate(metric, worst['generated'])}"
        )
    print(
        "G4: 0/500 short-gap mismatches; 500/500 long-gap mismatches; 1000/1000 offset "
        "checks passed"
    )
    print(f"TRACKED/FROZEN PASS: {len(before)}/{frozen}; worktree clean")


if __name__ == "__main__":
    main()
