"""Pushed-input preflight and durable wiring evidence for the Reply-0 launcher."""

from __future__ import annotations

import base64
import fcntl
import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, OpenerDirector, ProxyHandler, Request, build_opener

SHARED = Path("/Users/Shared/arci-reply0")
CLAIMS = Path(os.environ.get("REPLY0_CLAIMS", SHARED / "claims"))
CHECKOUT = SHARED / "checkout"
ROOT = Path(__file__).resolve().parents[1]
REG = "PREREGISTRATION-reply-0.draft.md"
LIST = "reply0-digests.sha256"
NOTE = "descriptor-digests.sha256"
REF = "refs/remotes/origin/v2/phase0"
FX = Path("/Users/Shared/arci-reply0/fx/manifest.json")
MODELS = {"4B": "qwen3.5:4b-mlx-ctx32k", "12B": "gemma4:12b-mlx-ctx32k"}
Row = dict[str, Any]
Transport = Callable[[int, bytes], tuple[int, bytes]]


def need(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def git(*args: str) -> bytes:
    return subprocess.check_output(
        ["/opt/homebrew/bin/git", "--no-optional-locks", "-C", str(ROOT), *args],
        stdin=subprocess.DEVNULL,
        timeout=15,
    )


def blob(commit: str, path: str) -> bytes:
    return git("cat-file", "blob", f"{commit}:./{path}")


def pinned_commit(file: str) -> str:
    if file == LIST:
        data = safe_file(CLAIMS, "push-receipt.txt").read_bytes()
        match = re.fullmatch(rb"([0-9a-f]{40}) refs/heads/v2/phase0\n?", data)
        need(match is not None, "invalid remote push receipt")
        assert match
        commit = match[1].decode("ascii")
        need(
            git("merge-base", commit, REF).decode().strip() == commit,
            "push receipt absent from origin tracking history",
        )
        return commit
    commit = git("log", "-1", "--format=%H", REF, "--", file).decode().strip()
    need(bool(re.fullmatch("[0-9a-f]{40}", commit)), f"{file} has no pushed commit")
    # Keep the existing push/fetch evidence requirement for the later descriptor note.
    for entry in git("reflog", "show", "--format=%H %gs", REF).decode().splitlines():
        tip, _, action = entry.partition(" ")
        published = action == "update by push" or action.startswith(("fetch ", "pull ", "clone:"))
        if published and git("merge-base", commit, tip).decode().strip() == commit:
            return commit
    raise ValueError(f"no push/fetch receipt for {file}")


def live_paths(study: Path, env: Path) -> None:
    need("REPLY0_CLAIMS" not in os.environ, "live claim directory override")
    home = Path.home().resolve()
    for path in (study, env):
        need(not path.resolve().is_relative_to(home), "live path under operator home")
    need(
        study.resolve() == CHECKOUT / "plan/exec/v2/study/reply-0"
        and env.resolve() == SHARED / "env",
        "unregistered live checkout or environment",
    )


def trial_binding(
    task: object, side: str, seed: int, label: str, opening: str, model: str, prompt: str
) -> str:
    fields = [task, side, seed, label, opening, model, prompt]
    return digest(json.dumps(fields, sort_keys=True, separators=(",", ":")).encode())


def authorize_trial(receipt: Row, task: object, model: str, prompt: str) -> None:
    """Only a launcher's scheduled child inherits the ephemeral suite capability."""
    need("REPLY0_CLAIMS" not in os.environ, "live claim directory override")
    token = os.environ.get("REPLY0_LAUNCH_TOKEN")
    need(bool(token), "live transport needs an active launcher claim")
    run = receipt["run"]
    need(re.fullmatch(r"reply0-[A-Za-z0-9-]+", run) is not None, "invalid live run")
    directory = CLAIMS / run
    need(
        Path(os.environ["REPLY0_RECEIPTS"]).resolve() == directory / "receipts",
        "receipt directory differs from claim",
    )
    with safe_file(CLAIMS, run + "/claim.json").open("rb") as file:
        try:
            fcntl.flock(file, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise ValueError("inactive launcher claim")
        claim = json.load(file)
        active = json.loads(safe_file(directory, "schedule.json").read_bytes())
        need(
            claim["run"] == run
            and active["run"] == run
            and active["token_sha256"] == digest(str(token).encode())
            and active["registration"] == claim["registration"]
            and claim["registration_sha256"] == active["registration_sha256"]
            and active["registration_sha256"] == digest(safe_file(ROOT, REG).read_bytes())
            and active["descriptor_sha256"]
            == digest(safe_file(ROOT, f"runs/{run}/descriptor.yaml").read_bytes()),
            "live claim binding differs",
        )
        key = trial_binding(
            task,
            receipt["arci_arm"],
            receipt["seed"],
            receipt["arm"],
            receipt["opening"],
            model,
            prompt,
        )
        need(key in active["trials"], "trial absent from claimed schedule")


def safe_file(root: Path, name: str) -> Path:
    rel = Path(name)
    need(
        name == rel.as_posix() and not rel.is_absolute() and ".." not in rel.parts,
        "unsafe relative path",
    )
    path = root / rel
    need(path.resolve() == path and path.is_file(), f"missing or linked input {name}")
    return path


def fixed_public() -> set[str]:
    paths = {
        REG,
        LIST,
        "DESIGN.md",
        "ENVIRONMENT.md",
        "fixture.py",
        "probe.py",
        "orderdesk/orderdesk_world.py",
        "orderdesk/task.json",
        "tasks/check/tasks.check.json",
        "projections/registered-rows.json",
        "harness/INTERFACE.md",
        "harness/DEVIATIONS.md",
        "harness/run-reply0.sh",
    }
    paths.update(
        f"tasks/{n}"
        for n in (
            "tasks.json",
            "make_tasks.py",
            "reply0_grade.py",
            "file_keys.py",
            "f2_parity.py",
            "check_tasks.py",
            "run_checkers.sh",
        )
    )
    paths.update(
        f"checkers/{n}" for n in ("feed_mcp_lint.mjs", "feed_mcp_linter.py", "verdicts.json")
    )
    for s in ("filesystem", "git"):
        paths.update(
            f"tasks/check/registered-{s}.{k}.json"
            for k in ("mcp-lint", "mcp-linter", "not-excused.mcp-linter")
        )
    paths.update(f"projections/plan-{k}.yaml" for k in ("8x15", "7x18", "6x20", "5x24"))
    paths.update(
        f"harness/{n}.py"
        for n in (
            "relay",
            "agent",
            "offline_model",
            "reply0_oracle",
            "make_suites",
            "clean_row",
            "suite_process",
            "wiring_check",
            "make_edited",
            "audit",
            "count_a",
            "count_b",
            "make_digests",
        )
    )
    paths.update(f"harness/edits/{c}.diff" for c in ("F1", "F2", "G1"))
    return paths


def required_inputs() -> set[str]:
    paths = fixed_public() - {LIST}
    paths.add("harness/answer_key.json")
    paths.update(
        f"harness/rules/{c}-{m}.json"
        for c in ("G1", "F1", "F2", "F0", "G2")
        for m in ("generic", "naming")
    )
    for folder in ("orderdesk", "tasks", "harness"):
        paths.update(
            p.relative_to(ROOT).as_posix()
            for p in (ROOT / folder).rglob("*")
            if p.is_file()
            and p.suffix != ".pyc"
            and not {"__pycache__", ".ruff_cache", ".pytest_cache"}.intersection(p.parts)
        )
    return paths


def entries(data: bytes) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in data.decode().splitlines():
        match = re.fullmatch(r"([a-f0-9]{64})  (.+)", line)
        need(match is not None, "malformed digest line")
        assert match is not None
        need(match[2] not in out, "duplicate digest entry")
        out[match[2]] = match[1]
    need(bool(out), "empty digest file")
    return out


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_list() -> str:
    pins = {p: digest(safe_file(ROOT, p).read_bytes()) for p in required_inputs()}
    pins[os.path.relpath(FX, ROOT)] = digest(FX.read_bytes())
    return "".join(f"{pins[p]}  {p}\n" for p in sorted(pins))


@dataclass(frozen=True)
class Registration:
    commit: str
    version: str
    models: dict[str, str]
    registration_sha256: str


def registration() -> Registration:
    commit = pinned_commit(LIST)
    raw = safe_file(ROOT, LIST).read_bytes()
    need(raw == blob(commit, LIST), "digest list differs from pushed list")
    pins = entries(raw)
    need(required_inputs().issubset(pins), "digest list omits required study inputs")
    source = os.path.relpath(FX, ROOT)
    need(
        pins.get(source) == "9c0f4a2dcfaf924b46228be3a0d8dfe2248517bf9039302c44103dc63f1a84ea",
        "fixture pin missing",
    )
    for name, sha in pins.items():
        if name == source:
            data = FX.read_bytes()
        else:
            data = safe_file(ROOT, name).read_bytes()
            need(data == blob(commit, name), f"{name} differs from pushed registration")
        need(digest(data) == sha, f"digest mismatch: {name}")
    reg = blob(commit, REG).decode("utf-8")
    version = re.search(r"(?i)\bOllama(?: version)?\s*:\s*`?(\d+\.\d+\.\d+)\b", reg)
    need(version is not None and "[fill at freeze" not in reg, "Ollama version not frozen")
    assert version is not None
    models: dict[str, str] = {}
    for key, name in MODELS.items():
        match = re.search(re.escape(name) + r"`?[,\s]+(?:sha256[ :]+)?`?([a-f0-9]{64})\b", reg)
        need(match is not None, f"full registered digest missing for {key}")
        assert match is not None
        models[key] = match[1]
    return Registration(commit, version[1], models, pins[REG])


def descriptor_note(reg: Registration) -> tuple[str, dict[str, str]]:
    commit = pinned_commit(NOTE)
    need(
        commit != reg.commit
        and git("merge-base", reg.commit, commit).decode().strip() == reg.commit,
        "descriptor note must follow registration",
    )
    data = safe_file(ROOT, NOTE).read_bytes()
    need(data == blob(commit, NOTE), "descriptor note differs from pushed note")
    pins = entries(data)
    for name, sha in pins.items():
        need(
            re.fullmatch(
                r"runs/reply0-(main|generic|confirmation)-(4B|12B)-(C0|G1|F2|F1|F0|G2)/descriptor\.yaml",
                name,
            )
            is not None,
            "unexpected descriptor note entry",
        )
        need(digest(safe_file(ROOT, name).read_bytes()) == sha, f"descriptor bytes differ: {name}")
    return commit, pins


NODE_SHA256 = "ee6fb0e015284d83a91e8ec5213f43a157f8a392b58555301682892ba928c04a"


def registered_node(env: Path) -> Path:
    binary = env.absolute() / "node/bin/node"
    need(binary.is_file() and os.access(binary, os.X_OK), "registered Node executable missing")
    with binary.open("rb") as stream:
        need(
            hashlib.file_digest(stream, "sha256").hexdigest() == NODE_SHA256, "Node digest differs"
        )
    return binary


def versions(env: Path) -> None:
    need(
        sys.version.split()[0] == "3.13.12"
        and Path(sys.prefix).resolve() == (env / "py").resolve(),
        "Python environment differs",
    )
    executables = {
        sys.executable: "95fb891ec36d4022bdf62172f9d3c757fb3c7b1669a274cacc87fe261a535b7e",
        "/opt/homebrew/bin/git": "9048038886ac36210fbb616b49b0707465f63683cb04e33a2013baf95f746938",
    }
    for name, registered in executables.items():
        need(
            bool(name) and digest(Path(name).read_bytes()) == registered,
            "runtime executable digest differs",
        )
    for package, want in (
        ("arci", "f231f01c357b48f9428db391018eb686b3ba0b34cd18f487055e3438ede13326"),
        ("mcp_server_git", "bbe6338fd73b97a272e70f580c750b3e20dbe949bdc1e0a80c3d0c2b37ab9b53"),
        ("node_modules", "34f117cd8cc12c1a77e6bff85be976b13486b71ff70a6a9a2461b55e51901f05"),
    ):
        if package == "node_modules":
            folder = env / "node/node_modules"
            pattern = "*"
        else:
            (folder,) = (env / "py/lib").glob("python*/site-packages/" + package)
            pattern = "*.py"
        sources = {
            p.relative_to(folder).as_posix(): digest(p.read_bytes())
            for p in folder.rglob(pattern)
            if p.is_file()
        }
        tree = digest(json.dumps(sources, sort_keys=True, separators=(",", ":")).encode())
        need(tree == want, package + " source digest differs")
    for package, want in (("agent-reliability-ci", "2.4.1"), ("mcp-server-git", "2026.11.18")):
        need(importlib.metadata.version(package) == want, f"{package} version differs")
    for cmd, expected in (
        ([str(registered_node(env)), "--version"], "v24.18.0"),
        (["/opt/homebrew/bin/git", "--version"], "git version 2.55.0"),
    ):
        need(
            subprocess.check_output(cmd, stdin=subprocess.DEVNULL, text=True, timeout=15).strip()
            == expected,
            " ".join(cmd) + " differs",
        )
    package = json.loads(
        (
            env / "node/node_modules/@modelcontextprotocol/server-filesystem/package.json"
        ).read_bytes()
    )
    need(package["version"] == "2.4.0", "filesystem version differs")
    need(
        digest((env / "node/package-lock.json").read_bytes())
        == "eed9ef81e41d799c76243af77bf6c1d97a013058ad95cd1008aa040fe52bd1a1",
        "node lock differs",
    )
    need(not list((env / "home").iterdir()), "server HOME must be empty")


def local_opener() -> OpenerDirector:
    class LocalOnly(HTTPRedirectHandler):
        def redirect_request(
            self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str
        ) -> None:
            raise HTTPError(req.full_url, code, msg, headers, fp)

    return build_opener(ProxyHandler({}), LocalOnly())


def warm_body(model: str) -> Row:
    return {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with OK."}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.7},
    }


def wiring_body(model: str, text: str) -> Row:
    call = {"name": "inspect_marker", "arguments": {}}
    return {
        "model": model,
        "options": {"temperature": 0.7},
        "stream": False,
        "think": False,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": call["name"],
                    "description": "Read a marker.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        "messages": [
            {"role": "system", "content": "Answer the user's question."},
            {"role": "user", "content": "What was the marker colour?"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": call}]},
            {"role": "tool", "tool_name": call["name"], "content": text},
        ],
    }


@dataclass(frozen=True)
class ProbeAdmission:
    directory: Path
    run: str
    model_key: str
    registration: Registration


PROBE: ContextVar[ProbeAdmission | None] = ContextVar("reply0_probe", default=None)


def authorize_probe(endpoint: str, body: bytes | None, step: int | None) -> None:
    admission = PROBE.get()
    if admission is None:
        raise ValueError("probe requires active suite admission")
    reg = admission.registration
    directory = admission.directory
    key = admission.model_key
    tag = MODELS[key]
    claim = json.loads(safe_file(CLAIMS, directory.name + "/claim.json").read_bytes())
    active = json.loads(safe_file(CLAIMS, "active-suite.json").read_bytes())
    need(
        directory.parent == CLAIMS
        and directory.name in (admission.run, admission.run + ".amendment")
        and claim["run"] == admission.run
        and claim["model"] == key
        and active["claim"] == directory.name
        and active["launcher"] == os.getpid()
        and claim["registration"] == reg.commit == pinned_commit(LIST)
        and claim["registration_sha256"]
        == reg.registration_sha256
        == digest(safe_file(ROOT, REG).read_bytes()),
        "probe claim, model or pushed registration differs",
    )
    for path in (CLAIMS / "suite.lock", directory / "claim.json"):
        with path.open("rb") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise ValueError("probe requires active suite and claim locks")
    plan: list[tuple[str, object, int | None]] = [
        ("version", None, None),
        ("tags", None, None),
        ("show", {"model": tag}, None),
        ("chat", warm_body(tag), 0),
        ("version", None, None),
        ("tags", None, None),
        ("ps", None, None),
    ]
    if admission.run == "reply0-wiring-" + key:
        plan.extend(("chat", wiring_body(tag, text), i) for i, text in enumerate(("violet", "")))
    # Exclusive creation consumes an ordinal even when opening the connection fails.
    position = len(list(directory.glob("probe-*.sent")))
    need(position < len(plan), "probe request ordinal exhausted")
    name, expected, ordinal = plan[position]
    expected_bytes = None if expected is None else json.dumps(expected).encode()
    need(
        (endpoint, body, step) == (name, expected_bytes, ordinal),
        "unregistered probe request or ordinal",
    )
    (directory / f"probe-{position}.sent").touch(exist_ok=False)


def probe_chat(step: int, body: bytes) -> tuple[int, bytes]:
    """Wiring and warm-up only, under the launcher's suite lock and consumed slot."""
    authorize_probe("chat", body, step)
    req = Request(
        "http://127.0.0.1:11434/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with local_opener().open(req, timeout=60) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()


def metadata(reg: Registration, key: str, *, loaded: bool = False) -> None:
    admission = PROBE.get()
    need(
        admission is not None and (admission.registration, admission.model_key) == (reg, key),
        "metadata model or registration differs from probe admission",
    )
    opener = local_opener()

    def get(endpoint: str, body: Row | None = None) -> Row:
        data = json.dumps(body).encode() if body else None
        req = Request(
            "http://127.0.0.1:11434/api/" + endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        authorize_probe(endpoint, data, None)
        with opener.open(req, timeout=8) as reply:
            return json.load(reply)

    need(get("version")["version"] == reg.version, "Ollama version differs")
    tag = MODELS[key]
    need(
        [m["digest"] for m in get("tags")["models"] if m["name"] == tag] == [reg.models[key]],
        "model digest differs",
    )
    if loaded:
        need(
            [(m["digest"], m["context_length"]) for m in get("ps")["models"] if m["name"] == tag]
            == [(reg.models[key], 32768)],
            "loaded context or digest differs",
        )
    else:
        params = get("show", {"model": tag})["parameters"]
        need(
            re.findall(r"(?m)^num_ctx\s+(\d+)\s*$", params) == ["32768"],
            "registered model context differs",
        )


def assistant_response(raw: bytes, model: str) -> None:
    response = json.loads(raw)
    need(isinstance(response, dict), "expected a chat response object")
    need(response.get("model") == model, "chat response model differs")
    need(response.get("done") is True, "chat response is unfinished")
    message = response.get("message")
    need(isinstance(message, dict) and message.get("role") == "assistant", "no assistant message")


def warm(model: str, send: Transport, failure_path: Path | None = None) -> None:
    payload = warm_body(model)
    status, body = send(0, json.dumps(payload).encode())
    try:
        need(status == 200, f"warm-up HTTP {status}")
        assistant_response(body, model)
    except ValueError as exc:
        if failure_path is None:
            raise ValueError(f"warm-up failed: {exc}", body) from exc
        failure_path.write_bytes(body)
        raise


def wiring(model: str, send: Transport, save: Callable[[list[Row]], None]) -> list[Row]:
    records: list[Row] = []
    for index, text in enumerate(("violet", "")):
        payload = wiring_body(model, text)
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        status = None
        answer = b""
        problem = None
        try:
            status, answer = send(index, body)
            if status == 200:
                assistant_response(answer, model)
                received = True
            else:
                received = isinstance(json.loads(answer).get("message"), dict)
        except (OSError, ValueError, AttributeError) as exc:
            received = False
            problem = str(exc)
        records.append(
            {
                "text": text,
                "status": status,
                "message": received,
                "response_b64": base64.b64encode(answer).decode(),
                "problem": problem,
            }
        )
        save(records)
        if status == 200 and not received:
            raise ValueError(f"invalid wiring response: {problem}")
    return records


def fallback(rows: list[Row], model: str) -> bool:
    need(len(rows) == 2 and [r["text"] for r in rows] == ["violet", ""], "incomplete wiring")
    for row in rows:
        raw = base64.b64decode(row["response_b64"], validate=True)
        if row["status"] == 200:
            assistant_response(raw, model)
            received = True
        else:
            try:
                received = isinstance(json.loads(raw).get("message"), dict)
            except (ValueError, AttributeError):
                received = False
        need(received is row["message"], "wiring message flag disagrees with response")
    need(rows[0]["status"] == 200 and rows[0]["message"] is True, "non-empty wiring failed")
    second = rows[1]
    if second["status"] == 200 and second["message"] is True:
        return False
    raw = base64.b64decode(second["response_b64"], validate=True).decode("utf-8", "replace")
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = None
    reason = parsed.get("error") if isinstance(parsed, dict) else raw
    rejection = re.compile(
        r"\b(?:empty(?: (?:tool|message|response|content|text|result))*"
        r" (?:is |are |was )?(?:rejected|invalid|not allowed|not supported)"
        r"|(?:tool (?:message|result|response)(?: content)?|message content|content|text)"
        r" (?:must not|cannot|can't) be empty"
        r"|(?:reject(?:ed)?|unsupported|invalid) empty "
        r"(?:tool (?:response|result|message)|content|text))\b",
        re.IGNORECASE,
    )
    need(
        second["status"] in (400, 422)
        and second["message"] is False
        and isinstance(reason, str)
        and rejection.search(reason) is not None,
        "inconclusive empty-text wiring",
    )
    return True
