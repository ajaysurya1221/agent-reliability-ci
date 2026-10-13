"""Build TTFV receipts (one per reader per track) from the AI-cohort workflow result.

    python plan/exec/scripts/cohort_receipts.py <result json> <receipts dir> <readme commit>

The result json is the Workflow tool's return value: {"results": [{"reader": {...}, "out": {...}}],
"scores": [{"id": ..., "score": {...}}]}. Readers are AI agents: every receipt sets reader.kind to
"ai-agent" and is never counted as a cold reader (protocol section 1.4).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

MACHINE = {
    "os": "Darwin 27.0.0 (macOS, arm64)",
    "cpu": "Apple M5 Pro, 15 cores",
    "python": "Python 3.14.6",
    "uv": "uv 0.12.5",
    "uv_cache": "warm",
}
# Readers whose scaffold_start stamp belongs to the failed first `arci init` (protocol 4 wants the
# invocation that produced the descriptor used for the run); their successful start was not stamped.
SCAFFOLD_START_UNKNOWN = {"reader-2-opus", "reader-3-sonnet", "reader-5-haiku"}
COACHING = [
    {
        "at": "",
        "what": (
            "Before readme_opened (not stamped): the facilitator prompt stated that this harness "
            "blocks `uv tool install` and that uvx or a uv venv are alternatives; it also "
            "prescribed the timestamping wrapper and the milestone names. No explanation of ARCI "
            "was given."
        ),
    }
]


REPO = "/Users/ajay/Developer/agent-reliability-ci/"
# A macOS per-user temp root (`/var/folders/xx/yyyy/T/<generated name>`) or a `/tmp/<name>` root;
# the path tail after the root is kept, so `<tmp>/demo.log` stays readable.
TMP_ROOT_RE = re.compile(
    r"/(?:private/)?(?:var/folders/[^/\s]+/[^/\s]+/T/[^/\s,;)'\"\]]+|tmp/[^/\s,;)'\"\]]+)"
)
# Generated directory names that may appear on their own (uv venvs, demo stores, caches).
LEAF_RE = re.compile(
    r"\b(?:tmp\.[A-Za-z0-9]{6,}|arci-demo-[a-z0-9]{6,}|uvcache\.[A-Za-z0-9]{6,}|ttfv-[ab]\.[A-Za-z0-9]{6,})\b"
)


def scrub(text: str | None) -> str:
    """Trim the maintainer checkout to repository-relative paths; replace temp roots and
    generated directory names with `<tmp>`."""
    if not text:
        return ""
    text = text.replace(REPO, "")
    text = TMP_ROOT_RE.sub("<tmp>", text)
    return LEAF_RE.sub("<tmp>", text)


def sentence(text: str | None) -> str:
    """Reader text followed by exactly one period."""
    t = scrub(text).rstrip()
    return t[:-1] if t.endswith(".") else t


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


def clean_failure(f: dict) -> dict:
    """ISO `at` only; any remark attached to the timestamp moves into `what`; paths scrubbed."""
    at = str(f.get("at", ""))
    m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)(.*)", at)
    if m:
        at, remark = m.group(1), m.group(2).strip(" ()")
    else:
        at, remark = "", at
    what = scrub(f.get("what", ""))
    if remark:
        what = f"[at: {remark}] {what}"
    return {"at": at, "milestone": scrub(f.get("milestone", "")), "what": what}


def is_demo_failure(f: dict) -> bool:
    text = (f.get("milestone", "") + " " + f.get("what", "")).lower()
    return "demo" in text or "all_steps_held" in text or "command_start" in text


def verdict_of(line: str | None) -> str:
    """The first whole-word verdict token in the reader's text (their own run's verdict comes
    first; later tokens are other lines they quoted)."""
    if not line:
        return "ERROR"
    m = re.search(r"\b(PASS|BLOCK|INCONCLUSIVE|ERROR)\b", line)
    return m.group(1) if m else "ERROR"


def agent_execution(store_dir: str | None) -> float | None:
    if not store_dir:
        return None
    path = Path(store_dir) / "trials.jsonl"
    if not path.exists():
        return None
    total = 0.0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            total += float(json.loads(line)["usage"]["wall_seconds"])
    return round(total, 3)


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
            "self-stamped milestones with `date -u` under the facilitator's wrapper; machine "
            "shared with the orchestrator session (not controlled). Never counted as a cold "
            "reader. "
            "Protocol 2.1 deviation: the maintainer checkout was present on the machine; the "
            "reader read README.md from it and Track B copied the sample tree from it (no clone "
            "was made by the reader). "
            f"Files read: {scrub(', '.join(out.get('files_read', []))) or 'none listed'}. "
            f"Confusions: {sentence(' | '.join(out.get('confusions', []))) or 'none'}. "
            f"Reader notes: {sentence(out.get('notes', ''))}."
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
        # The stamped attempt's exit code was never captured (the facilitator's wrapper used
        # bash's PIPESTATUS under zsh); readers 1-4 re-ran the demo under bash outside the clock
        # and reported that exit code. The receipt keeps the stamped attempt only.
        rerun_exit = a.get("exit_code")
        ra["outcome"].update(
            {
                "completed": None,
                "verdict": verdict_of(a.get("verdict_for_agent_b")),
                "exit_code": None,
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
            f"Command used: {sentence(a.get('command_used'))}. Log: {scrub(a.get('log_path'))}. "
            f"Reader's verdict line for agent B: {sentence(a.get('verdict_for_agent_b'))}. "
            + "The stamped attempt's exit code was not captured (the facilitator's wrapper used "
            "bash's PIPESTATUS under zsh), so exit_code and completed are null; "
            + (
                "the reader re-ran the demo under bash outside the clock and reported exit "
                f"{rerun_exit} (see failures). "
                if rerun_exit is not None
                else "the reader did not re-run it. "
            )
            + "interpretation_answered not stamped (answers given after both tracks). "
            + common_notes
            + f" Scorer rationale: {sentence(sc.get('rationale', ''))}."
        )
        failures = [clean_failure(f) for f in out.get("failures", [])]
        ra["failures"] = [f for f in failures if is_demo_failure(f)]
        # Track B receipt
        rb = base(template, reader, "own-agent", readme_commit)
        agent_exec = agent_execution(b.get("store_dir"))
        rb["project"] = {
            "_comment": template["project"]["_comment"],
            "kind": "sample",
            "description": (
                "examples/recipes/python_agent copied to a temporary directory, arci.yaml removed; "
                f"project dir {scrub(b.get('project_dir'))}"
            ),
            "refs_preexisting": True,
            "workers": None,
        }
        scaffold_start = None if reader["id"] in SCAFFOLD_START_UNKNOWN else b.get("scaffold_start")
        rb["timestamps"].update(
            {
                "readme_opened": a.get("readme_opened"),
                "install_start": b.get("install_start"),
                "install_done": b.get("install_done"),
                "scaffold_start": scaffold_start,
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
                "scaffold": seconds(scaffold_start, b.get("descriptor_written")),
                "run": seconds(b.get("run_start"), b.get("verdict_printed")),
                "agent_execution": agent_exec,
                "interpretation": None,
                "total": None,
            }
        )
        v = verdict_of(b.get("verdict_line"))
        validated = (
            bool(b.get("verdict_line"))
            and verdict_of(b.get("gate_verdict_line")) == v
            and v != "ERROR"
            and bool(b.get("decision_sha256_before"))
            and b.get("decision_sha256_before") == b.get("decision_sha256_after")
        )
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
            f"Install method: {sentence(b.get('install_method'))}. Commands: "
            f"{sentence(' ; '.join(b.get('commands_used', [])))}. "
            f"Store: {scrub(b.get('store_dir'))} with {', '.join(b.get('store_files') or [])}; "
            "gate line: "
            f"{scrub(b.get('gate_verdict_line'))}. "
            + (
                "scaffold_start is null: the reader's stamp was taken at the failed first "
                f"`arci init` ({b.get('scaffold_start')}), and the successful second invocation "
                "was not stamped, so the scaffold duration is unknown. "
                if reader["id"] in SCAFFOLD_START_UNKNOWN
                else ""
            )
            + "readme_opened is the Track A stamp (one README "
            "read for both tracks). store_validated stamp and the protocol 4.4 total are null (the "
            "reader validated the store itself; the facilitator did not stamp it). "
            + (
                "agent_execution summed from the store's trials.jsonl by the builder. "
                if agent_exec is not None
                else "agent_execution null: the temporary store was no longer readable. "
            )
            + common_notes
        )
        rb["failures"] = [f for f in failures if not is_demo_failure(f)]
        for rec, track in ((ra, "demo"), (rb, "own-agent")):
            path = out_dir / f"2026-10-13-ai-{reader['id']}-{track}.json"
            path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        rows.append(
            f"| ai-{reader['id']} ({model}) | A: {ra['durations_seconds']['install']}+"
            f"{ra['durations_seconds']['run']}={ra['durations_seconds']['total']} s, "
            f"exit {a.get('exit_code')} | B: install {rb['durations_seconds']['install']} s, "
            f"scaffold {rb['durations_seconds']['scaffold']} s, "
            f"run {rb['durations_seconds']['run']} s, "
            f"{v}, validated={bool(validated)}, init_attempts={b.get('init_attempts')} | "
            f"q1-q5: {sum(1 for k in ra['comprehension']['scores'].values() if k)}/5 | "
            f"interp demo {sc.get('interpretation_demo_block')}, "
            f"own {sc.get('interpretation_own_run')} | "
            f"failures {len(out.get('failures', []))} |"
        )
    print("| reader | Track A | Track B | comprehension | interpretation | failures |")
    print("|---|---|---|---|---|---|")
    print("\n".join(rows))


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
