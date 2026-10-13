"""Build TTFV receipts (one per reader per track) from the AI-cohort workflow result.

    python plan/exec/scripts/cohort_receipts.py <result json> <receipts dir> <readme commit>
        [--legacy-sentence] [--overwrite]
    python plan/exec/scripts/cohort_receipts.py <result json> --persist <augmented json>

The result json is the Workflow tool's return value: {"results": [{"reader": {...}, "out": {...}}],
"scores": [{"id": ..., "score": {...}}]}. Readers are AI agents: every receipt sets reader.kind to
"ai-agent" and is never counted as a cold reader (protocol section 1.4).

`--persist` writes a copy of the result json in which each reader's `track_b` gains
`persisted_store`: the raw `trials.jsonl` lines of the reader's run store and their summed
`agent_execution`, read while the temporary store still exists. A later build from that copy
uses them when the store is gone, so the receipts rebuild byte for byte without the stores.

`--legacy-sentence` keeps the v0.8.0 builder's punctuation, which put an extra period after
reader text ending in a period inside closing quotes or brackets (`."`, `.")`, `."}`). The
2026-10-13 cohort receipts were built that way and are never edited after merge, so rebuild them
with this flag.

A build refuses to replace a receipt file that already exists in the receipts dir unless
`--overwrite` is given (committed receipts are never edited; rebuild them into a scratch copy).
It is all-or-nothing: every receipt is built in memory first, so an error leaves the receipts dir
untouched, then written to a staging directory inside it and moved into place.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

Json = dict[str, Any]

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
# Abbreviated temp paths typed by readers (`/var/folders/.../T/x`): the whole token goes.
TMP_ABBREV_RE = re.compile(r"/(?:private/)?var/folders/[^\s,;)'\"\]]*")
LEAF_RE = re.compile(
    r"\b(?:tmp\.[A-Za-z0-9]{6,}|arci-demo-[A-Za-z0-9_]{6,}|uvcache\.[A-Za-z0-9]{6,}|ttfv-[ab]\.[A-Za-z0-9]{6,})\b"
)


def scrub(text: str | None) -> str:
    """Trim the maintainer checkout to repository-relative paths; replace temp roots and
    generated directory names with `<tmp>`."""
    if not text:
        return ""
    text = text.replace(REPO, "")
    text = TMP_ROOT_RE.sub("<tmp>", text)
    text = TMP_ABBREV_RE.sub("<tmp>", text)
    return LEAF_RE.sub("<tmp>", text)


# Text whose last sentence already ended inside closing quotes or brackets: `."`, `.")`, `."}`.
CLOSED_SENTENCE_RE = re.compile(r"[.!?][\"')\]}]+$")


def sentence(text: str | None, *, legacy: bool = False) -> str:
    """Scrubbed reader text ending in exactly one terminal mark; "" when there is no text.

    A period is appended unless the text already ends in one, or (unless `legacy`) in a terminal
    mark followed by closing quotes or brackets. `legacy=True` reproduces the v0.8.0 builder.
    """
    t = scrub(text).rstrip()
    if not t or t.endswith("."):
        return t
    if not legacy and (t.endswith(("?", "!")) or CLOSED_SENTENCE_RE.search(t)):
        return t
    return t + "."


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


def base(template: Json, reader: Json, track: str, readme_commit: str) -> Json:
    r: Json = json.loads(json.dumps(template))
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


def clean_failure(f: Json) -> Json:
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


def is_demo_failure(f: Json) -> bool:
    text = (f.get("milestone", "") + " " + f.get("what", "")).lower()
    return "demo" in text or "all_steps_held" in text or "command_start" in text


def verdict_of(line: str | None) -> str:
    """The first whole-word verdict token in the reader's text (their own run's verdict comes
    first; later tokens are other lines they quoted)."""
    if not line:
        return "ERROR"
    m = re.search(r"\b(PASS|BLOCK|INCONCLUSIVE|ERROR)\b", line)
    return m.group(1) if m else "ERROR"


PERSISTED = "persisted_store"


def read_trials(store_dir: str | None) -> list[str] | None:
    """The raw lines of `<store>/trials.jsonl`, or None when the store is gone or unreadable."""
    if not store_dir:
        return None
    path = Path(store_dir) / "trials.jsonl"
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None


def sum_wall_seconds(lines: list[str]) -> float:
    """Protocol 4.5: the sum of usage.wall_seconds over the non-blank trials.jsonl lines."""
    total = 0.0
    for line in lines:
        if line.strip():
            total += float(json.loads(line)["usage"]["wall_seconds"])
    return round(total, 3)


def agent_execution(track_b: Json) -> float | None:
    """Summed agent_execution from the live store, else from `persisted_store`, else None.

    When both exist they must agree; a rebuild never silently changes a recorded value."""
    lines = read_trials(track_b.get("store_dir"))
    persisted: Json = track_b.get(PERSISTED) or {}
    from_persisted: float | None = None
    if persisted.get("trials_jsonl") is not None:
        from_persisted = sum_wall_seconds(persisted["trials_jsonl"])
        recorded = persisted.get("agent_execution")
        if recorded is not None and float(recorded) != from_persisted:
            msg = f"persisted agent_execution {recorded} != sum of persisted lines {from_persisted}"
            raise ValueError(msg)
    elif persisted.get("agent_execution") is not None:
        from_persisted = float(persisted["agent_execution"])
    if lines is None:
        return from_persisted
    live = sum_wall_seconds(lines)
    if from_persisted is not None and live != from_persisted:
        msg = f"store {track_b.get('store_dir')}: live {live} != persisted {from_persisted}"
        raise ValueError(msg)
    return live


def persist(result_path: Path, out_path: Path) -> None:
    """Write a copy of the result json with each readable store's trials lines and sum."""
    if out_path.resolve() == result_path.resolve():
        raise SystemExit("--persist writes a copy; give an output path other than the input")
    data: Json = json.loads(result_path.read_text(encoding="utf-8"))
    for item in data["results"]:
        out = item.get("out")
        if not out:
            continue
        b: Json = out["track_b"]
        lines = read_trials(b.get("store_dir"))
        rid = item["reader"]["id"]
        if lines is not None:
            total = sum_wall_seconds(lines)
            b[PERSISTED] = {"agent_execution": total, "trials_jsonl": lines}
            print(f"{rid}: persisted {len(lines)} lines, agent_execution {total}")
        elif b.get(PERSISTED):
            print(f"{rid}: store gone; keeping the already persisted values")
        else:
            print(
                f"{rid}: store gone and nothing persisted; agent_execution stays null",
                file=sys.stderr,
            )
    out_path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def write_all(out_dir: Path, receipts: dict[str, str], *, overwrite: bool) -> None:
    """Write every receipt or none: refuse existing files unless `overwrite`, stage the files in
    a temporary directory inside `out_dir`, then move each into place."""
    if not out_dir.is_dir():
        raise SystemExit(f"receipts dir {out_dir} does not exist")
    existing = sorted(name for name in receipts if (out_dir / name).exists())
    if existing and not overwrite:
        raise SystemExit(
            f"refusing to overwrite existing receipts in {out_dir} (pass --overwrite): "
            + ", ".join(existing)
        )
    staging = Path(tempfile.mkdtemp(prefix=".cohort-receipts-", dir=out_dir))
    try:
        for name, text in receipts.items():
            (staging / name).write_text(text, encoding="utf-8")
        for name in receipts:
            os.replace(staging / name, out_dir / name)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def build(
    result_path: Path,
    out_dir: Path,
    readme_commit: str,
    *,
    legacy: bool = False,
    overwrite: bool = False,
) -> None:
    data: Json = json.loads(result_path.read_text(encoding="utf-8"))
    template: Json = json.loads(
        (out_dir.parent / "receipt.template.json").read_text(encoding="utf-8")
    )

    def sent(text: str | None, fallback: str = "none.") -> str:
        return sentence(text, legacy=legacy) or fallback

    scores = {s["id"]: s["score"] for s in data.get("scores", []) if s}
    rows: list[str] = []
    receipts: dict[str, str] = {}
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
            f"Confusions: {sent(' | '.join(out.get('confusions', [])))} "
            f"Reader notes: {sent(out.get('notes', ''))}"
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
            f"Command used: {sent(a.get('command_used'))} Log: {scrub(a.get('log_path'))}. "
            f"Reader's verdict line for agent B: {sent(a.get('verdict_for_agent_b'))} "
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
            + f" Scorer rationale: {sent(sc.get('rationale', ''))}"
        )
        failures = [clean_failure(f) for f in out.get("failures", [])]
        ra["failures"] = [f for f in failures if is_demo_failure(f)]
        # Track B receipt
        rb = base(template, reader, "own-agent", readme_commit)
        agent_exec = agent_execution(b)
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
            f"Install method: {sent(b.get('install_method'))} Commands: "
            f"{sent(' ; '.join(b.get('commands_used', [])))} "
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
            name = f"2026-10-13-ai-{reader['id']}-{track}.json"
            if name in receipts:
                raise ValueError(f"two readers would write {name}")
            receipts[name] = json.dumps(rec, indent=2) + "\n"
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
    write_all(out_dir, receipts, overwrite=overwrite)
    print("| reader | Track A | Track B | comprehension | interpretation | failures |")
    print("|---|---|---|---|---|---|")
    print("\n".join(rows))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("result", type=Path, help="the Workflow result json (or a persisted copy)")
    ap.add_argument("receipts_dir", nargs="?", type=Path)
    ap.add_argument("readme_commit", nargs="?")
    ap.add_argument("--persist", type=Path, metavar="OUT_JSON", help="write an augmented copy")
    ap.add_argument("--legacy-sentence", action="store_true", help="v0.8.0 punctuation")
    ap.add_argument(
        "--overwrite", action="store_true", help="replace receipt files that already exist"
    )
    args = ap.parse_args(argv)
    if args.persist is not None:
        if args.receipts_dir is not None:
            ap.error("--persist takes only the result json")
        persist(args.result, args.persist)
        return
    if args.receipts_dir is None or args.readme_commit is None:
        ap.error("building receipts needs <receipts dir> and <readme commit>")
    build(
        args.result,
        args.receipts_dir,
        args.readme_commit,
        legacy=args.legacy_sentence,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
