"""Reply-0: check every registered task against the fixture and the real servers. No model.

    python3 -B check_tasks.py ENV_DIR OUT_DIR [FX_DIR]

ENV_DIR is the pinned environment (the directory named in ENVIRONMENT.md as `$ENV`). FX_DIR is
the fixture; it defaults to /Users/Shared/arci-reply0/fx, the registered path.
With REPLY0_NO_SANDBOX=1 the enclosing sandbox supplies network denial. This checks
all 72 tasks with read-only server calls, both F2 paths and the registered grader.
OUT_DIR receives the exact per-task evidence and checker inputs.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from contextlib import ExitStack, closing
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, NoReturn, cast

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

HARNESS = HERE.parent / "harness"
sys.path.insert(0, str(HARNESS))

from f2_parity import edited_entry, relay_result  # noqa: E402
from file_keys import SELECTORS, file_key  # noqa: E402
from harness.make_edited import build as build_edit  # noqa: E402
from harness.make_suites import descriptor, relay_argv, write_inputs  # noqa: E402
from harness.reply0_oracle import KEY_FILE, passed, snapshot  # noqa: E402
from probe import Server  # noqa: E402  (the probe's own stdio client)
from reply0_grade import normalise, passes  # noqa: E402

from arci.descriptor import compile_descriptor_text  # noqa: E402
from arci.schedule import build_schedule, spec_sha256  # noqa: E402
from arci.schema import TrialEnvelope  # noqa: E402

DENY = "(version 1)(allow default)(deny network*)"
PROTOCOL = "2025-11-25"
FIXTURE = "/Users/Shared/arci-reply0/fx"
Json = Any


def fail(message: str) -> NoReturn:
    raise SystemExit("CHECK FAILED: " + message)


def substitute(value: Json, fx: str) -> Json:
    if isinstance(value, str):
        return value.replace("{FX}", fx)
    if isinstance(value, list):
        return [substitute(v, fx) for v in cast(list[Json], value)]
    if isinstance(value, dict):
        return {k: substitute(v, fx) for k, v in cast(dict[str, Json], value).items()}
    return value


def git(repo: Path, *args: str) -> str:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(repo), "LC_ALL": "C",
           "TZ": "UTC", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}  # fmt: skip
    done = subprocess.run(
        ["git", "--no-optional-locks", *args],
        cwd=repo,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        fail(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout


def check_fixture(fx: Path) -> None:
    if hashlib.sha256((fx / "manifest.json").read_bytes()).hexdigest() != (
        "9c0f4a2dcfaf924b46228be3a0d8dfe2248517bf9039302c44103dc63f1a84ea"
    ):
        fail("unregistered fixture manifest")
    manifest = json.loads((fx / "manifest.json").read_text("utf-8"))
    for rel, digest in manifest["files"].items():
        if hashlib.sha256((fx / "files" / rel).read_bytes()).hexdigest() != digest:
            fail(f"fixture file {rel} differs from the manifest")
    head = git(fx / "repo", "rev-parse", "main").strip()
    if head != manifest["repo"]["branches"]["main"]:
        fail("fixture repository head differs from the manifest")
    if git(fx / "repo", "status", "--porcelain").strip():
        fail("fixture repository has uncommitted changes")


def check_source(task: Json, fx: Path) -> None:
    source = task["source"]
    if source["kind"] == "file_field":
        selector = SELECTORS[task["id"].split("-")[1]]
        path = fx / source["path"]
        if selector != source["selector"] or [file_key(path, selector)] != task["expect"]:
            fail(f"{task['id']}: registered answer differs from the selected fixture field")
        if str(path) != task["good"][-1]["arguments"]["path"]:
            fail(f"{task['id']}: wrong file source or scalar key")
    elif source["kind"] == "git_lines":
        lines = {line.strip() for line in git(fx / "repo", *source["args"]).splitlines() if line}
        if lines != set(task["expect"]):
            fail(f"{task['id']}: git gives {sorted(lines)}, the key says {task['expect']}")
    else:
        fail(f"{task['id']}: unknown source kind")


def fill(template: str, arguments: dict[str, Json]) -> str:
    def one(match: re.Match[str]) -> str:
        value = str(arguments[match.group(2)])
        return value.rsplit("/", 1)[0] if match.group(1) == "parent" else value

    return re.sub(r"\{(arg|parent):([A-Za-z_]+)\}", one, template)


def confinement() -> list[str]:
    return [] if os.environ.get("REPLY0_NO_SANDBOX") == "1" else ["sandbox-exec", "-p", DENY]


def commands(env_dir: Path, fx: Path) -> dict[str, tuple[list[str], dict[str, str]]]:
    base = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(env_dir / "home"),
            "LC_ALL": "C", "TZ": "UTC"}  # fmt: skip
    node = env_dir / "node/node_modules/@modelcontextprotocol/server-filesystem/dist/index.js"
    return {
        "filesystem": ([*confinement(), "node", str(node), str(fx / "files")], base),
        "git": (
            [*confinement(), str(env_dir / "py/bin/python"), "-m", "mcp_server_git",
             "--repository", str(fx / "repo")],
            {**base, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
             "PYTHONDONTWRITEBYTECODE": "1"},
        ),
    }  # fmt: skip


def text_of(result: Json) -> tuple[str, bool]:
    blocks = result.get("content") or []
    text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    return text, result.get("isError") is True


class Session:
    def __init__(self, command: list[str], env: dict[str, str]) -> None:
        self.server = Server(command, env, None, 20.0)
        _, reply, _, problem = self.server.request(
            "initialize",
            {"protocolVersion": PROTOCOL, "capabilities": {},
             "clientInfo": {"name": "reply0-check", "version": "0.1"}},
        )  # fmt: skip
        if problem or reply is None or "result" not in reply:
            fail(f"initialize: {problem}")
        self.info = reply["result"].get("serverInfo")
        self.server.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        _, reply, _, problem = self.server.request("tools/list", {})
        if problem or reply is None:
            fail(f"tools/list: {problem}")
        self.read_only = {
            tool["name"]
            for tool in reply["result"]["tools"]
            if (tool.get("annotations") or {}).get("readOnlyHint") is True
        }
        self.tools = [tool["name"] for tool in reply["result"]["tools"]]

    def result(self, call: Json) -> dict[str, Json]:
        if call["name"] not in self.read_only:
            fail(f"{call['name']} is not marked read-only by the server")
        _, reply, others, problem = self.server.request("tools/call", call)
        if problem or reply is None or "result" not in reply:
            fail(f"{call}: {problem or reply}")
        if others:
            fail(f"{call}: the server sent something else as well: {others}")
        return reply["result"]

    def close(self) -> None:
        self.server.stop()


def contains_key(text: str, key: str) -> bool:
    # Only the leakage/availability check searches prose. Grading uses exact lines.
    return re.search(rf"(?<!\w){re.escape(normalise(key))}(?!\w)", normalise(text)) is not None


def check_examples() -> None:
    examples = [
        ("260", ["260"], True),
        ("-260", ["260"], False),
        ("260.5", ["260"], False),
        ("1260", ["260"], False),
        ("1,260.", ["1260"], True),
        (".260", ["260"], False),
        ("main release-1", ["release-1"], False),
        ("release-1", ["release-1"], True),
        ("Bram de Wit, not Asha Verma", ["Bram de Wit"], False),
        ("It was not Bram de Wit.", ["Bram de Wit"], False),
        ("“BRAM de Wit.”", ["Bram de Wit"], True),
        ("release-1\nmain", ["main", "release-1"], True),
        ("main\nmain", ["main"], False),
    ]
    for answer, keys, wanted in examples:
        if passes(answer, keys, []) != wanted:
            fail(f"grader regression: {answer!r}")
        print(f"{'PASS' if wanted else 'FAIL'} {answer!r}")


def check_control(env_dir: Path, work: Path, task: Json, cell: Json) -> Json:
    task_file = work / "task.json"
    order = task["order_id"]
    opening = {"name": "lookup_order", "arguments": {"order_id": order}}
    if task["bad"] != opening or task["good"] != [opening] or order not in task["ask"]:
        fail(f"{task['id']}: order_id disagrees with the ask or opening")
    task_file.write_text(json.dumps({"order_id": order}))
    command = [
        *confinement(),
        str(env_dir / "py/bin/python"),
        "-P",
        "-m",
        "arci.mcp_toolset_server",
        "--toolset",
        "orderdesk_world:make_tools",
        "--seed",
        "0",
        "--workdir",
        str(work),
        "--task-file",
        str(task_file),
        "--tools",
        "lookup_order,check_stock",
    ]
    env = {
        "PATH": os.defpath,
        "HOME": str(env_dir / "home"),
        "PYTHONPATH": str(HERE.parent / "orderdesk"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    with closing(Session(command, env)) as session:
        if set(session.tools) != {"lookup_order", "check_stock"}:
            fail("orderdesk exposes tools outside the registered allowlist")
        session.read_only = {"lookup_order", "check_stock"}
        result = session.result(opening)
    text, error = text_of(result)
    world = json.loads((work / "state.json").read_text())
    key = [str(world["order"]["total_cents"])]
    if error or json.loads(text) != world["order"] or world["order_id"] != order:
        fail(f"{task['id']}: order lookup differs from snapshot")
    if any(contains_key(value, key[0]) for value in (cell["reply_as_given"], cell["sentence"])):
        fail(f"{task['id']}: control opening leaks the key")
    if not passes(key[0], key, []) or any(
        passes(a, key, []) for a in (text, cell["reply_as_given"], cell["sentence"])
    ):
        fail(f"{task['id']}: control grading")
    return {
        "cell": "C0",
        "set": "main",
        "id": task["id"],
        "seed": 0,
        "bad_call": opening,
        "original_result": result,
        "last_good_reply": text,
        "pasting_last_reply_passes": False,
    }


def check_parity(cell: Json, call: Json, raw: Json, edited: Session, rewrite: bool) -> None:
    delivered = relay_result(cell, call, raw)
    if (delivered != raw) != rewrite or edited.result(call) != delivered:
        fail(f"F2: complete edited and relay results disagree or wrong rewrite for {call}")


def check_protected_paths(fx: Path) -> None:
    for path in (KEY_FILE, HERE / "tasks.json"):
        for root in (fx / "files", fx / "repo"):
            if path.resolve().is_relative_to(root.resolve()):
                fail(f"answer material located in served root {root}")
            # A second name for a protected file inside a root is just as visible.
            if path.exists() and any(
                candidate.is_file() and path.samefile(candidate) for candidate in root.rglob("*")
            ):
                fail(f"{path.name} has an alias in a served root")
    print("check 10: key and task list outside both served roots; orderdesk exposes two lookups")


def parity_session(
    stack: ExitStack, work: Path, argv: list[str], key: str, label: str, rules: str, server: str
) -> Session:
    work.mkdir()
    task = work / "task.json"
    task.write_text(json.dumps({"key_id": key}))
    (work / "reply0-arm.json").write_text(
        json.dumps({"arm": label, "rules": rules, "server": server})
    )
    return stack.enter_context(
        closing(
            Session(argv, {**os.environ, "ARCI_WORKDIR": str(work), "ARCI_TASK_FILE": str(task)})
        )
    )


def check_server_edits(env_dir: Path, fx: Path, work: Path, doc: Json) -> None:
    for name in ("F1", "F2", "G1"):
        cell = doc["cells"][name]
        edits = work / "edited"
        built = build_edit(env_dir, edits, name)
        digests = json.loads((built / "digests.json").read_bytes())
        server = cell["server"]
        by_arm = relay_argv(env_dir, fx, name, server, [], edits)
        by_rule = relay_argv(env_dir, fx, name, server, ["naming"], None)
        count = rewrites = 0
        with ExitStack() as stack:
            named = parity_session(
                stack,
                work / (name + "-rule"),
                by_rule,
                name,
                "naming-sentence",
                "naming",
                "shipped",
            )
            package = parity_session(
                stack, work / (name + "-edit"), by_arm, name, "edited-server", "none", "edited"
            )
            shipped = parity_session(
                stack, work / (name + "-base"), by_arm, name, "server-as-shipped", "none", "shipped"
            )
            for session_dir, expected in (("-edit", "after"), ("-base", "before")):
                lines = (work / (name + session_dir) / "ledger.jsonl").read_text().splitlines()
                (start,) = [row for line in lines if (row := json.loads(line))["record"] == "start"]
                src = "server.py" if name == "G1" else "dist/server.js"
                key = "mcp_server_git/server.py" if name == "G1" else "server.js"
                if start["sha256"][key] != digests[expected][src]:
                    fail(f"{name}: running source disagrees with package digest")
            for task in cell["main"] + cell["held_out"]:
                bad, args = task["bad"], task["bad"]["arguments"]
                cases = [(bad, True), *((good, False) for good in task["good"])]
                if name == "F1":
                    cases += [
                        ({"name": "read_file", "arguments": args}, False),
                        (
                            {"name": bad["name"], "arguments": {"path": args["path"] + "-later"}},
                            True,
                        ),
                    ]
                elif name == "F2":
                    cases += [
                        ({"name": bad["name"], "arguments": {**args, "pattern": pattern}}, change)
                        for pattern, change in (
                            ("absent?.txt", False),
                            ("@(todo.txt|x)", False),
                            ("todo\n", False),
                            ("another-missing", True),
                        )
                    ]
                else:
                    cases += [
                        (
                            {
                                "name": bad["name"],
                                "arguments": {
                                    "repo_path": args["repo_path"],
                                    "end_timestamp": "1990-01-01",
                                },
                            },
                            False,
                        ),
                        (
                            {
                                "name": bad["name"],
                                "arguments": {**args, "start_timestamp": "29990101"},
                            },
                            True,
                        ),
                    ]
                    cases.append(
                        (
                            {
                                "name": bad["name"],
                                "arguments": {
                                    "repo_path": args["repo_path"],
                                    "end_timestamp": "1990-01-01",
                                    "start_timestamp": None,
                                },
                            },
                            False,
                        )
                    )
                for call, change in cases:
                    raw = shipped.result(call)
                    expected = deepcopy(raw)
                    if change:
                        sentence = fill(cell["sentence"], call["arguments"])
                        old = expected["content"][0]["text"]
                        expected["content"][0]["text"] = sentence
                        if expected.get("structuredContent", {}).get("content") == old:
                            expected["structuredContent"]["content"] = sentence
                    if (
                        (expected != raw) != change
                        or named.result(call) != expected
                        or (package.result(call) != expected)
                    ):
                        fail(f"{name}: complete-result parity for {call}")
                    count += 1
                    rewrites += change
        for suffix, wanted in (("-edit", 0), ("-base", 0), ("-rule", rewrites)):
            lines = (work / (name + suffix) / "ledger.jsonl").read_text().splitlines()
            calls = [r for line in lines if (r := json.loads(line))["record"] == "call"]
            if len(calls) != count or sum(r["rule"] is not None for r in calls) != wanted:
                fail(f"{name}: package/relay rewrite attribution")
        print(
            f"check 9 {name}: {count} complete results agree; {rewrites} matching calls", flush=True
        )


def pipe_trials(config: Json, work: Path, env: dict[str, str]) -> list[Json]:
    result: list[Json] = []
    manifest = compile_descriptor_text(json.dumps(config))
    for spec in build_schedule(manifest):
        trial = work / spec.arm
        trial.mkdir()
        (trial / "task.json").write_text(json.dumps(spec.task))
        (trial / "spec.json").write_text(spec.model_dump_json())
        assert spec.command
        (trial / "config.json").write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "env": {
                            "command": sys.executable,
                            "args": [
                                "-P",
                                str(HARNESS / "tests/core/pipe_boundary.py"),
                                str(trial / "spec.json"),
                                str(trial),
                            ],
                        }
                    }
                }
            )
        )
        argv = [
            s.replace("{task_file}", str(trial / "task.json")).replace(
                "{mcp_config}", str(trial / "config.json")
            )
            for s in spec.command.argv
        ]
        subprocess.run(
            argv,
            cwd=trial,
            env={
                **env,
                **spec.command.env,
                "ARCI_WORKDIR": str(trial),
                "ARCI_SEED": str(spec.seed),
            },
            stdin=subprocess.DEVNULL,
            check=True,
            timeout=120,
        )
        state = snapshot(dict(spec.task), str(trial))
        result.append(
            {
                "arm": spec.arm,
                "seed": spec.seed,
                "final_state": state,
                "recording": json.loads((trial / "recording.json").read_bytes()),
                "outcome": "PASS" if passed(dict(spec.task), state) else "FAIL",
            }
        )
    return result


def actual_trials(config: Json, work: Path, env: dict[str, str]) -> list[Json]:
    descriptor_path = work / "pair.yaml"
    descriptor_path.write_text(json.dumps(config))
    process = subprocess.run(
        [
            sys.executable,
            "-P",
            "-m",
            "arci",
            "run",
            "--workers",
            "1",
            "--out",
            str(work / "stores"),
            str(descriptor_path),
        ],
        env=env,
        cwd=HARNESS,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=270,
    )
    store = work / "stores" / config["experiment_id"]
    if not (store / "trials.jsonl").exists():
        fail(f"ARCI pair returned {process.returncode}: {process.stderr[-400:]}")
    trials = [
        TrialEnvelope.model_validate_json(row)
        for row in (store / "trials.jsonl").read_bytes().splitlines()
    ]
    if len(trials) != 2 or any(
        not t.validate_seal() or t.termination != "completed" for t in trials
    ):
        fail(f"ARCI pair incomplete: {[(t.termination, t.failure_detail) for t in trials]}")
    specs = {s.trial_id: s for s in build_schedule(compile_descriptor_text(json.dumps(config)))}
    for trial in trials:
        spec = specs.pop(trial.trial_id)
        if (trial.spec_sha256, trial.arm, trial.task_id, trial.seed, trial.pair_id) != (
            spec_sha256(spec),
            spec.arm,
            spec.task_id,
            spec.seed,
            spec.pair_id,
        ):
            fail("sealed trial disagrees with scheduled identity")
    if specs:
        fail("missing scheduled trial")
    return [trial.model_dump(mode="json") for trial in trials]


def exercise(
    env_dir: Path,
    fx: Path,
    work: Path,
    doc: Json,
    cell_id: str,
    task: Json,
    reference: Json,
    script: str,
    *,
    pipes: bool,
) -> None:
    plan = work / "plan.json"
    plan.write_text(
        json.dumps(
            {
                task["key_id"]: {
                    "script": script,
                    "good": task["good"],
                    "expect": task["expect"],
                    "world_key": "order.total_cents" if cell_id == "C0" else None,
                }
            }
        )
    )
    run = f"check-{task['id']}-{script}"
    config = descriptor(
        doc, env_dir, fx, cell_id, "main", "4B", [task], run=run, plain=True, plans=(plan, plan)
    )
    receipts = work / "receipts"
    env = {
        **os.environ,
        "PYTHONPATH": str(HARNESS),
        "REPLY0_RECEIPTS": str(receipts),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    trials = (pipe_trials if pipes else actual_trials)(config, work, env)
    all_receipts = [json.loads(path.read_bytes()) for path in receipts.glob("*.json")]
    if len(all_receipts) != 2 or {r["arci_arm"] for r in all_receipts} != {"baseline", "candidate"}:
        fail("missing or duplicate scheduled receipt")
    for trial in trials:
        side, state = trial["arm"], trial["final_state"]
        (receipt,) = [r for r in all_receipts if r["arci_arm"] == side]
        if (receipt["run"], receipt["key_id"], receipt["seed"], receipt["arm"]) != (
            run,
            task["key_id"],
            trial["seed"],
            config[side]["label"],
        ) or not receipt["complete"]:
            fail("wrong receipt identity or incomplete run")
        first = receipt["exchanges"][0]
        body = base64.b64decode(first["request_b64"], validate=True)
        if first["status"] != 200 or hashlib.sha256(body).hexdigest() != first["sha256"]:
            fail("wrong first-request receipt")
        calls = [r for r in state["ledger"] if r["record"] == "call"]
        records = [r for r in trial["recording"] if not r["tool"].startswith("rpc:")]
        actions = [task["bad"]] + ([] if script == "gives-up" else task["good"])
        if (
            receipt["calls"] != actions
            or [{"name": c["tool"], "arguments": c["arguments"]} for c in calls] != actions
            or len(records) != len(calls)
        ):
            fail("unexpected stand-in calls")
        raw = reference["original_result"]
        if calls[0]["server_reply"] != raw:
            fail("opening server result differs from fixture")
        expected = deepcopy(raw)
        expected.setdefault("isError", False)
        if side == "baseline" and cell_id != "C0":
            sentence = reference["sentence"]
            old = expected["content"][0]["text"]
            expected["content"][0]["text"] = sentence
            if expected.get("structuredContent", {}).get("content") == old:
                expected["structuredContent"]["content"] = sentence
        if calls[0]["passed_on"] != expected:
            fail("opening relay delivery differs from registered arm")
        text = text_of(expected)[0]
        injection = None
        if cell_id == "C0":
            expected["content"] = []
            injection = "empty_result"
            text = doc["cells"]["C0"]["sentence"] if side == "baseline" else ""
        if (
            records[0]["result"]["value"] != expected
            or records[0]["result"]["injected_by"] != injection
            or records[0]["occurrence"] != 0
        ):
            fail("wrong opening boundary recording")
        if json.loads(body)["messages"] != [
            {"role": "system", "content": doc["system_prompt"]},
            {"role": "user", "content": task["ask"]},
            {"role": "assistant", "content": "", "tool_calls": [{"function": task["bad"]}]},
            {"role": "tool", "tool_name": task["bad"]["name"], "content": text},
        ]:
            fail("model-facing opening differs")
        if any(
            r["result"]["injected_by"] is not None or r["result"]["value"] != c["passed_on"]
            for r, c in zip(records[1:], calls[1:], strict=True)
        ):
            fail("unexpected later delivery")
        wanted = script == "corrected" or (
            script == "paste" and reference["pasting_last_reply_passes"]
        )
        answers = {
            "corrected": str(state["world"]["order"]["total_cents"])
            if cell_id == "C0"
            else "\n".join(task["expect"]),
            "gives-up": "I could not find it.",
            "paste": reference["last_good_reply"],
        }
        if (
            state["answer"] != answers[script]
            or receipt["answer"] != state["answer"]
            or trial["outcome"] != ("PASS" if wanted else "FAIL")
        ):
            fail(f"{run}/{side}: incorrect final answer or grade")


def check_arms(env_dir: Path, fx: Path, out: Path, doc: Json, references: list[Json]) -> None:
    lookup = {row["id"]: row for row in references}
    pipes = os.environ.get("REPLY0_CHECK_TRANSPORT") == "stdio"
    evidence: list[Json] = []
    for cell_id, cell in doc["cells"].items():
        for task in cell["main"] + cell["held_out"]:
            for script in ("corrected", "gives-up", "paste"):
                with TemporaryDirectory(dir=out) as directory:
                    exercise(
                        env_dir,
                        fx,
                        Path(directory),
                        doc,
                        cell_id,
                        task,
                        lookup[task["id"]],
                        script,
                        pipes=pipes,
                    )
                evidence.append({"id": task["id"], "script": script, "arms_verified": 2})
        print(
            f"check 8 {cell_id}: {len(cell['main']) + len(cell['held_out'])} tasks"
            " x 3 scripts x 2 arms",
            flush=True,
        )
    (out / "standins.check.json").write_text(
        json.dumps({"transport": "stdio-components" if pipes else "arci-run", "cases": evidence})
        + "\n"
    )


def main(argv: list[str]) -> int:
    env_dir, out_dir = Path(argv[1]), Path(argv[2])
    fx = Path(argv[3]) if len(argv) > 3 else Path(FIXTURE)
    if fx.resolve() != fx:
        fail(f"the fixture path {fx} is not a real path")
    check_fixture(fx)
    check_examples()
    out_dir.mkdir(parents=True, exist_ok=True)
    document = substitute(json.loads((HERE / "tasks.json").read_text("utf-8")), str(fx))
    servers = commands(env_dir, fx)
    rows: list[Json] = []
    replies: dict[str, Json] = {}
    parity_openings = parity_later = 0
    for name, cell in document["cells"].items():
        tasks = [("main", t) for t in cell["main"]] + [("held_out", t) for t in cell["held_out"]]
        ids = [t["id"] for _, t in tasks]
        if len(set(ids)) != len(ids):
            fail(f"{name}: task ids repeat")
        if cell["server"] == "orderdesk":
            for _, task in tasks:
                with TemporaryDirectory(dir=out_dir) as directory:
                    rows.append(check_control(env_dir, Path(directory), task, cell))
            continue
        with ExitStack() as stack:
            command, env = servers[cell["server"]]
            session = stack.enter_context(closing(Session(command, env)))
            edited = None
            if name == "F2":
                work = Path(stack.enter_context(TemporaryDirectory(dir=out_dir)))
                entry = edited_entry(env_dir, work, cell)
                edited = stack.enter_context(
                    closing(Session([*confinement(), "node", str(entry), str(fx / "files")], env))
                )
            bucket = replies.setdefault(cell["server"], {"tools": session.tools, "replies": []})
            for part, task in tasks:
                check_source(task, fx)
                expect, decoys = task["expect"], task["decoys"]
                raw = session.result(task["bad"])
                bad_text, bad_error = text_of(raw)
                args = task["bad"]["arguments"]
                exact = {
                    "F1": f"ENOENT: no such file or directory, lstat '{args.get('path')}'",
                    "F2": "No matches found",
                    "G1": "Commit history:\n",
                    "G2": "Error executing tool git_branch: Invalid branch type: "
                    f"{args.get('branch_type')}",
                    "F0": "Input validation error: Invalid arguments for tool read_text_file: "
                    "path: Invalid input: expected string, received undefined",
                }[name]
                if bad_text != exact:
                    fail(f"{task['id']}: incorrect opening reply {bad_text!r}")
                if edited:
                    check_parity(cell, task["bad"], raw, edited, True)
                    parity_openings += 1
                    for pattern in ("absent?.txt", "@(todo.txt|missing.txt)", "todo\n"):
                        later = {"name": cell["tool"], "arguments": {**args, "pattern": pattern}}
                        check_parity(cell, later, session.result(later), edited, False)
                        parity_later += 1
                if not re.search(cell["reply_pattern"], bad_text):
                    fail(f"{task['id']}: the bad call's reply is {bad_text!r}")
                if bad_error is not cell["reply_is_error"]:
                    fail(f"{task['id']}: isError is {bad_error}")
                sentence = fill(cell["sentence"], task["bad"]["arguments"])
                for label, text in (("bad reply", bad_text), ("sentence", sentence)):
                    if any(contains_key(text, key) for key in expect):
                        fail(f"{task['id']}: the {label} holds a key string")
                    if passes(text, expect, decoys):
                        fail(f"{task['id']}: the {label} would pass as an answer")
                last = ""
                for good in task["good"]:
                    last, good_error = text_of(session.result(good))
                    if good_error:
                        fail(f"{task['id']}: a good call failed: {last!r}")
                if not all(contains_key(last, key) for key in expect):
                    fail(f"{task['id']}: the last good reply does not hold the key")
                if not passes("\n".join(expect), expect, decoys):
                    fail(f"{task['id']}: the bare key does not pass")
                paste = passes(last, expect, decoys)
                # A single-branch reply can already be the exact answer, with no decoy.
                plain_key = sorted(last.strip().splitlines()) == sorted(expect)
                if paste != plain_key or (paste and any(contains_key(last, d) for d in decoys)):
                    fail(f"{task['id']}: pasting extra server material would pass")
                rows.append({
                    "cell": name, "set": part, "id": task["id"], "bad_call": task["bad"],
                    "original_result": raw, "bad_reply": bad_text, "bad_is_error": bad_error,
                    "sentence": sentence,
                    "last_good_reply": last, "pasting_last_reply_passes": paste,
                })  # fmt: skip
                changed = [k for k, v in task["bad"]["arguments"].items()
                           if task["good"][0]["arguments"].get(k) != v]  # fmt: skip
                missing = [k for k in task["good"][0]["arguments"]
                           if k not in task["bad"]["arguments"]]  # fmt: skip
                kind = "missing" if cell["kind"] == "missing_required" else cell["kind"]
                bucket["replies"].append({
                    "id": f"{name}/{part}/{task['id']}", "tool": task["bad"]["name"],
                    "bad_call": kind, "what": f"cell {name}, {cell['kind']}",
                    "args": task["bad"]["arguments"],
                    "target": (missing or changed or [None])[0],
                    "is_error": bad_error, "protocol_error": False, "expect_error": True,
                    "text": bad_text, "structured": None, "duration_ms": 0,
                })  # fmt: skip

    paste_ids = {r["id"] for r in rows if r["pasting_last_reply_passes"]}
    if paste_ids != {"G2-b4-everything", "G2-b4-both"}:
        fail(f"unexpected full-reply paste set {sorted(paste_ids)}")
    check_protected_paths(fx)
    write_inputs(document)
    with TemporaryDirectory(dir=out_dir) as tmp:
        check_server_edits(env_dir, fx, Path(tmp).resolve(), document)
    check_arms(env_dir, fx, out_dir.resolve(), document, rows)
    check_fixture(fx)
    shown = json.dumps(rows, indent=1, ensure_ascii=False).replace(str(fx), "$FX")
    (out_dir / "tasks.check.json").write_text(shown + "\n", encoding="utf-8")
    for server, bucket in replies.items():
        (out_dir / f"registered-{server}.replies.json").write_text(
            json.dumps(bucket, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    for cell_id in document["cells"]:
        group = [r for r in rows if r["cell"] == cell_id]
        rejected = sum(not r["pasting_last_reply_passes"] for r in group)
        print(f"{cell_id}: {len(group)} bare keys pass; {rejected}/{len(group)} pastes rejected")
    print(
        f"F2: {parity_openings} scripted openings and {parity_later} later nonmatches "
        "agree on complete results"
    )
    print(f"all checks hold: {len(rows)} tasks; fixture unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
