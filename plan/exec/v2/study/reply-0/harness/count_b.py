"""Independent Reply-0 counter. Only released ARCI code is shared with the producer."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.metadata
import json
import os
import posixpath
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterator, Sequence
from contextlib import ExitStack
from dataclasses import asdict, dataclass, field
from pathlib import Path
from queue import Empty, Queue
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic
from typing import TextIO, cast

from pydantic import JsonValue

from arci.contracts import evaluate_contract
from arci.descriptor import compile_run_descriptor
from arci.fingerprint import fingerprint
from arci.gate import decide
from arci.hashing import hash_record
from arci.schedule import build_schedule, spec_sha256
from arci.schema import (
    ContractSpec,
    Event,
    GateDecision,
    Manifest,
    Outcome,
    TrialEnvelope,
    TrialSpec,
)
from arci.suite_gate import decide_suite
from arci.suite_schedule import build_suite_round, suite_experiment_id
from arci.suite_schema import SuiteDecision, SuiteManifest
from arci.toolbox import format_diagnostic

Obj = dict[str, JsonValue]
STUDY = Path(__file__).resolve().parents[1]
FX = Path("/Users/Shared/arci-reply0/fx")
TASK_SHA = "76ee13ca3c4eaa54514ae4c08cef1cc75e93e81c8b43ac4073dee5e267b922a1"
MODELS = ("qwen3.5:4b-mlx-ctx32k", "gemma4:12b-mlx-ctx32k")
SIDES = ("baseline", "candidate")


class Invalid(ValueError):
    """Evidence cannot support a verified count."""


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise Invalid(reason)


def obj(value: object) -> Obj:
    if not isinstance(value, dict):
        raise Invalid("expected a JSON object")
    return cast(Obj, value)


def array(value: object) -> list[JsonValue]:
    if not isinstance(value, list):
        raise Invalid("expected a JSON array")
    return cast(list[JsonValue], value)


def rows(value: object) -> list[Obj]:
    return [obj(item) for item in array(value)]


def string(value: object) -> str:
    if not isinstance(value, str):
        raise Invalid("expected a string")
    return value


def integer(value: object) -> int:
    if type(value) is not int:
        raise Invalid("expected an integer")
    return value


def dump(value: object) -> str:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    )


def same(actual: object, expected: object, what: str) -> None:
    require(dump(actual) == dump(expected), what)


def unique(items: list[tuple[str, JsonValue]]) -> Obj:
    result = dict(items)
    require(len(items) == len(result), "duplicate JSON member")
    return result


def parse(data: str | bytes) -> Obj:
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    result = obj(json.loads(data, object_pairs_hook=unique))
    _ = dump(result)  # Reject nonfinite numbers even in unused metadata.
    return result


def read(path: Path) -> Obj:
    return parse(path.read_bytes())


def jsonl(path: Path) -> Iterator[Obj]:
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            yield parse(line)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def flag(argv: Sequence[str], name: str) -> str:
    require(
        argv.count(name) == 1 and argv.index(name) + 1 < len(argv), f"missing or repeated {name}"
    )
    return argv[argv.index(name) + 1]


def normal_line(line: str) -> str:
    wrappers = " '\"\u2018\u2019\u201c\u201d`()[]{}"
    value = " ".join(unicodedata.normalize("NFKC", line).casefold().split())
    value = value.strip(wrappers).removesuffix(".").strip(wrappers)
    return value.replace(",", "") if re.fullmatch(r"[0-9]{1,3}(?:,[0-9]{3})+", value) else value


def grade(answer: JsonValue, expected: Sequence[JsonValue], decoys: Sequence[JsonValue]) -> bool:
    if not isinstance(answer, str) or len(answer) > 600 or not expected:
        return False
    lines = sorted(normal_line(line) for line in answer.strip().splitlines())
    return lines == sorted(normal_line(string(x)) for x in expected) and set(lines).isdisjoint(
        normal_line(string(x)) for x in decoys
    )


def verify_grade(
    trial: TrialEnvelope,
    contract: ContractSpec,
    answer: JsonValue,
    expected: Sequence[JsonValue],
    decoys: Sequence[JsonValue],
) -> None:
    # ARCI evaluates boundary invariants without importing an oracle when state is None.
    violations = evaluate_contract(contract, trial.events, {}, None).violations
    observed = trial.contract
    completed = trial.termination.value == "completed"
    # The parent can fail writing trial_end after a successful oracle evaluation.
    graded_before_sink_error = (
        trial.termination.value == "harness_error"
        and trial.failure_detail == "event sink failed"
        and trial.agent_claimed_success is True
        and observed is not None
        and observed.success
    )
    passed = (completed or graded_before_sink_error) and grade(answer, expected, decoys)
    if observed is not None:
        require(observed.violations == violations, "contract violations differ from observed calls")
        if observed.grader_error is None:
            same(observed.success, passed, "oracle disagrees with answer")
    if completed:
        require(
            observed is not None and observed.grader_error is None,
            "completed trial missing valid grade",
        )
        success = passed and not any(v.severity == "hard" for v in violations)
        same(
            trial.outcome.value,
            "PASS" if success else "FAIL",
            "sealed outcome disagrees with answer and observed contract",
        )
    elif trial.termination.value == "budget":
        require(trial.outcome == Outcome.FAIL, "budget exhaustion must count as FAIL")
    elif trial.termination.value in ("harness_error", "grader_error", "replay_miss"):
        require(trial.outcome == Outcome.ERROR, "infrastructure termination must count as ERROR")
    else:
        require(trial.outcome != Outcome.PASS, "PASS without completed grade")


@dataclass(frozen=True)
class Registration:
    cell: str
    definition: Obj
    task: Obj
    generic: str
    prompt: str


def registration() -> dict[str, Registration]:
    data = (STUDY / "tasks/tasks.json").read_bytes()
    require(digest(data) == TASK_SHA, "registered task bytes differ")
    registry = parse(data.decode().replace("{FX}", str(FX)))
    tasks: dict[str, Registration] = {}
    for cell, value in obj(registry["cells"]).items():
        definition = obj(value)
        for row in rows(definition["main"]) + rows(definition["held_out"]):
            task_id = string(row["id"])
            require(task_id not in tasks, "duplicate registered task")
            tasks[task_id] = Registration(
                cell,
                definition,
                row,
                string(registry["generic_sentence"]),
                string(registry["system_prompt"]),
            )
    return tasks


def opening_transcript(check_dir: Path) -> dict[str, Obj]:
    path = check_dir / "tasks.check.json"
    data = path.read_bytes()
    pins = [
        parts[0]
        for line in (STUDY / "reply0-digests.sha256").read_text().splitlines()
        if len(parts := line.split()) == 2 and parts[1] == "tasks/check/tasks.check.json"
    ]
    same(pins, [digest(data)], "opening transcript differs from registered pin")
    entries = rows(
        json.loads(data.decode("utf-8").replace("$FX", str(FX)), object_pairs_hook=unique)
    )
    indexed: dict[str, Obj] = {}
    for row in entries:
        key = string(row["id"])
        require(key not in indexed, "duplicate opening transcript row")
        require(isinstance(row.get("original_result"), dict), "transcript missing original_result")
        indexed[key] = row
    return indexed


def public_task(reg: Registration) -> Obj:
    row = reg.task
    task: Obj = {
        "cell": reg.cell,
        "key_id": row["key_id"],
        "ask": row["ask"],
        "bad": row["bad"],
        "clean": rows(row["good"])[0],
    }
    if reg.cell == "C0":
        task["order_id"] = row["order_id"]
    return task


def normal_reply(raw: Obj) -> Obj:
    if "error" in raw:
        error = obj(raw["error"])
        if error["code"] in (-32600, -32601, -32602):
            return raw
        return {"isError": True, "content": [{"type": "text", "text": error["message"]}]}
    return {"isError": False, **raw}


def matches(reg: Registration, call: Obj, reply: Obj) -> bool:
    cell = reg.definition
    if (
        "reply_pattern" not in cell
        or call["name"] != cell["tool"]
        or reply.get("isError") is not cell["reply_is_error"]
    ):
        return False
    blocks = rows(reply.get("content", []))
    if len(blocks) != 1 or blocks[0].get("type") != "text":
        return False
    text = string(blocks[0]["text"])
    match = re.fullmatch if reg.cell == "F2" else re.search
    args = obj(call["arguments"])
    when = obj(cell.get("sentence_when", {}))
    return (
        bool(match(string(cell["reply_pattern"]), text))
        and all(args.get(string(k)) is not None for k in array(when.get("arg_present", [])))
        and all(
            isinstance(args.get(k), str) and re.fullmatch(string(pattern), string(args[k]))
            for k, pattern in obj(when.get("arg_matches", {})).items()
        )
    )


def rewrite(reply: Obj, sentence: str, call: Obj) -> Obj:
    args = obj(call["arguments"])

    def replace(match: re.Match[str]) -> str:
        value = string(args[match[2]])
        return posixpath.dirname(value) if match[1] == "parent" else value

    text = re.sub(r"\{(arg|parent):([^}]+)\}", replace, sentence)
    block = rows(reply["content"])[0]
    result: Obj = {**reply, "content": [{**block, "text": text}]}
    structured = reply.get("structuredContent")
    if isinstance(structured, dict) and structured.get("content") == block["text"]:
        result["structuredContent"] = {**structured, "content": text}
    return result


class Reference:
    """Read the pinned shipped server over stdio. Never execute a stored command."""

    def __init__(self, stack: ExitStack, reg: Registration, spec: TrialSpec):
        env_root = Path(os.environ.get("REPLY0_ENV", "/Users/Shared/arci-reply0/env")).absolute()
        python = str(env_root / "py/bin/python")
        packages = env_root / "py/lib/python3.13/site-packages"
        self.directory = Path(stack.enter_context(TemporaryDirectory(dir=STUDY)))
        same(
            digest((FX / "manifest.json").read_bytes()),
            "9c0f4a2dcfaf924b46228be3a0d8dfe2248517bf9039302c44103dc63f1a84ea",
            "registered fixture manifest differs",
        )
        env = {
            "PATH": "/opt/homebrew/bin:/usr/bin:/bin",
            "TZ": "UTC",
            "LC_ALL": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "HOME": str(env_root / "home"),
        }
        self.sources: dict[str, Path] = {}
        if reg.definition["server"] == "filesystem":
            dist = env_root / "node/node_modules/@modelcontextprotocol/server-filesystem/dist"
            argv = [str(env_root / "node/bin/node"), str(dist / "index.js"), str(FX / "files")]
            self.sources.update({name: dist / name for name in ("index.js", "server.js")})
        elif reg.definition["server"] == "git":
            env.update(
                GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1", GIT_OPTIONAL_LOCKS="0"
            )
            package = packages / "mcp_server_git"
            self.sources.update({"mcp_server_git/" + p.name: p for p in package.glob("*.py")})
            argv = [python, "-P", "-m", "mcp_server_git", "--repository", str(FX / "repo")]
        else:
            require(spec.mcp_server is not None, "missing order desk bridge")
            assert spec.mcp_server is not None
            factory = flag(spec.mcp_server.argv, "--toolset")
            require(
                bool(re.fullmatch(r"orderdesk_world:[A-Za-z][A-Za-z_0-9]*", factory)),
                "unknown order desk toolset",
            )
            task_file = self.directory / "task.json"
            _ = task_file.write_text(dump(spec.task), encoding="utf-8")
            self.sources = {
                "arci/mcp_toolset_server.py": packages / "arci/mcp_toolset_server.py",
                "orderdesk_world.py": STUDY / "orderdesk/orderdesk_world.py",
            }
            env["PYTHONPATH"] = str(STUDY / "orderdesk")
            argv = [
                python,
                "-P",
                "-m",
                "arci.mcp_toolset_server",
                "--toolset",
                factory,
                "--workdir",
                str(self.directory),
                "--seed",
                str(spec.seed),
                "--task-file",
                str(task_file),
            ]
        self.sources["executable"] = Path(argv[0])
        self.digests = {k: digest(path.read_bytes()) for k, path in self.sources.items()}
        if os.environ.get("REPLY0_NO_SANDBOX") != "1":
            argv = ["sandbox-exec", "-p", "(version 1)(allow default)(deny network*)", *argv]
        self.process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env=env,
            cwd=self.directory,
        )
        stack.callback(self.close)
        self.lines: Queue[str] = Queue()
        assert self.process.stdout
        self.reader = Thread(target=self._read, args=(self.process.stdout,), daemon=True)
        self.reader.start()
        self.serial = 0
        self.identity = self.rpc(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "count-b", "version": "1"},
            },
        )
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.tools: list[Obj] = []
        cursor: Obj = {}
        seen: set[str] = set()
        while True:
            page = self.rpc("tools/list", cursor)
            for tool in rows(page["tools"]):
                name = string(tool["name"])
                allowed = (
                    name in ("lookup_order", "check_stock")
                    if reg.cell == "C0"
                    else obj(tool.get("annotations", {})).get("readOnlyHint") is True
                )
                if allowed:
                    description = tool.get("description")
                    self.tools.append(
                        {
                            "type": "function",
                            "function": {
                                "name": name,
                                "description": description
                                if isinstance(description, str)
                                else name,
                                "parameters": tool.get("inputSchema", {"type": "object"}),
                            },
                        }
                    )
            if not page.get("nextCursor"):
                break
            token = string(page["nextCursor"])
            require(token not in seen, "repeated tools/list cursor")
            seen.add(token)
            cursor = {"cursor": token}
        self.cache: dict[str, Obj] = {}

    def _read(self, stream: TextIO) -> None:
        try:
            for line in stream:
                self.lines.put(line)
        finally:
            self.lines.put("")

    def close(self) -> None:
        self.process.kill()
        _ = self.process.wait(timeout=5)
        self.reader.join(timeout=5)
        for stream in (self.process.stdin, self.process.stdout):
            if stream:
                stream.close()

    def send(self, frame: Obj) -> None:
        assert self.process.stdin
        _ = self.process.stdin.write(dump(frame) + "\n")
        self.process.stdin.flush()

    def rpc(self, method: str, params: Obj) -> Obj:
        deadline = monotonic() + 15
        self.serial += 1
        self.send({"jsonrpc": "2.0", "id": self.serial, "method": method, "params": params})
        while True:
            try:
                remaining = deadline - monotonic()
                require(remaining > 0, "reference server timed out")
                line = self.lines.get(timeout=remaining)
            except Empty as exc:
                raise Invalid("reference server timed out") from exc
            require(bool(line), "reference server closed")
            try:
                frame = parse(line)
            except ValueError:
                continue
            if "method" in frame:
                if "id" in frame:
                    reply: Obj = {"id": frame["id"], "jsonrpc": "2.0"}
                    if frame["method"] == "ping":
                        reply["result"] = {}
                    else:
                        reply["error"] = {"code": -32601, "message": "Method not found"}
                    self.send(reply)
            elif frame.get("id") == self.serial:
                return {"error": frame["error"]} if "error" in frame else obj(frame["result"])

    def original(self, call: Obj) -> Obj:
        require(
            any(obj(t["function"])["name"] == call["name"] for t in self.tools),
            "unadvertised forwarded call",
        )
        key = dump(call)
        if key not in self.cache:
            self.cache[key] = self.rpc("tools/call", call)
        return self.cache[key]


@dataclass(frozen=True)
class Assignment:
    phase: str
    opening: str
    label: str
    rules: str
    server: str
    model: str
    run: str
    empty_null: bool


def assignment(
    spec: TrialSpec, manifest: Manifest | SuiteManifest, reg: Registration
) -> Assignment:
    command = spec.command
    require(command is not None, "missing agent command")
    assert command
    argv = command.argv
    run = manifest.suite_id if isinstance(manifest, SuiteManifest) else manifest.experiment_id
    opening, model = flag(argv, "--opening"), flag(argv, "--model")
    labels = (manifest.baseline.label, manifest.candidate.label)
    key = (opening, *labels)
    phases = {
        ("bad", "naming-sentence", "reply-as-given"): "main",
        ("bad", "naming-sentence", "generic-sentence"): "generic",
        ("bad", "edited-server", "server-as-shipped"): "confirmation",
        ("clean", "clean", "clean"): "clean",
        ("none", "clean", "clean"): "unscripted",
    }
    phase = phases[key]
    require(phase != "confirmation" or reg.cell == "F1", "confirmation outside F1")
    require(model in MODELS and flag(argv, "--run-id") == run, "unexpected model or run")
    require(
        flag(argv, "--arm") == spec.variant and command.env.get("REPLY0_ARCI_ARM") == spec.arm,
        "arm command mismatch",
    )
    rules = {"naming-sentence": "naming", "generic-sentence": "generic"}.get(spec.variant, "none")
    if reg.cell == "C0":
        rules = "none"
    return Assignment(
        phase,
        opening,
        spec.variant,
        rules,
        "edited" if spec.variant == "edited-server" else "shipped",
        model,
        run,
        "--empty-fallback-null" in argv,
    )


def verify_patched_bytes(original: bytes, edited: bytes, patch: bytes) -> None:
    """Verify each unified-diff hunk against both byte streams, including unchanged gaps."""
    old_lines, new_lines = original.splitlines(keepends=True), edited.splitlines(keepends=True)
    lines = patch.splitlines(keepends=True)
    cursor = next((i for i, line in enumerate(lines) if line.startswith(b"@@ ")), len(lines))
    require(cursor < len(lines), "registered edit has no hunks")
    old_pos = new_pos = 0
    while cursor < len(lines):
        header = re.match(rb"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", lines[cursor])
        require(header is not None, "invalid registered diff header")
        assert header
        old_n, new_n = int(header[2] or b"1"), int(header[4] or b"1")
        old_start = int(header[1]) - int(old_n > 0)
        new_start = int(header[3]) - int(new_n > 0)
        require(
            old_pos <= old_start
            and new_pos <= new_start
            and old_lines[old_pos:old_start] == new_lines[new_pos:new_start],
            "changes outside registered patch",
        )
        cursor += 1
        old_hunk: list[bytes] = []
        new_hunk: list[bytes] = []
        while cursor < len(lines) and not lines[cursor].startswith(b"@@ "):
            marker, content = lines[cursor][:1], lines[cursor][1:]
            require(marker in (b" ", b"-", b"+"), "invalid registered hunk")
            cursor += 1
            if cursor < len(lines) and lines[cursor].startswith(b"\\ No newline at end of file"):
                content = content.removesuffix(b"\n")
                cursor += 1
            if marker != b"+":
                old_hunk.append(content)
            if marker != b"-":
                new_hunk.append(content)
        old_pos, new_pos = old_start + old_n, new_start + new_n
        require(
            len(old_hunk) == old_n
            and len(new_hunk) == new_n
            and old_lines[old_start:old_pos] == old_hunk
            and new_lines[new_start:new_pos] == new_hunk,
            "registered patch does not produce edited source",
        )
    require(old_lines[old_pos:] == new_lines[new_pos:], "changes after registered patch")


def startup(
    ledger: list[Obj],
    spec: TrialSpec,
    reg: Registration,
    a: Assignment,
    ref: Reference,
    edited: Path | None,
) -> None:
    def one(kind: str) -> Obj:
        found = [r for r in ledger if r["record"] == kind]
        require(len(found) == 1, f"missing or repeated ledger {kind}")
        return found[0]

    same(
        one("arm"),
        {"record": "arm", "arm": a.label, "rules": a.rules, "server": a.server},
        "wrong ledger arm",
    )
    same(one("task"), {"record": "task", "key_id": reg.task["key_id"]}, "wrong ledger task")
    start = one("start")
    require(
        all(r["record"] in ("arm", "task", "start", "norm", "call", "refused") for r in ledger),
        "ledger error or unknown record",
    )
    expected = dict(ref.digests)
    argv = [string(x) for x in array(start["argv"])]
    server = spec.mcp_server
    require(server is not None, "missing registered relay command")
    assert server
    options = server.argv
    if "--server" in options:
        commands = dict(
            options[i + 1].split("=", 1) for i, token in enumerate(options) if token == "--server"
        )
        command = [string(x) for x in array(json.loads(commands[a.server]))]
    else:
        command = list(options[options.index("--") + 1 :])
    # The relay can include its network-denial wrapper in the recorded actual argv.
    if argv[:1] == ["sandbox-exec"] and argv[1:3] == [
        "-p",
        "(version 1)(allow default)(deny network*)",
    ]:
        argv = argv[3:]
    command = [v.replace("{seed}", str(spec.seed)) for v in command]
    same(argv, command, "server argv differs from scheduled launch")
    environment = dict(
        options[i + 1].split("=", 1) for i, token in enumerate(options) if token == "--env"
    )
    roots = dict(
        options[i + 1].split("=", 1) for i, token in enumerate(options) if token == "--module-root"
    )
    same(
        start["module_root"],
        roots.get(a.server, environment.get("PYTHONPATH")),
        "server module root mismatch",
    )
    first_call = next(
        (i for i, r in enumerate(ledger) if r["record"] in ("call", "refused")), len(ledger)
    )
    require(
        all(r["record"] not in ("arm", "task", "start") for r in ledger[first_call:]),
        "call before startup",
    )
    if a.server == "edited":
        if edited is None:
            scripts = [
                Path(arg)
                for arg in command
                if Path(arg).parts[-4:] == ("F1", "package", "dist", "index.js")
            ]
            require(
                len(scripts) == 1,
                "cannot locate registered edit manifest",
            )
            folder = (STUDY / scripts[0]).parents[2]
        else:
            folder = edited / reg.cell
        edit = read(folder / "digests.json")
        require(edit["cell"] == reg.cell, "wrong edit manifest")
        patch = (STUDY / "harness/edits/F1.diff").read_bytes()
        same(edit["patch_sha256"], digest(patch), "wrong edit patch")
        before, after = obj(edit["before"]), obj(edit["after"])
        require(
            before.keys() == after.keys() and sum(before[k] != after[k] for k in before) == 1,
            "edit must change exactly one file",
        )
        require(
            any(
                (STUDY / arg).resolve() == (folder / "package/dist/index.js").resolve()
                for arg in argv
            ),
            "wrong edited launch",
        )
        for name, value in after.items():
            p = (folder / "package" / name).resolve()
            require(p.is_relative_to((folder / "package").resolve()), "invalid edit filename")
            edited_bytes = p.read_bytes()
            same(digest(edited_bytes), value, "edited package digest mismatch")
            original = ref.sources["index.js"].parent.parent / name
            shipped_bytes = original.read_bytes()
            same(digest(shipped_bytes), before[name], "shipped package digest mismatch")
            if before[name] != value:
                verify_patched_bytes(shipped_bytes, edited_bytes, patch)
        for name in ("index.js", "server.js"):
            expected[name] = string(after["dist/" + name])
    same(start["sha256"], expected, "server source digest mismatch")
    for k in ("protocolVersion", "serverInfo"):
        same(start[k], ref.identity[k], "wrong server initialization")


def event_calls(trial: TrialEnvelope) -> list[tuple[Obj, Obj | None]]:
    starts: dict[str, Obj] = {}
    finishes: dict[str, Obj] = {}
    occurrences: Counter[str] = Counter()
    last_call_id = None
    for event in sorted(trial.events, key=lambda e: e.seq):
        if event.kind not in ("tool_start", "tool_finish"):
            continue
        payload = event.payload
        name = string(payload["tool"])
        if name.startswith("rpc:"):
            continue
        call_id = string(payload["call_id"])
        last_call_id = call_id
        if event.kind == "tool_start":
            require(
                call_id not in starts and integer(payload["occurrence"]) == occurrences[name],
                "duplicate or misnumbered tool start",
            )
            starts[call_id] = payload
            occurrences[name] += 1
        else:
            require(call_id in starts and call_id not in finishes, "unmatched tool finish")
            finishes[call_id] = payload
    recording = {
        (r.tool, r.occurrence, r.arguments_sha256): r
        for r in trial.recording
        if not r.tool.startswith("rpc:")
    }
    require(
        len(recording) == sum(not r.tool.startswith("rpc:") for r in trial.recording),
        "duplicate recording",
    )
    unmatched = [s for cid, s in starts.items() if cid not in finishes]
    same(
        [
            c.model_dump(mode="json")
            for c in trial.incomplete_calls
            if not c.tool.startswith("rpc:")
        ],
        unmatched,
        "sealed incomplete calls differ from unmatched starts",
    )
    if unmatched:
        require(
            trial.termination.value == "timeout"
            and len(unmatched) == 1
            and unmatched[0]["call_id"] == last_call_id,
            "unmatched start must be the final tool event of a timeout",
        )
    require(len(finishes) == len(recording), "incomplete tool evidence")
    result: list[tuple[Obj, Obj | None]] = []
    for cid, start in starts.items():
        call = {"name": start["tool"], "arguments": start["arguments"]}
        finish = finishes.get(cid)
        if finish is None:
            result.append((call, None))
            continue
        record_key = (
            string(start["tool"]),
            integer(start["occurrence"]),
            hash_record(obj(start["arguments"])),
        )
        require(record_key in recording, "recording call mismatch")
        record = recording.pop(record_key)
        for key in ("tool", "ok", "value", "error_kind", "injected_by"):
            same(
                finish[key],
                record.result.model_dump(mode="json")[key],
                f"recording finish {key} mismatch",
            )
        same(finish["tool"], start["tool"], "finish names another tool")
        result.append((call, finish))
    return result


def message_text(value: Obj) -> str:
    if "error" in value:
        return "MCP RPC error: " + repr(value["error"])
    return "\n".join(
        string(block["text"]) for block in rows(value["content"]) if block.get("type") == "text"
    )


@dataclass
class Delivery:
    calls: list[Obj]
    texts: list[str]
    forwarded: list[Obj]
    exposed: bool
    pending: Obj | None


def delivery(
    trial: TrialEnvelope,
    ledger: list[Obj],
    reg: Registration,
    a: Assignment,
    ref: Reference,
    transcript: Obj | None = None,
) -> Delivery:
    calls: list[Obj] = []
    texts: list[str] = []
    forwarded: list[Obj] = []
    exposed = False
    events = event_calls(trial)
    entries = [r for r in ledger if r["record"] in ("call", "refused")]
    pending = events[-1][0] if events and events[-1][1] is None else None
    if pending is not None and len(entries) == len(events) - 1:
        events.pop()  # No relay reply had been persisted when the runner stopped the call.
    require(len(entries) == len(events), "missing or extra ledger call")
    for index, (row, (call, finish)) in enumerate(zip(entries, events, strict=True)):
        same(call, {"name": row["tool"], "arguments": row["arguments"]}, "ledger call mismatch")
        if finish is not None:
            calls.append(call)
        bad_opening = index == 0 and a.opening == "bad"
        if bad_opening:
            same(call, reg.task["bad"], "unregistered bad opening")
            require(row["record"] == "call", "scripted opening was refused")
        if row["record"] == "refused":
            require(
                all(obj(t["function"])["name"] != call["name"] for t in ref.tools),
                "refused advertised tool",
            )
            if finish is not None:
                value = obj(finish["value"])
                same(obj(value["error"])["code"], -32601, "wrong refused error")
                texts.append(message_text(value))
            continue
        same(row["seq"], len(forwarded), "ledger sequence mismatch")
        forwarded.append(call)
        raw = ref.original(call)
        normalized = normal_reply(raw)
        applies = matches(reg, call, normalized)
        if bad_opening and reg.cell != "C0":
            require(applies, "registered fault predicate absent at bad opening")
            require(transcript is not None, "missing registered opening transcript")
            assert transcript is not None
            same(transcript["cell"], reg.cell, "opening transcript cell mismatch")
            same(transcript["bad_call"], call, "opening transcript call mismatch")
            same(
                transcript["original_result"], raw, "opening transcript differs from shipped server"
            )
        exposed |= applies
        rule: str | None = None
        if applies and a.server == "edited":
            raw = rewrite(raw, string(reg.definition["sentence"]), call)
            normalized = normal_reply(raw)
        same(row["server_reply"], raw, "original server reply differs from independent fixture")
        if applies and a.rules != "none":
            normalized = rewrite(
                normalized,
                reg.generic if a.rules == "generic" else string(reg.definition["sentence"]),
                call,
            )
            rule = a.rules + ":0"
        same(row["rule"], rule, "wrong relay rule")
        same(row["passed_on"], normalized, "wrong relay delivery")
        if finish is None:
            continue
        injected = reg.cell == "C0" and a.phase == "main" and index == 0
        value = {**normalized, "content": []} if injected else normalized
        same(finish["injected_by"], "empty_result" if injected else None, "wrong fault injection")
        same(finish["value"], value, "sealed tool reply mismatch")
        text = message_text(value)
        if injected:
            text = (
                string(reg.definition["sentence"])
                if trial.arm == "baseline"
                else ("null" if a.empty_null else "")
            )
        texts.append(text)
    return Delivery(calls, texts, forwarded, exposed, pending)


def verify_complete_termination(trial: TrialEnvelope, spec: TrialSpec) -> None:
    """Check a finished receipt against the runner's independent exit and failure evidence."""
    term = trial.termination.value
    detail = trial.failure_detail
    if term == "timeout":
        require(
            trial.agent_claimed_success is False,
            "complete receipt contradicts timeout after successful exit",
        )
        require(
            trial.outcome == Outcome.FAIL,
            "runner timeout after a complete receipt must count as FAIL",
        )
    elif term == "grader_error":
        require(
            bool(detail)
            and trial.contract is not None
            and trial.contract.grader_error is not None
            and format_diagnostic(trial.contract.grader_error) == detail,
            "complete receipt without supporting grader error",
        )
    elif term == "harness_error":
        require(detail is not None, "complete receipt without runner failure detail")
        assert detail is not None
        exits = spec.command.infra_exit_codes if spec.command else ()
        # The released runner scrubs numbers from the stored diagnostic, including the exit code.
        agent_failure = trial.agent_claimed_success is False and any(
            detail == format_diagnostic(f"agent reported an infrastructure failure (exit {code})")
            for code in exits
        )
        # The parent can observe a boundary or event-sink failure even after a clean agent exit.
        boundary_failure = (
            detail
            in (
                "boundary exited before returning",
                "MCP server exited before the agent finished",
                "event sink failed",
                "invalid boundary protocol",
                "partial boundary protocol line",
                "boundary protocol line too long",
                "boundary protocol reader failed",
            )
            or re.fullmatch(r"[A-Za-z_]\w*(?:Error|Exception): .+", detail) is not None
        )
        require(
            (agent_failure or boundary_failure)
            and trial.failure_fingerprint == fingerprint("harness", detail),
            "complete receipt contradicts claimed infrastructure termination",
        )
    elif trial.outcome == Outcome.ERROR:
        raise Invalid("complete receipt without supporting infrastructure termination")


