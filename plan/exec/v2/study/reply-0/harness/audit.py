"""Verify Reply-0 evidence against the released schedule and independent fixture queries."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import posixpath
import re
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from arci.contracts import evaluate_contract
from arci.fingerprint import fingerprint
from arci.gate import replay_decision
from arci.hashing import hash_record
from arci.schedule import build_schedule, spec_sha256
from arci.schema import ContractSpec, GateDecision, Manifest, TrialEnvelope, TrialSpec
from arci.suite_gate import replay_suite_decision
from arci.suite_schedule import build_suite_round
from arci.suite_schema import SuiteDecision, SuiteManifest
from arci.toolbox import format_diagnostic

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness import make_suites  # noqa: E402
from harness.make_edited import build, hashes  # noqa: E402
from harness.relay import provenance  # noqa: E402
from probe import Server  # noqa: E402
from tasks.reply0_grade import passes  # noqa: E402

Row = dict[str, Any]
FX = make_suites.FX
ENV = Path(os.environ.get("REPLY0_ENV", Path(sys.prefix).parent))
DENY = ["sandbox-exec", "-p", "(version 1)(allow default)(deny network*)"]
LABELS = {
    "clean": ("clean", "clean", "clean"),
    "unscripted": ("clean", "clean", "none"),
    "main": ("naming-sentence", "reply-as-given", "bad"),
    "generic": ("naming-sentence", "generic-sentence", "bad"),
    "confirmation": ("edited-server", "server-as-shipped", "bad"),
}


def require(ok: bool, explanation: str) -> None:
    if not ok:
        raise ValueError(explanation)


def encoded(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    )


def same(actual: object, expected: object, field: str) -> None:
    # JSON true and 1, and explicit null and an absent field, are distinct evidence.
    require(encoded(actual) == encoded(expected), f"{field} differs")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


def lines(path: Path) -> list[Row]:
    return [json.loads(line) for line in path.read_bytes().splitlines()]


TRANSCRIPT_SHA256 = "80aff1c9fb3f14d094e20a17594bda672183bd4c93e071c8802263ea2ba5d64a"


def transcript(path: Path, doc: Row) -> dict[str, Row]:
    rows = read(path)
    expected = {
        t["id"]: (cell, part, t["bad"])
        for cell, entry in doc["cells"].items()
        for part in ("main", "held_out")
        for t in entry[part]
    }
    require(isinstance(rows, list), "checker transcript must be an array")
    same(sorted(row["id"] for row in rows), sorted(expected), "checker task inventory")
    out = {}
    for row in rows:
        cell, part, call = expected[row["id"]]
        original = row.get("original_result")
        require(
            isinstance(original, dict) and isinstance(original.get("content"), list),
            "missing original_result in checker transcript",
        )
        expanded = json.loads(json.dumps(row).replace("$FX", str(FX)))
        same(
            [row["cell"], row["set"], expanded["bad_call"]], [cell, part, call], "checker identity"
        )
        out[row["id"]] = expanded["original_result"]
    same(digest(path), TRANSCRIPT_SHA256, "pinned checker transcript")
    return out


def fixture() -> None:
    manifest = FX / "manifest.json"
    same(
        digest(manifest),
        "9c0f4a2dcfaf924b46228be3a0d8dfe2248517bf9039302c44103dc63f1a84ea",
        "fixture manifest",
    )
    data = read(manifest)
    files = FX / "files"
    require(
        FX.resolve() == FX and not any(p.is_symlink() for p in FX.rglob("*")), "fixture symlink"
    )
    same(hashes(files), data["files"], "fixture files")

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["/opt/homebrew/bin/git", "--no-optional-locks", "-C", str(FX / "repo"), *args],
            stdin=subprocess.DEVNULL,
            timeout=15,
            text=True,
            env={
                "LC_ALL": "C",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
                "PATH": os.defpath,
            },
        ).strip()

    refs = git("for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads").splitlines()
    same(dict(line.split() for line in refs), data["repo"]["branches"], "fixture branches")
    same(git("rev-parse", "HEAD"), data["repo"]["branches"]["main"], "fixture HEAD")
    same(git("status", "--porcelain", "--untracked-files=all", "--ignored"), "", "fixture worktree")


def transform(cell: Row, call: Row, raw: Row, template: str) -> tuple[Row, bool]:
    normal: Row = deepcopy(raw)
    if "error" in raw:
        error = raw["error"]
        if error["code"] in {-32600, -32601, -32602}:
            return normal, False
        normal = {"isError": True, "content": [{"type": "text", "text": error["message"]}]}
    normal.setdefault("isError", False)
    if (
        "reply_pattern" not in cell
        or call["name"] != cell["tool"]
        or normal["isError"] is not cell["reply_is_error"]
    ):
        return normal, False
    blocks = normal["content"]
    if len(blocks) != 1 or blocks[0]["type"] != "text":
        return normal, False
    old, args = blocks[0]["text"], call["arguments"]
    match = re.fullmatch if cell["tool"] == "search_files" else re.search
    when = cell.get("sentence_when", {})
    if not match(cell["reply_pattern"], old) or any(
        args.get(k) is None for k in when.get("arg_present", [])
    ):
        return normal, False
    for key, pattern in when.get("arg_matches", {}).items():
        if not isinstance(args.get(key), str) or not re.fullmatch(pattern, args[key]):
            return normal, False

    def expand(m: re.Match[str]) -> str:
        arg = str(args[m[2]])
        return posixpath.dirname(arg) if m[1] == "parent" else arg

    new = re.sub(r"\{(arg|parent):([A-Za-z_]+)\}", expand, template)
    blocks[0]["text"] = new
    if normal.get("structuredContent", {}).get("content") == old:
        normal["structuredContent"]["content"] = new
    return normal, True


class FixtureServer(Server):
    def close(self) -> None:
        try:
            self.stop()
        finally:
            for pipe in (self._process.stdout, self._process.stderr):
                if pipe is not None:
                    pipe.close()


class Reference:
    """Query only advertised read-only tools on a separately launched shipped server."""

    def __init__(self, server: Server, cell: str):
        self.server = server
        self.init = self.rpc(
            "initialize",
            {
                "capabilities": {},
                "protocolVersion": "2025-11-25",
                "clientInfo": {"name": "arci-ollama-agent", "version": "0.2"},
            },
        )
        server.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools: list[Row] = []
        params: Row = {}
        while True:
            page = self.rpc("tools/list", params)
            tools.extend(
                t
                for t in page["tools"]
                if (
                    t["name"] in ("lookup_order", "check_stock")
                    if cell == "C0"
                    else t.get("annotations", {}).get("readOnlyHint") is True
                )
            )
            if not page.get("nextCursor"):
                break
            params = {"cursor": page["nextCursor"]}
        self.listed = {k: v for k, v in page.items() if k != "nextCursor"} | {"tools": tools}
        self.names = {t["name"] for t in tools}
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"]
                    if isinstance(t.get("description"), str)
                    else t["name"],
                    "parameters": t.get("inputSchema", {"type": "object"}),
                },
            }
            for t in tools
        ]
        self.cache: dict[str, Row] = {}

    def rpc(self, method: str, params: Row) -> Row:
        _, reply, _, problem = self.server.request(method, params)
        if problem or reply is None:
            raise ValueError(f"independent {method} failed: {problem}")
        return reply["result"] if "result" in reply else {"error": reply["error"]}

    def query(self, call: Row) -> Row:
        require(call["name"] in self.names, "tool outside reference allowlist")
        key = encoded(call)
        if key not in self.cache:
            self.cache[key] = self.rpc("tools/call", call)
        return self.cache[key]


def server_command(
    cell_id: str, server: str, portable: bool = False
) -> tuple[list[str], dict[str, str]]:
    args = make_suites.relay_argv(ENV, FX, cell_id, server, [], None, portable=portable)
    env = dict(args[i + 1].split("=", 1) for i, a in enumerate(args) if a == "--env")
    return args[args.index("--") + 1 :], env


@contextmanager
def reference(
    cell_id: str, server: str, work: Path, task: Row, seed: int
) -> Generator[Reference, None, None]:
    command, env = server_command(cell_id, server)
    task_file = work / "task.json"
    task_file.write_text(encoded(task))
    sub = {"{workdir}": str(work), "{task_file}": str(task_file), "{seed}": str(seed)}
    argv = [sub.get(a, a) for a in command]
    if os.getenv("REPLY0_NO_SANDBOX") != "1":
        argv = DENY + argv
    process = FixtureServer(argv, env, str(work), 20.0)
    try:
        yield Reference(process, cell_id)
    finally:
        process.close()


@dataclass
class Observation:
    trial: TrialEnvelope
    exposure: bool
    retry: bool
    corrected: bool
    exhausted: bool
    length: bool = False
    late_infrastructure: str | None = None


@dataclass
class Evidence:
    experiment: str
    model: str
    cell: str
    phase: str
    observations: list[Observation]
    history: list[Row]
    verdict: str
    statistical_block: bool
    gate: str


def startup(
    ledger: list[Row],
    key: str,
    label: str,
    rules: str,
    server: str,
    ref: Reference,
    command: list[str],
    env: dict[str, str],
) -> list[Row]:
    require(
        all(r["record"] in {"arm", "start", "task", "norm", "call"} for r in ledger),
        "invalid ledger event",
    )
    fixed = [r for r in ledger if r["record"] != "norm"]
    same(
        fixed[:2],
        [
            {"record": "arm", "arm": label, "rules": rules, "server": server},
            {"record": "task", "key_id": key},
        ],
        "ledger assignment",
    )
    start = fixed[2]
    prefix = DENY if start["argv"][:3] == DENY else []
    same(
        start,
        {
            "record": "start",
            "argv": prefix + command,
            "sha256": provenance(command, env),
            "module_root": env.get("PYTHONPATH"),
            "protocolVersion": ref.init["protocolVersion"],
            "serverInfo": ref.init["serverInfo"],
        },
        "server launch",
    )
    require(all(r["record"] == "call" for r in fixed[3:]), "unexpected second startup")
    return fixed[3:]


def boundary(
    trial: TrialEnvelope, ref: Reference, calls: list[Row], results: list[tuple[Row, str | None]]
) -> None:
    rpc = [r for r in trial.recording if r.tool.startswith("rpc:")]
    same([r.tool for r in rpc], ["rpc:initialize", "rpc:tools/list"], "RPC recording")
    for r, value in zip(rpc, [ref.init, ref.listed], strict=True):
        same(r.result.value, value, r.tool)
        require(r.result.ok and r.result.injected_by is None, "failed RPC")
    records = [r for r in trial.recording if not r.tool.startswith("rpc:")]
    starts = [e.payload for e in trial.events if e.kind == "tool_start"]
    incomplete = [c.model_dump() for c in trial.incomplete_calls]
    if incomplete:
        require(
            trial.termination != "completed" and len(incomplete) == 1, "invalid incomplete call"
        )
        same(starts[-1], incomplete[0], "interrupted boundary call")
        starts.pop()
    finishes = [e.payload for e in trial.events if e.kind == "tool_finish"]
    occurrences: Counter[str] = Counter()
    for i, (call, (result, injection), r, start, finish) in enumerate(
        zip(calls, results, records, starts, finishes, strict=True)
    ):
        name, args = call["name"], call["arguments"]
        identity = f"c-{i:04d}"
        occurrence = occurrences[name]
        same(
            start,
            {"call_id": identity, "tool": name, "arguments": args, "occurrence": occurrence},
            "tool_start",
        )
        occurrences[name] += 1
        same(
            [r.tool, r.occurrence, r.arguments_sha256],
            [name, occurrence, hash_record(args)],
            "recorded call",
        )
        error = "mcp_error" if "error" in result else "tool_error" if result["isError"] else None
        expected = {
            "tool": name,
            "call_id": identity,
            "value": result,
            "ok": error is None,
            "injected_by": injection,
            "error_kind": error,
        }
        same(finish, expected, "tool_finish")
        same(r.result.model_dump(include=set(expected)), expected, "sealed tool result")


@dataclass
class MessageEvidence:
    answer: str | None
    exhausted: bool
    terminal_length: bool
    refused_over_budget: bool


def messages(
    receipt: Row,
    ref: Reference,
    task: Row,
    prompt: str,
    model: str,
    opening: str,
    calls: list[Row],
    texts: list[str],
    trial: TrialEnvelope,
    offline: bool,
    budget: int,
) -> MessageEvidence:
    history: list[Row] = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": task["ask"]},
    ]
    attempted: list[Row] = []
    used = 0
    over_budget = False
    terminal_length = False

    def deliver(function: Row) -> None:
        nonlocal used, over_budget
        name = function["name"]
        call = {"name": name, "arguments": function.get("arguments", {})}
        attempted.append(call)
        if name not in ref.names:
            error = {"code": -32601, "message": f"unknown tool {name}"}
            text = f"MCP RPC error: {error}"
        elif used == budget:
            over_budget = True
            require(trial.termination == "budget", "unrecorded excess call")
            text = "arci: tool budget exceeded"
        else:
            same(calls[used], call, "call requested by agent")
            text = texts[used]
            used += 1
        history.append({"role": "tool", "tool_name": name, "content": text})

    if opening != "none":
        call = task["bad"] if opening == "bad" else task["good"][0]
        history.append({"role": "assistant", "content": "", "tool_calls": [{"function": call}]})
        deliver(call)
    exchanges = receipt["exchanges"]
    same(receipt["steps"], len(exchanges), "attempted exchanges")
    require(1 <= len(exchanges) <= 8, "exchange count")
    answer = None
    last_calls: list[Row] = []
    saved_calls = attempted.copy()
    for i, exchange in enumerate(exchanges):
        saved_calls = attempted.copy()
        body = base64.b64decode(exchange["request_b64"], validate=True)
        same(hashlib.sha256(body).hexdigest(), exchange["sha256"], "sent-byte digest")
        same(
            json.loads(body),
            {
                "model": model,
                "messages": history,
                "tools": ref.tools,
                "stream": False,
                "think": False,
                "options": {"temperature": 0.7},
            },
            "sent request",
        )
        terminal = i == len(exchanges) - 1
        if exchange["status"] != 200:
            require(
                i > 0 and terminal and receipt["complete"] is False and trial.outcome != "PASS",
                "unanswered request",
            )
            break
        raw = base64.b64decode(exchange["response_b64"], validate=True)
        try:
            response = json.loads(raw)
        except (ValueError, UnicodeError):
            response = None
        if offline and isinstance(response, dict):
            same(response.get("received_sha256"), exchange["sha256"], "stand-in receiver digest")
        done_reason = None
        if isinstance(response, dict):
            done_reason = response.get("done_reason")
            same(response.get("model"), model, "response model")
            require(response.get("done") is True, "non-streaming response unfinished")
            if "done_reason" in exchange:
                same(exchange["done_reason"], done_reason, "receipt done_reason")
            else:
                require(
                    terminal and not receipt["complete"] and trial.termination == "timeout",
                    "missing receipt done_reason",
                )

        message = response.get("message") if isinstance(response, dict) else None
        if isinstance(message, dict):
            last_calls = message.get("tool_calls", [])
        if (
            not isinstance(message, dict)
            or message.get("role") != "assistant"
            or not isinstance(last_calls, list)
            or (not last_calls and not isinstance(message.get("content"), str))
            or any(
                not isinstance(c, dict)
                or not isinstance(c.get("function"), dict)
                or not isinstance(c["function"].get("name"), str)
                or not isinstance(c["function"].get("arguments", {}), dict)
                for c in last_calls
            )
        ):
            require(
                terminal
                and receipt["complete"] is False
                and trial.termination == "harness_error"
                and trial.outcome == "ERROR",
                "malformed backend response graded as a trial",
            )
            break
        history.append(message)
        if not last_calls:
            require(terminal, "request after final answer")
            answer = message["content"]
            terminal_length = done_reason == "length"
        for request in last_calls:
            if terminal and not receipt["complete"] and used == len(calls) and used < budget:
                break
            deliver(request["function"])
    same(used, len(calls), "forwarded call count")
    require(type(receipt["complete"]) is bool, "invalid completion flag")
    if receipt["complete"]:
        require(not last_calls or len(exchanges) == 8, "premature completion")
        same(receipt["answer"], answer, "last answer")
    else:
        require(trial.termination != "completed", "missing completed receipt")
        same(receipt["answer"], None, "partial answer")
    same(receipt["calls"], attempted if receipt["complete"] else saved_calls, "receipt calls")
    exhausted = bool(receipt["complete"] and len(exchanges) == 8 and last_calls and answer is None)
    return MessageEvidence(answer, exhausted, terminal_length, over_budget)


def termination_evidence(
    trial: TrialEnvelope, spec: TrialSpec, receipt: Row, present: bool, messages: MessageEvidence
) -> str | None:
    complete = receipt["complete"]
    exited_zero = trial.agent_claimed_success
    term = trial.termination
    detail = trial.failure_detail or ""
    require(not complete or present, "complete receipt without an answer file")
    same(
        trial.usage.tool_calls,
        sum(e.kind == "tool_start" for e in trial.events),
        "runner tool usage",
    )
    if term == "completed":
        require(
            complete and present and exited_zero is True,
            "completion lacks successful agent exit or answer",
        )
    elif term == "timeout":
        require(
            exited_zero is False
            and trial.usage.wall_seconds >= spec.budgets.max_seconds
            and detail == "trial exceeded max_seconds",
            "timeout contradicts agent exit or wall budget",
        )
    elif term == "budget":
        require(
            messages.refused_over_budget
            and trial.usage.tool_calls == spec.budgets.max_tool_calls
            and detail == "tool call budget exhausted",
            "call budget lacks runner evidence",
        )
    elif term == "crash":
        require(exited_zero is not True, "crash contradicts successful agent exit")
        if present:
            require(
                detail == "command exited non-zero"
                and trial.failure_fingerprint == fingerprint("crash", detail),
                "missing late crash evidence",
            )
    elif term == "grader_error":
        require(
            bool(
                trial.contract
                and trial.contract.grader_error
                and detail == format_diagnostic(trial.contract.grader_error)
            )
            and trial.failure_fingerprint == fingerprint("grader", detail),
            "missing grader failure evidence",
        )
    elif term == "harness_error":
        require(
            bool(detail) and trial.failure_fingerprint == fingerprint("harness", detail),
            "missing runner infrastructure evidence",
        )
        if present or complete:
            agent_failure = (
                exited_zero is False
                and spec.command is not None
                and any(
                    detail
                    == format_diagnostic(f"agent reported an infrastructure failure (exit {code})")
                    for code in spec.command.infra_exit_codes
                )
            )
            parent_failure = detail in {
                "boundary exited before returning",
                "MCP server exited before the agent finished",
                "event sink failed",
                "partial boundary protocol line",
                "boundary protocol line too long",
                "boundary protocol reader failed",
                "invalid boundary protocol",
            }
            require(parent_failure or agent_failure, "unsupported late infrastructure failure")
    else:
        raise ValueError("unexpected termination for registered recording")
    return (
        detail
        if present and term in ("harness_error", "grader_error", "timeout", "crash")
        else None
    )


def audit_trial(
    trial: TrialEnvelope,
    spec: TrialSpec,
    receipt: Row,
    ref: Reference,
    work: Path,
    doc: Row,
    task: Row,
    model: str,
    phase: str,
    run: str,
    edited: Path | None,
    fallback: bool,
    contract: ContractSpec,
    original: Row,
    offline: bool,
) -> Observation:
    cid = spec.condition.condition_id
    cell = doc["cells"][cid]
    side = int(spec.arm == "candidate")
    label, opening = LABELS[phase][side], LABELS[phase][2]
    same(
        [
            trial.experiment_id,
            trial.trial_id,
            trial.pair_id,
            trial.arm,
            trial.variant,
            trial.task_id,
            trial.condition_id,
            trial.seed,
            trial.spec_sha256,
        ],
        [
            spec.experiment_id,
            spec.trial_id,
            spec.pair_id,
            spec.arm,
            label,
            task["id"],
            cid,
            spec.seed,
            spec_sha256(spec),
        ],
        "scheduled identity",
    )
    same(spec.task, make_suites.public_task(cid, task), "registered task")
    same(
        [receipt[k] for k in ("run", "key_id", "arci_arm", "arm", "seed", "opening")],
        [run, task["key_id"], spec.arm, label, spec.seed, opening],
        "receipt identity",
    )
    state = trial.model_dump()["final_state"]
    require(isinstance(state, dict), "missing ledger and final state")
    rules = (
        {"naming-sentence": "naming", "generic-sentence": "generic"}.get(label, "none")
        if cid != "C0"
        else "none"
    )
    server = "edited" if label == "edited-server" else "shipped"
    portable = bool(spec.command and spec.command.argv[1:4] == ("-P", "-m", "agent"))
    command, env = server_command(cid, cell["server"], portable)
    if server == "edited":
        require(edited is not None, "missing registered edited source")
        assert edited is not None
        command[1] = make_suites.study_path(edited / "F1/package/dist/index.js", portable)
    command = [a.replace("{seed}", str(spec.seed)) for a in command]
    rows = startup(state["ledger"], task["key_id"], label, rules, server, ref, command, env)
    calls: list[Row] = []
    texts: list[str] = []
    results: list[tuple[Row, str | None]] = []
    exposure = False
    for seq, row in enumerate(rows):
        call = {"name": row["tool"], "arguments": row["arguments"]}
        raw = ref.query(call)
        name_result, hit = transform(cell, call, raw, cell["sentence"])
        if seq == 0 and cid != "C0" and opening == "bad":
            same(call, task["bad"], "scripted opening")
            require(hit, "registered fault absent at scripted opening")
            same(raw, original, "exact registered opening result")
        exposure |= hit
        expected_raw = deepcopy(raw)
        if hit and server == "edited":
            expected_raw = deepcopy(name_result)
            if "isError" not in raw:
                expected_raw.pop("isError")
        normal, _ = transform({}, call, expected_raw, "")
        delivered = normal
        if rules == "naming" and hit:
            delivered = name_result
        elif rules == "generic" and hit:
            delivered, _ = transform(cell, call, raw, doc["generic_sentence"])
        same(
            row,
            {
                "record": "call",
                "seq": seq,
                "tool": call["name"],
                "arguments": call["arguments"],
                "server_reply": expected_raw,
                "passed_on": delivered,
                "rule": rules + ":0" if delivered != normal else None,
            },
            f"ledger call {seq}",
        )
        injected = cid == "C0" and opening == "bad" and seq == 0
        result = delivered | {"content": []} if injected else delivered
        text = (
            ("MCP RPC error: " + str(result["error"]))
            if "error" in result
            else "\n".join(
                b["text"]
                for b in result["content"]
                if b["type"] == "text" and isinstance(b.get("text"), str)
            )
        )
        if injected:
            text = cell["sentence"] if side == 0 else "null" if fallback else ""
        calls.append(call)
        results.append((result, "empty_result" if injected else None))
        texts.append(text)
    boundary(trial, ref, calls, results)
    chain = messages(
        receipt,
        ref,
        task,
        doc["system_prompt"],
        model,
        opening,
        calls,
        texts,
        trial,
        offline,
        spec.budgets.max_tool_calls,
    )
    world = read(work / "state.json") if cid == "C0" else None
    same(
        state,
        {
            "ledger": state["ledger"],
            "answer": chain.answer if state["answer_present"] else None,
            "answer_present": state["answer_present"],
            "world": world,
        },
        "sealed final state",
    )
    require(type(state["answer_present"]) is bool, "invalid answer file evidence")
    late = termination_evidence(trial, spec, receipt, state["answer_present"], chain)
    expect = [str(world["order"]["total_cents"])] if world is not None else task["expect"]
    violations = evaluate_contract(contract, trial.events, spec.task, None).violations
    if trial.contract is not None:
        same(
            [v.model_dump() for v in trial.contract.violations],
            [v.model_dump() for v in violations],
            "observed contract violations",
        )
    if (
        trial.termination == "completed"
        and trial.contract is not None
        and trial.contract.grader_error is None
    ):
        grade = passes(state["answer"], expect, task["decoys"])
        same(trial.contract.success, grade, "registered oracle")
        same(
            trial.outcome.value,
            "PASS" if grade and not violations else "FAIL",
            "sealed grade",
        )
    elif trial.termination == "completed":
        raise ValueError("completed without grading")
    else:
        error_terms = {"harness_error", "grader_error", "replay_miss"}
        same(
            trial.outcome.value,
            "ERROR" if trial.termination in error_terms else "FAIL",
            "termination outcome",
        )
    later = [c for c in calls[1:] if c["name"] == calls[0]["name"]]
    return Observation(
        trial,
        exposure,
        bool(later),
        any(c in task["good"] for c in later),
        chain.exhausted,
        chain.terminal_length,
        late,
    )


def compile_run_descriptor(path: Path) -> SuiteManifest | Manifest:
    # The study uses the installed 2.4.1 dual compiler. The checkout also contains a v1 compiler.
    return import_module("arci.descriptor").compile_run_descriptor(path)


def descriptor_path(store: Path, supplied: Path | None, run: str) -> Path:
    if supplied is not None:
        return supplied
    for p in (
        store / "descriptor.yaml",
        store.parent / "descriptor.yaml",
        store.parent.parent / "descriptor.yaml",
        ROOT / "runs" / run / "descriptor.yaml",
    ):
        if p.is_file():
            return p
    # Offline checks often keep a single named descriptor beside the stores directory.
    matches = [
        p
        for p in store.parent.parent.glob("*.yaml")
        if compile_run_descriptor(p).experiment_id == read(store / "manifest.json")["experiment_id"]
    ]
    require(len(matches) == 1, "provide the registered --descriptor")
    return matches[0]


def verify(
    store: Path,
    receipts: Path,
    check_dir: Path,
    descriptor: Path | None = None,
    expected_digest: str | None = None,
    edit_root: Path | None = None,
) -> Evidence:
    fixture()
    doc = make_suites.register()
    disk = read(store / "manifest.json")
    suite = disk.get("schema_version") == "arci-suite/1"
    run = disk["suite_id" if suite else "experiment_id"]
    path = descriptor_path(store, descriptor, run)
    if expected_digest is not None:
        same(digest(path), expected_digest, "pinned descriptor digest")
    manifest = compile_run_descriptor(path)
    registered = type(manifest).model_validate(disk)
    require(
        registered.validate_seal() and manifest.record_sha256 == registered.record_sha256,
        "compiled descriptor differs from sealed manifest",
    )
    trials = [
        TrialEnvelope.model_validate_json(line)
        for line in (store / "trials.jsonl").read_bytes().splitlines()
    ]
    events: dict[str, list[Row]] = defaultdict(list)
    for event in lines(store / "events.jsonl"):
        events[event["trial_id"]].append(event)
    trial_index = {t.trial_id: t for t in trials}
    require(
        len(trial_index) == len(trials) and all(t.validate_seal() for t in trials),
        "duplicate trial or invalid trial seal",
    )
    history: list[Row] = []
    statistical = False
    gate_text = ""
    if isinstance(manifest, SuiteManifest):
        sd = SuiteDecision.model_validate_json((store / "decision.json").read_bytes())
        require(replay_suite_decision(sd, manifest, trials), "suite decision replay")
        stop = sd.stopped_at_round or len(sd.history)
        require(stop > 0, "suite has no complete stopping round")
        schedule = [spec for r in range(1, stop + 1) for spec in build_suite_round(manifest, r)]
        history = [h.model_dump() for h in sd.history]
        verdict = sd.verdict.value
        statistical = bool(
            verdict == "BLOCK"
            and history[-1]["block_crossed"]
            and not any(h["candidate_hard_violations"] for h in history)
        )
        gate = subprocess.run(
            [sys.executable, "-B", "-m", "arci", "gate", str(store)],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
        gate_text = gate.stdout + gate.stderr
        require(
            gate.returncode == sd.exit_code and "stored decision: MATCH" in gate_text.splitlines(),
            "suite gate did not MATCH",
        )
    else:
        assert isinstance(manifest, Manifest)
        pd = GateDecision.model_validate_json((store / "decision.json").read_bytes())
        require(replay_decision(pd, manifest, trials), "plain decision replay")
        schedule = list(build_schedule(manifest))
        verdict = pd.verdict.value
    same(sorted(trial_index), sorted(s.trial_id for s in schedule), "scheduled trial set")
    same(sorted(events), sorted(trial_index), "events trial set")
    (condition,) = manifest.conditions
    cid = condition.condition_id
    cell = doc["cells"][cid]
    baseline, candidate = manifest.baseline.command, manifest.candidate.command
    require(baseline is not None and candidate is not None, "expected command agents")
    assert baseline and candidate
    opening = baseline.argv[baseline.argv.index("--opening") + 1]
    (phase,) = [
        p
        for p, v in LABELS.items()
        if v == (manifest.baseline.label, manifest.candidate.label, opening)
    ]
    model = baseline.argv[baseline.argv.index("--model") + 1]
    require(model in make_suites.MODELS.values(), "unknown model")
    fallback = "--empty-fallback-null" in baseline.argv
    for command in (baseline, candidate):
        for flag, val in (
            ("--model", model),
            ("--opening", opening),
            ("--run-id", run),
            ("--prompt", doc["system_prompt"]),
        ):
            same(command.argv[command.argv.index(flag) + 1], val, flag)
        same("--empty-fallback-null" in command.argv, fallback, "wiring fallback")
    offline = ["--offline" in command.argv for command in (baseline, candidate)]
    same(offline[0], offline[1], "transport assignment")
    if not offline[0]:
        # Recheck the pinned descriptor when counting a live run outside the wrapper.
        from harness import wiring_check as wire

        reg = wire.registration()
        key = next(key for key, tag in make_suites.MODELS.items() if tag == model)
        fallback_for_model = read(ROOT / "wiring.json")[key]["empty_fallback_null"]
        require(type(fallback_for_model) is bool, "unverified wiring")
        if isinstance(manifest, SuiteManifest):
            ids = read(ROOT / "clean-row/kept.json")[key][cid][
                "held_out" if phase == "confirmation" else "main"
            ]["kept"]
            _, pins = wire.descriptor_note(reg)
            same(digest(path), pins[f"runs/{run}/descriptor.yaml"], "pushed descriptor digest")
        else:
            require(phase in ("clean", "unscripted"), "unregistered plain live phase")
            ids = [manifest.task_id]
        parts = (
            ("held_out",)
            if phase == "confirmation"
            else ("main", "held_out")
            if phase == "clean"
            else ("main",)
        )
        rows = [row for part in parts for row in cell[part] if row["id"] in ids]
        canonical = "-".join(["reply0", phase, key, cid] + ([] if suite else ids))
        same(run, canonical, "canonical run")
        same(
            read(path),
            make_suites.descriptor(
                doc,
                ENV,
                FX,
                cid,
                phase,
                key,
                rows,
                run=run,
                plain=not suite,
                edited=(ENV / "edited" if phase == "confirmation" else None),
                fallback=cid == "C0" and phase == "main" and fallback_for_model,
            ),
            "registered live descriptor",
        )
    require(cid == "C0" or not fallback, "unexpected fallback")
    expected_tasks = {t["id"]: t for part in ("main", "held_out") for t in cell[part]}
    # The task checker is independent of this audit. All replies are also freshly queried.
    checks = transcript(check_dir / "tasks.check.json", doc)
    seen: set[str] = set()
    exported_receipts: list[Row] = []
    observations: list[Observation] = []
    with ExitStack() as stack:
        tmp = Path(stack.enter_context(TemporaryDirectory(dir=ROOT)))
        edited: Path | None = None
        if phase == "confirmation":
            require(cid == "F1", "ineligible confirmation")
            config = read(path)["mcp_server"]["argv"]
            edited_cmd = json.loads(next(a[7:] for a in config if a.startswith("edited=")))
            entry = ROOT / Path(edited_cmd[1])
            edited = entry.parents[3]
            require(
                entry == edited / "F1/package/dist/index.js",
                "unexpected edited command",
            )
            if edit_root is not None:
                require(
                    edited == edit_root.resolve(), "edited root differs from independent assignment"
                )
            rebuilt = build(ENV, tmp / "rebuilt", "F1")
            same(
                read(edited / "F1/digests.json"), read(rebuilt / "digests.json"), "edit provenance"
            )
            same(
                hashes(edited / "F1/package"),
                read(rebuilt / "digests.json")["after"],
                "edited tree",
            )
            same(
                str((edited / "F1/node_modules").resolve()),
                str((ENV / "node/node_modules").resolve()),
                "edited dependencies",
            )
        shared = (
            None if cid == "C0" else stack.enter_context(reference(cid, cell["server"], tmp, {}, 0))
        )
        for spec in schedule:
            trial = trial_index[spec.trial_id]
            ordered = sorted(events[spec.trial_id], key=lambda e: e["seq"])
            same([e["seq"] for e in ordered], list(range(len(ordered))), "event sequence")
            same(ordered, [e.model_dump(mode="json") for e in trial.events], "event stream")
            task = expected_tasks[spec.task_id]
            identity = [run, task["key_id"], spec.seed, spec.arm]
            filename = (
                hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()
                + ".json"
            )
            require(filename not in seen, "duplicate scheduled receipt identity")
            seen.add(filename)
            with ExitStack() as one:
                work = Path(one.enter_context(TemporaryDirectory(dir=tmp)))
                ref = shared or one.enter_context(
                    reference(cid, cell["server"], work, spec.task, spec.seed)
                )
                receipt = read(receipts / filename)
                exported_receipts.append(receipt)
                try:
                    obs = audit_trial(
                        trial,
                        spec,
                        receipt,
                        ref,
                        work,
                        doc,
                        task,
                        model,
                        phase,
                        run,
                        edited,
                        fallback,
                        manifest.contract,
                        checks[spec.task_id],
                        offline[0],
                    )
                except (KeyError, IndexError, TypeError, ValueError) as exc:
                    raise ValueError(f"{spec.trial_id}: {exc}") from exc
                observations.append(obs)
    same(sorted(p.name for p in receipts.iterdir()), sorted(seen), "receipt inventory")
    fixture()
    if (store / "ledger.jsonl").exists():
        expected_ledgers = [
            {"trial_id": t.trial_id, "ledger": (t.final_state or {}).get("ledger")} for t in trials
        ]
        same(
            sorted(map(encoded, lines(store / "ledger.jsonl"))),
            sorted(map(encoded, expected_ledgers)),
            "exported ledgers",
        )
    if (store / "receipts.jsonl").exists():
        same(
            sorted(map(encoded, lines(store / "receipts.jsonl"))),
            sorted(map(encoded, exported_receipts)),
            "exported receipts",
        )
    return Evidence(
        manifest.experiment_id,
        model,
        cid,
        phase,
        observations,
        history,
        verdict,
        statistical,
        gate_text,
    )


def reading_conditions(data: Evidence) -> list[str]:
    reasons: list[str] = []
    for side in ("baseline", "candidate"):
        ts = [o.trial.termination.value for o in data.observations if o.trial.arm == side]
        if "crash" in ts:
            reasons.append(f"{side}: crash")
        if 20 * ts.count("timeout") > len(ts):
            reasons.append(f"{side}: over 5% wall timeouts")
    return reasons


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("store", type=Path)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--check-dir", type=Path, required=True)
    parser.add_argument("--descriptor", type=Path)
    parser.add_argument("--descriptor-sha256")
    parser.add_argument("--edited", type=Path)
    return parser.parse_args()


def summary(data: Evidence) -> Row:
    reasons = reading_conditions(data)
    health = {}
    for side in ("baseline", "candidate"):
        obs = [o for o in data.observations if o.trial.arm == side]
        terms = Counter(o.trial.termination.value for o in obs)
        health[side] = {
            "trials": len(obs),
            "terminal_length": sum(o.length for o in obs),
            "late_infrastructure": [
                {"trial_id": o.trial.trial_id, "detail": o.late_infrastructure}
                for o in obs
                if o.late_infrastructure is not None
            ],
            "crashes": terms["crash"],
            "wall_timeouts": terms["timeout"],
            "call_budget": terms["budget"],
            "step_exhausted": sum(o.exhausted and o.trial.termination == "completed" for o in obs),
        }
    return {
        "valid": not reasons,
        "reasons": reasons,
        "arms": health,
        "experiment_id": data.experiment,
        "trials": len(data.observations),
        "verdict": data.verdict,
        "statistical_block": data.statistical_block,
        "gate": data.gate,
    }


def main() -> int:
    args = arguments()
    try:
        data = verify(
            args.store,
            args.receipts,
            args.check_dir,
            args.descriptor,
            args.descriptor_sha256,
            args.edited,
        )
        report = summary(data)
        print(encoded(report))
        return int(not report["valid"])
    except (
        OSError,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        print(encoded({"valid": False, "reasons": [str(exc)]}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
