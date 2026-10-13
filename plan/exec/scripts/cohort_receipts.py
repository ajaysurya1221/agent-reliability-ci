"""Build TTFV receipts (one per reader per track) from the AI-cohort workflow result.

    python plan/exec/scripts/cohort_receipts.py <workflow result json> <receipts dir> <readme commit>

The result json is the Workflow tool's return value: {"results": [{"reader": {...}, "out": {...}}],
"scores": [{"id": ..., "score": {...}}]}. Readers are AI agents: every receipt sets reader.kind to
"ai-agent" and is never counted as a cold reader (protocol section 1.4).
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

MACHINE = {
    "os": "Darwin 27.0.0 (macOS, arm64)",
    "cpu": "Apple M5 Pro, 15 cores",
    "python": "Python 3.14.6",
    "uv": "uv 0.12.5",
    "uv_cache": "warm",
}
COACHING = [
    {
        "at": "pre-attempt",
        "what": (
            "Facilitator prompt stated, before the clock, that this harness blocks "
            "`uv tool install` and that uvx or a uv venv are alternatives; it also prescribed the "
            "timestamping wrapper and the milestone names. No explanation of ARCI was given."
        ),
    }
]


def parse(ts: str | None) -> dt.datetime | None:
    if not ts:
        return None
    try:
        return dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def seconds(a: str | None, b: str | None) -> int | None:
    pa, pb = parse(a), parse(b)
    if pa is None or pb is None:
        return None
    return int((pb - pa).total_seconds())


def base(template: dict, reader: dict, track: str, readme_commit: str) -> dict:
    r = json.loads(json.dumps(template))
    r["track"] = track
    r["date"] = "2026-10-13"
    r["reader"] = {
        "_comment": template["reader"]["_comment"],
        "handle": f"ai-{reader['id']}",
        "kind": "ai-agent",
    }
    r["facilitator"] = "claude-fable-orchestrator"
    r["machine"] = {"_comment": template["machine"]["_comment"], **MACHINE}
    r["network"] = "yes"
    r["package"] = {
        "_comment": template["package"]["_comment"],
        "version": "0.8.0",
        "source": "pypi",
        "wheel_sha256": "",
        "readme_url": (
            f"https://github.com/ajaysurya1221/agent-reliability-ci/blob/{readme_commit}/README.md"
        ),
    }
    r["coaching_events"] = list(COACHING)
    return r


def verdict_of(line: str | None) -> str:
    if not line:
        return "ERROR"
    for v in ("PASS", "BLOCK", "INCONCLUSIVE", "ERROR"):
        if v in line:
            return v
    return "ERROR"


def build(result_path: Path, out_dir: Path, readme_commit: str) -> None:
    data = json.loads(result_path.read_text(encoding="utf-8"))
    template = json.loads((out_dir.parent / "receipt.template.json").read_text(encoding="utf-8"))
    scores = {s["id"]: s["score"] for s in data.get("scores", []) if s}
    rows: list[str] = []
    for item in data["results"]:
        reader, out = item["reader"], item["out"]
        if not out:
            rows.append(f"| ai-{reader['id']} | no result | | | | |")
            continue
        sc = scores.get(reader["id"]) or {}
        a, b, ans = out["track_a"], out["track_b"], out["answers"]
        persona = reader["persona"]
        model = reader["model"]
        common_notes = (
            f"AI-agent reader (Claude {model} via the Workflow tool, persona: {persona}); "
            "self-stamped milestones with `date -u` under the facilitator's wrapper; machine shared "
            "with the orchestrator session (not controlled). Never counted as a cold reader. "
            f"Files read: {', '.join(out.get('files_read', [])) or 'none listed'}. "
            f"Confusions: {' | '.join(out.get('confusions', [])) or 'none'}. "
            f"Reader notes: {out.get('notes', '')}"
        )
        # Track A receipt
        ra = base(template, reader, "demo", readme_commit)
        ra["timestamps"].update(
            {
                "readme_opened": a.get("readme_opened"),
                "command_start": a.get("command_start"),
                "demo_banner": a.get("demo_banner"),
                "demo_verdict": a.get("demo_verdict"),
                "all_steps_held": a.get("all_steps_held"),
                "interpretation_answered": None,
            }
        )
        ra["durations_seconds"].update(
            {
                "install": seconds(a.get("command_start"), a.get("demo_banner")),
                "scaffold": None,
                "run": seconds(a.get("demo_banner"), a.get("all_steps_held")),
                "agent_execution": None,
                "interpretation": None,
                "total": seconds(a.get("readme_opened"), a.get("all_steps_held")),
            }
        )
        held = bool(a.get("all_steps_held")) and a.get("exit_code") == 0
        ra["outcome"].update(
            {
                "completed": held and bool(sc.get("interpretation_demo_block")),
                "verdict": a.get("verdict_for_agent_b") or ("BLOCK" if held else "ERROR"),
                "exit_code": a.get("exit_code"),
                "store_validated": None,
                "decision_sha256": "",
                "init_attempts": None,
                "descriptor_hand_edited": None,
                "trials_started": None,
                "interpretation_answer": ans["interpretation_demo_block"],
                "interpretation_correct": sc.get("interpretation_demo_block"),
            }
        )
        ra["comprehension"]["answered_on"] = ""
        ra["comprehension"]["scorer"] = (
            f"scorer-{reader['id']} (Claude sonnet) + orchestrator check"
        )
        ra["comprehension"]["answers"] = {
            k: ans[k]
            for k in (
                "q1_what_is_it",
                "q2_who_for",
                "q3_pass_means",
                "q4_does_not_do",
                "q5_first_three_commands",
            )
        }
        ra["comprehension"]["scores"] = {
            k: sc.get(k)
            for k in (
                "q1_what_is_it",
                "q2_who_for",
                "q3_pass_means",
                "q4_does_not_do",
                "q5_first_three_commands",
            )
        }
        ra["comprehension"]["all_correct"] = sc.get("all_five_correct")
        ra["notes"] = (
            f"Command used: {a.get('command_used')}. Log: {a.get('log_path')}. "
            "interpretation_answered not stamped (answers given after both tracks). "
            + common_notes
            + f" Scorer rationale: {sc.get('rationale', '')}"
        )
        ra["failures"] = [f for f in out.get("failures", []) if "demo" in f.get("what", "").lower()]
        # Track B receipt
        rb = base(template, reader, "own-agent", readme_commit)
        rb["project"] = {
            "_comment": template["project"]["_comment"],
            "kind": "sample",
            "description": (
                "examples/recipes/python_agent copied to a temporary directory, arci.yaml removed; "
                f"project dir {b.get('project_dir')}"
            ),
            "refs_preexisting": True,
            "workers": None,
        }
        rb["timestamps"].update(
            {
                "readme_opened": a.get("readme_opened"),
                "install_start": b.get("install_start"),
                "install_done": b.get("install_done"),
                "scaffold_start": b.get("scaffold_start"),
                "descriptor_written": b.get("descriptor_written"),
                "run_start": b.get("run_start"),
                "verdict_printed": b.get("verdict_printed"),
                "store_validated": None,
                "interpretation_answered": None,
            }
        )
        rb["durations_seconds"].update(
            {
                "install": seconds(b.get("install_start"), b.get("install_done")),
                "scaffold": seconds(b.get("scaffold_start"), b.get("descriptor_written")),
                "run": seconds(b.get("run_start"), b.get("verdict_printed")),
                "agent_execution": None,
                "interpretation": None,
                "total": None,
            }
        )
        validated = (
            bool(b.get("verdict_line"))
            and b.get("gate_verdict_line") == b.get("verdict_line")
            and b.get("decision_sha256_before")
            and b.get("decision_sha256_before") == b.get("decision_sha256_after")
        )
        v = verdict_of(b.get("verdict_line"))
        rb["outcome"].update(
            {
                "completed": bool(validated)
                and v != "ERROR"
                and bool(sc.get("interpretation_own_run")),
                "verdict": v,
                "exit_code": b.get("run_exit_code"),
                "store_validated": bool(validated),
                "decision_sha256": b.get("decision_sha256_before") or "",
                "init_attempts": b.get("init_attempts"),
                "descriptor_hand_edited": b.get("descriptor_hand_edited"),
                "trials_started": "trials.jsonl" in (b.get("store_files") or []),
                "interpretation_answer": ans["interpretation_own_run"],
                "interpretation_correct": sc.get("interpretation_own_run"),
            }
        )
        rb["comprehension"]["answered_on"] = f"2026-10-13-ai-{reader['id']}-demo.json"
        rb["notes"] = (
            f"Install method: {b.get('install_method')}. Commands: "
            f"{' ; '.join(b.get('commands_used', []))}. Store: {b.get('store_dir')} with "
            f"{', '.join(b.get('store_files') or [])}; gate line: {b.get('gate_verdict_line')}. "
            "store_validated stamp and the protocol 4.4 total are null (the reader validated the "
            "store itself; the facilitator did not stamp it). " + common_notes
        )
        rb["failures"] = [
            f for f in out.get("failures", []) if "demo" not in f.get("what", "").lower()
        ]
        for rec, track in ((ra, "demo"), (rb, "own-agent")):
            path = out_dir / f"2026-10-13-ai-{reader['id']}-{track}.json"
            path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        rows.append(
            f"| ai-{reader['id']} ({model}) | A: {ra['durations_seconds']['install']}+"
            f"{ra['durations_seconds']['run']}={ra['durations_seconds']['total']} s, "
            f"exit {a.get('exit_code')} | B: install {rb['durations_seconds']['install']} s, "
            f"scaffold {rb['durations_seconds']['scaffold']} s, run {rb['durations_seconds']['run']} s, "
            f"{v}, validated={bool(validated)}, init_attempts={b.get('init_attempts')} | "
            f"q1-q5: {sum(1 for k in ra['comprehension']['scores'].values() if k)}/5 | "
            f"interp demo {sc.get('interpretation_demo_block')}, own {sc.get('interpretation_own_run')} | "
            f"failures {len(out.get('failures', []))} |"
        )
    print("| reader | Track A | Track B | comprehension | interpretation | failures |")
    print("|---|---|---|---|---|---|")
    print("\n".join(rows))


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