def response_calls(message: Obj) -> list[Obj]:
    calls: list[Obj] = []
    for item in rows(message.get("tool_calls", [])):
        function = obj(item.get("function"))
        calls.append(
            {"name": string(function.get("name")), "arguments": obj(function.get("arguments", {}))}
        )
    return calls


def verify_receipt(
    receipt: Obj,
    delivery: Delivery,
    reg: Registration,
    a: Assignment,
    ref: Reference,
    state: Obj,
    trial: TrialEnvelope,
    spec: TrialSpec,
    offline: bool,
) -> bool:
    for k, v in (
        ("run", a.run),
        ("key_id", reg.task["key_id"]),
        ("seed", trial.seed),
        ("arci_arm", trial.arm),
        ("arm", a.label),
        ("opening", a.opening),
    ):
        same(receipt[k], v, "wrong receipt " + k)
    complete = receipt["complete"]
    require(type(complete) is bool, "invalid receipt completion")
    require(
        complete is True or trial.termination.value != "completed",
        "completed trial has partial receipt",
    )
    if trial.termination.value == "timeout":
        require(
            trial.usage.wall_seconds >= spec.budgets.max_seconds,
            "timeout before wall budget expired",
        )
    received_calls = rows(receipt["calls"])
    history: list[Obj] = [
        {"role": "system", "content": reg.prompt},
        {"role": "user", "content": reg.task["ask"]},
    ]
    offset = 0

    attempted: list[Obj] = []
    names = {string(obj(t["function"])["name"]) for t in ref.tools}
    budget_hit = False

    def consume(function: Obj) -> None:
        nonlocal offset, budget_hit
        name = string(function["name"])
        call: Obj = {"name": name, "arguments": obj(function.get("arguments", {}))}
        attempted.append(call)
        if name not in names:
            text = message_text({"error": {"code": -32601, "message": f"unknown tool {name}"}})
            # A relay refusal is recorded. A pre-relay boundary refusal has no event.
            if offset < len(delivery.calls) and delivery.calls[offset] == call:
                same(delivery.texts[offset], text, "wrong recorded refusal")
                offset += 1
        elif offset >= spec.budgets.max_tool_calls:
            text = "arci: tool budget exceeded"
            budget_hit = True
        else:
            require(offset < len(delivery.calls), "sent history has unrecorded call")
            same(call, delivery.calls[offset], "sent call mismatch")
            text = delivery.texts[offset]
            offset += 1
        history.append({"role": "tool", "tool_name": name, "content": text})

    if a.opening != "none":
        first = obj(public_task(reg)["clean" if a.opening == "clean" else "bad"])
        history.append({"role": "assistant", "content": "", "tool_calls": [{"function": first}]})
        require(first["name"] in names, "unadvertised scripted opening")
        consume(first)
    exchanges = rows(receipt["exchanges"])
    require(
        1 <= len(exchanges) <= 8 and integer(receipt["steps"]) == len(exchanges),
        "wrong exchange count",
    )
    exhausted = False
    terminal = False
    pending = delivery.pending
    answer: JsonValue = None
    for step, exchange in enumerate(exchanges, 1):
        require(not terminal, "request after final answer")
        data = base64.b64decode(string(exchange["request_b64"]), validate=True)
        body_sha = digest(data)
        same(body_sha, exchange["sha256"], "request digest mismatch")
        if "receiver_sha256" in exchange:
            same(exchange.get("receiver_sha256"), body_sha, "receiver digest mismatch")
        # Every send persists the attempts made before it, including local refusals.
        same(received_calls[: len(attempted)], attempted, "receipt calls mismatch")
        same(
            parse(data),
            {
                "model": a.model,
                "messages": history,
                "tools": ref.tools,
                "stream": False,
                "think": False,
                "options": {"temperature": 0.7},
            },
            "sent body differs from independent history",
        )
        if exchange["response_b64"] is None:
            require(
                step > 1 and step == len(exchanges) and not complete and exchange["status"] is None,
                "missing response",
            )
            break
        response = base64.b64decode(string(exchange["response_b64"]), validate=True)
        status = integer(exchange["status"])
        # Offline receivers return their own digest in the response bytes. A failure
        # response can be a plain HTTP error page instead of JSON.
        try:
            payload = parse(response)
        except (ValueError, UnicodeError):
            if status == 200:
                raise
            payload = {}
        if "received_sha256" in payload:
            same(payload["received_sha256"], body_sha, "receiver response digest mismatch")
        elif offline and status == 200:
            raise Invalid("missing stand-in receiver digest")
        if status != 200:
            require(
                step > 1
                and step == len(exchanges)
                and 100 <= status <= 599
                and not complete
                and trial.termination.value == "harness_error"
                and trial.outcome == Outcome.ERROR,
                "unsuccessful chat response without documented later infrastructure error",
            )
            break
        same(payload.get("model"), a.model, "response model differs from requested model")
        require(payload.get("done") is True, "response done must be true")
        message = obj(payload["message"])
        require(message.get("role") == "assistant", "missing assistant response")
        history.append(message)
        try:
            functions = response_calls(message)
        except Invalid:
            require(
                1 < step == len(exchanges)
                and not complete
                and trial.termination.value == "harness_error"
                and trial.outcome == Outcome.ERROR
                and trial.agent_claimed_success is not True,
                "malformed tool_calls requires a later incomplete infrastructure ERROR",
            )
            break
        if not functions:
            terminal = True
            answer = message.get("content")
            if not isinstance(answer, str):
                require(
                    step == len(exchanges)
                    and not complete
                    and trial.outcome == Outcome.ERROR
                    and trial.termination.value == "harness_error",
                    "terminal response missing string content requires infrastructure ERROR",
                )
                answer = None
        else:
            for requested in functions:
                if not complete and step == len(exchanges) and offset == len(delivery.calls):
                    if pending is not None and (
                        requested["name"] == pending["name"] or string(requested["name"]) in names
                    ):
                        require(
                            offset < spec.budgets.max_tool_calls,
                            "unexpected incomplete call",
                        )
                        same(requested, pending, "unmatched start differs from final response call")
                        attempted.append(requested)
                        pending = None
                        break
                    if pending is None and len(attempted) >= len(received_calls):
                        break
                consume(requested)
            exhausted = step == 8
    require(offset == len(delivery.calls), "receipt omitted recorded calls")
    require(pending is None, "unmatched start absent from final response")
    same(
        received_calls,
        attempted if complete else attempted[: len(received_calls)],
        "receipt calls mismatch",
    )
    if not complete and (
        trial.termination.value == "harness_error" or delivery.pending is not None
    ):
        same(
            [receipt["answer"], state["answer"]],
            [None, None],
            "incomplete failure recorded an answer",
        )
    if complete:
        if trial.outcome != Outcome.ERROR:
            same(
                trial.termination.value == "budget", budget_hit, "call budget termination mismatch"
            )
        require(terminal or exhausted, "premature receipt completion")
        same(receipt["answer"], answer, "receipt contradicts final response")
        same(state["answer"], answer, "snapshot contradicts final response")
        verify_complete_termination(trial, spec)
    return complete is True and exhausted and answer is None


@dataclass
class Group:
    trials: int = 0
    passed: int = 0


def groups() -> dict[str, Group]:
    return {"yes": Group(), "no": Group()}


@dataclass
class Counts:
    trials: int = 0
    passed: int = 0
    failed: int = 0
    errored: int = 0
    by_termination: dict[str, int] = field(default_factory=dict[str, int])
    wall_timeouts: int = 0
    call_budget: int = 0
    step_exhausted: int = 0
    same_tool: dict[str, Group] = field(default_factory=groups)
    corrected_same_tool: dict[str, Group] = field(default_factory=groups)
    unscripted_exposed: int = 0
    unscripted_trials: int = 0

    def add(
        self,
        trial: TrialEnvelope,
        a: Assignment,
        reg: Registration,
        calls: Delivery,
        exhausted: bool,
    ) -> None:
        passed = trial.outcome == Outcome.PASS
        self.trials += 1
        self.passed += passed
        self.failed += trial.outcome == Outcome.FAIL
        self.errored += trial.outcome == Outcome.ERROR
        term = trial.termination.value
        self.by_termination[term] = self.by_termination.get(term, 0) + 1
        self.wall_timeouts += term == "timeout"
        self.call_budget += term == "budget"
        self.step_exhausted += exhausted
        if a.opening == "none":
            self.unscripted_trials += 1
            self.unscripted_exposed += calls.exposed
        else:
            opening = obj(public_task(reg)["clean" if a.opening == "clean" else "bad"])
            retries = [c for c in calls.forwarded[1:] if c["name"] == opening["name"]]
            good = {dump(c) for c in rows(reg.task["good"])}
            for group, yes in (
                (self.same_tool, bool(retries)),
                (self.corrected_same_tool, any(dump(c) in good for c in retries)),
            ):
                bucket = group["yes" if yes else "no"]
                bucket.trials += 1
                bucket.passed += passed

    def output(self) -> Obj:
        return asdict(self)


def pair_counts(pairs: dict[str, dict[str, Outcome]]) -> dict[str, int]:
    counts: dict[str, int] = dict.fromkeys(("minus", "zero", "plus", "errored"), 0)
    for sides in pairs.values():
        require(set(sides) == set(SIDES), "missing arm of pair")
        if Outcome.ERROR in sides.values():
            counts["errored"] += 1
        else:
            diff = int(sides["candidate"] == Outcome.PASS) - int(sides["baseline"] == Outcome.PASS)
            counts[("minus", "zero", "plus")[diff + 1]] += 1
    return counts


def load_schedule(
    store: Path, descriptor: Path | None, pin: str | None
) -> tuple[
    Manifest | SuiteManifest, GateDecision | SuiteDecision, list[TrialSpec], list[TrialEnvelope]
]:
    data = read(store / "manifest.json")
    trials = [TrialEnvelope.model_validate(row) for row in jsonl(store / "trials.jsonl")]
    require(all(t.validate_seal() for t in trials), "invalid trial seal")
    if data["schema_version"] == "arci-suite/1":
        manifest = SuiteManifest.model_validate(data)
        decision = SuiteDecision.model_validate(read(store / "decision.json"))
        require(
            suite_experiment_id(manifest) == manifest.experiment_id, "incorrect suite experiment ID"
        )
        require(1 <= decision.stopped_at_round <= manifest.max_rounds, "invalid stopping round")
        specs = [
            spec
            for r in range(1, decision.stopped_at_round + 1)
            for spec in build_suite_round(manifest, r)
        ]
        require(
            bool(decision.history) and decision.history[-1].round == decision.stopped_at_round,
            "incomplete suite history",
        )
        require(
            all(look.verdict.value == "INCONCLUSIVE" for look in decision.history[:-1]),
            "evidence continues past first decisive round",
        )
        require(
            decision.verdict.value != "INCONCLUSIVE"
            or decision.stopped_at_round == manifest.max_rounds,
            "inconclusive before registered cap",
        )
        result = decide_suite(manifest, trials)
        require(result == decision, "released suite decision mismatch")
    else:
        manifest = Manifest.model_validate(data)
        decision = GateDecision.model_validate(read(store / "decision.json"))
        specs = list(build_schedule(manifest))
        result = decide(manifest, trials)
        require(result == decision, "released plain decision mismatch")
    require(
        manifest.validate_seal() and decision.validate_seal(), "invalid manifest or decision seal"
    )
    if descriptor is None:
        descriptor = store / "descriptor.yaml"
        if not descriptor.is_file() and store.parent.name == "stores":
            # make_suites can name this clean.yaml, main.yaml or held.yaml.
            candidates = sorted(store.parent.parent.glob("*.yaml"))
            matches = [
                p
                for p in candidates
                if read(p).get(
                    "suite_id" if isinstance(manifest, SuiteManifest) else "experiment_id"
                )
                == (
                    manifest.suite_id
                    if isinstance(manifest, SuiteManifest)
                    else manifest.experiment_id
                )
            ]
            require(len(matches) == 1, "cannot identify detached descriptor; supply --descriptor")
            descriptor = matches[0]
    require(
        descriptor.is_file(), "missing descriptor.yaml; supply the detached file with --descriptor"
    )
    compiled = compile_run_descriptor(descriptor)
    require(
        compiled.record_sha256 == manifest.record_sha256,
        "descriptor differs from compiled manifest",
    )
    actual_pin = digest(descriptor.read_bytes())
    if pin is not None:
        require(actual_pin == pin, "descriptor byte digest mismatch")
    elif isinstance(manifest, SuiteManifest) and (STUDY / "descriptor-digests.sha256").is_file():
        pins = (STUDY / "descriptor-digests.sha256").read_text(encoding="utf-8").splitlines()
        require(
            any(line.split()[:1] == [actual_pin] for line in pins),
            "descriptor absent from published pins",
        )
    elif isinstance(manifest, SuiteManifest):
        require(
            all(
                arm.command and "--offline" in arm.command.argv
                for arm in (manifest.baseline, manifest.candidate)
            ),
            "deciding suite lacks independently published descriptor digest",
        )
    same(
        sorted(t.trial_id for t in trials),
        sorted(s.trial_id for s in specs),
        "duplicate, extra or missing scheduled trial",
    )
    return manifest, result, specs, trials


def verified_count(
    store: Path,
    receipts: Path,
    check_dir: Path,
    descriptor: Path | None = None,
    pin: str | None = None,
    edited: Path | None = None,
    publication: bool = False,
) -> tuple[Obj, str]:
    require(
        importlib.metadata.version("agent-reliability-ci") == "2.4.1",
        "requires released ARCI 2.4.1",
    )
    require(check_dir.is_dir(), "missing --check-dir")
    manifest, decision, specs, trials = load_schedule(store, descriptor, pin)
    publication = (
        publication
        or store.parent.name == "runs"
        or any((store / name).exists() for name in ("ledger.jsonl", "receipts.jsonl"))
        or any(
            not arm.command or "--offline" not in arm.command.argv
            for arm in (manifest.baseline, manifest.candidate)
        )
    )
    exports: dict[str, Counter[str]] = {}
    if publication:
        for name in ("ledger.jsonl", "receipts.jsonl"):
            require((store / name).is_file(), f"missing aggregate {name}")
            exports[name] = Counter(digest(dump(row).encode()) for row in jsonl(store / name))
    transcripts: dict[str, Obj] | None = None
    registered = registration()
    by_key = {string(r.task["key_id"]): r for r in registered.values()}
    by_id = {t.trial_id: t for t in trials}
    events: dict[tuple[str, int], Event] = {}
    for data in jsonl(store / "events.jsonl"):
        event = Event.model_validate(data)
        key = (event.trial_id, event.seq)
        require(key not in events, "duplicate exported event")
        events[key] = event
    seen: set[str] = set()
    pairs: dict[str, dict[str, Outcome]] = defaultdict(dict)
    total = {side: Counts() for side in SIDES}
    task_counts: dict[str, dict[str, Counts]] = {side: {} for side in SIDES}
    identities: set[tuple[str, str, str]] = set()
    refs: dict[str, Reference] = {}
    with ExitStack() as stack:
        for spec in specs:
            trial = by_id[spec.trial_id]
            try:
                for k in ("experiment_id", "task_id", "arm", "variant", "pair_id", "seed"):
                    same(getattr(trial, k), getattr(spec, k), "scheduled " + k + " mismatch")
                same(trial.spec_sha256, spec_sha256(spec), "scheduled spec hash mismatch")
                same(trial.condition_id, spec.condition.condition_id, "wrong condition")
                for event in trial.events:
                    require(event.trial_id == trial.trial_id, "embedded event trial mismatch")
                    exported = events.pop((event.trial_id, event.seq), None)
                    require(exported is not None, "missing exported event")
                    assert exported
                    same(
                        exported.model_dump(mode="json"),
                        event.model_dump(mode="json"),
                        "exported event differs",
                    )
                reg = by_key[string(spec.task["key_id"])]
                if isinstance(manifest, SuiteManifest):
                    same(spec.task_id, reg.task["id"], "suite task ID differs from registration")
                same(spec.task, public_task(reg), "task differs from registration")
                a = assignment(spec, manifest, reg)
                identities.add((a.model, reg.cell, a.phase))
                require(len(identities) == 1, "mixed cell, model or phase")
                state = obj(trial.final_state)
                ledger = rows(state["ledger"])
                # C0 has one independent seeded world at a time.
                with ExitStack() as trial_stack:
                    if reg.cell == "C0":
                        ref = Reference(trial_stack, reg, spec)
                    else:
                        if reg.cell not in refs:
                            refs[reg.cell] = Reference(stack, reg, spec)
                        ref = refs[reg.cell]
                    startup(ledger, spec, reg, a, ref, edited)
                    transcript = None
                    if a.opening == "bad" and reg.cell != "C0":
                        if transcripts is None:
                            transcripts = opening_transcript(check_dir)
                        transcript = transcripts.get(string(reg.task["id"]))
                    calls = delivery(trial, ledger, reg, a, ref, transcript)
                    key_bytes = json.dumps(
                        [a.run, reg.task["key_id"], spec.seed, spec.arm], separators=(",", ":")
                    ).encode()
                    name = digest(key_bytes) + ".json"
                    require(name not in seen, "receipt reused")
                    seen.add(name)
                    receipt = read(receipts / name)
                    exhausted = verify_receipt(
                        receipt,
                        calls,
                        reg,
                        a,
                        ref,
                        state,
                        trial,
                        spec,
                        bool(spec.command and "--offline" in spec.command.argv),
                    )
                    if publication:
                        for file, record in (
                            ("ledger.jsonl", {"trial_id": trial.trial_id, "ledger": ledger}),
                            ("receipts.jsonl", receipt),
                        ):
                            key = digest(dump(record).encode())
                            require(
                                exports[file][key] == 1,
                                f"missing, changed or repeated aggregate {file} row",
                            )
                            del exports[file][key]
                    expected = array(reg.task["expect"])
                    if reg.cell == "C0":
                        world = read(ref.directory / "state.json")
                        same(state["world"], world, "seeded world mismatch")
                        same(world["order_id"], reg.task["order_id"], "wrong order")
                        expected = [str(integer(obj(world["order"])["total_cents"]))]
                    else:
                        same(state["world"], None, "unexpected world")
                verify_grade(
                    trial, manifest.contract, state["answer"], expected, array(reg.task["decoys"])
                )
                pairs[spec.pair_id][spec.arm] = trial.outcome
                total[spec.arm].add(trial, a, reg, calls, exhausted)
                task_counts[spec.arm].setdefault(string(reg.task["id"]), Counts()).add(
                    trial, a, reg, calls, exhausted
                )
            except (KeyError, IndexError, ValueError, OSError) as exc:
                raise Invalid(f"{spec.trial_id}: {exc}") from exc
    require(not any(exports.values()), "extra aggregate ledger.jsonl or receipts.jsonl row")
    require(not events, "extra exported event")
    require(seen == {p.name for p in receipts.iterdir()}, "extra or missing receipt")
    require(len(identities) == 1, "empty schedule")
    model, cell, phase = identities.pop()
    counts = pair_counts(pairs)
    if isinstance(decision, SuiteDecision):
        cumulative = dict.fromkeys(counts, 0)
        for look in decision.history:
            by_round = {k: v for k, v in pairs.items() if k.startswith(f"r{look.round:06d}:")}
            for k, v in pair_counts(by_round).items():
                cumulative[k] += v
            same(cumulative, look.counts.model_dump(), "suite history pair counts mismatch")
        same(cumulative, counts, "pairs beyond stopping round")
        gate = subprocess.run(
            [sys.executable, "-I", "-B", "-m", "arci", "gate", str(store)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        require(
            any(line.strip() == "stored decision: MATCH" for line in gate.stdout.splitlines()),
            "released gate did not confirm MATCH",
        )
    arms: Obj = {}
    for side, label in zip(SIDES, (manifest.baseline.label, manifest.candidate.label), strict=True):
        if (
            total[side].by_termination.get("crash", 0)
            or total[side].wall_timeouts * 20 > total[side].trials
        ):
            print(
                f"{side} fails preregistration R3 (crash or over 5% wall timeouts)", file=sys.stderr
            )
        arms[side] = {
            "label": label,
            "all": total[side].output(),
            "by_task": {k: v.output() for k, v in task_counts[side].items()},
        }
    return {
        "experiment_id": manifest.experiment_id,
        "model": model,
        "cell": cell,
        "phase": phase,
        "pairs": dict(counts),
        "arms": arms,
    }, decision.verdict.value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("store", type=Path)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument(
        "--check-dir",
        type=Path,
        required=True,
        help="checker output directory; original replies are queried from the pinned servers",
    )
    parser.add_argument(
        "--descriptor",
        type=Path,
        help="detached descriptor (published stores contain descriptor.yaml)",
    )
    parser.add_argument(
        "--publication",
        action="store_true",
        help="require published aggregate and receiver evidence",
    )
    parser.add_argument("--descriptor-sha256", help="independently published descriptor digest")
    parser.add_argument("--edited", type=Path, help="registered edit root for confirmation")
    args = parser.parse_args()
    try:
        output, verdict = verified_count(
            args.store,
            args.receipts,
            args.check_dir,
            args.descriptor,
            args.descriptor_sha256,
            args.edited,
            args.publication,
        )
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        IndexError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"invalid count: {exc}", file=sys.stderr)
        return 1
    print("recomputed verdict:", verdict, file=sys.stderr)
    sys.stdout.buffer.write((dump(output) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
