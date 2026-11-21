"""Read private CLI JSONL. Only top-level CLI diagnostics can attribute a termination."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypeGuard

from grade import AGENT_PYTHON, Grade

DEVELOPER = Path("/Users/ajay/Developer")
PROJECT = DEVELOPER / "agent-reliability-ci"
WORKTREES = DEVELOPER / ".arci-worktrees"
SERVICE = {
    "quota": r"quota|usage.?limit|out of credits|insufficient.?credits",
    "rate": r"rate.?limit|throttl|too many requests|\b429\b",
    "auth": r"authenticat|unauthori[sz]ed|forbidden|invalid.?api.?key|not logged in|\b40[13]\b",
    "server": r"\b5\d\d\b|internal.?server.?error|service.?unavailable|server.?overloaded",
    "retry": r"retries exhausted|exhausted.*retr|retry limit|max(?:imum)?.*retr|retry.*exhaust",
    "transport": r"transport|network|connection|disconnect|dns|error sending request|"
    r"timed? ?out|broken pipe|stream.?closed|reconnecting|failed to connect",
}
CLI_ERRORS = {
    "error",
    "turn.failed",
    "stream_error",
    "stream.error",
    "retry",
    "turn.retrying",
    "refusal",
    "turn.refused",
}
REFUSAL = re.compile(
    r"\b(?:refus(?:al|ed|ing)|request (?:declined|denied)|"
    r"(?:cannot|can['\u2019]t|unable to|not able to) (?:assist|help|comply|fulfil|proceed|"
    r"continue|do (?:this|that)|complete (?:this|the|your) (?:task|request|work|change))|"
    r"(?:usage|rate|credit|quota) (?:limit (?:reached|exceeded)|exhausted)|"
    r"(?:hit|reached|exceeded) (?:your |my |the )?(?:usage limit|quota|rate limit)|"
    r"quota exceeded|insufficient_quota|out of credits|too many requests|"
    r"authentication failed|service unavailable|internal server error|"
    r"rate limited|(?:quota|usage limit) has been exceeded|"
    r"HTTP (?:429|503)(?=\s*[:.,-]?\s*(?:too many requests|service unavailable)))\b",
    re.I,
)
META = {"thread.started", "turn.started", "turn.completed"}
REMOTE = re.compile(
    r"(?:^|[^\w])(?:mcp(?:__|[._-](?:tool|server|resource))|web(?:__|[._-](?:search|run|fetch))"
    r"|session[._-](?:history|lookup|search)|memory[._-](?:query|recent)|search_sessions)",
    re.I,
)
DENIAL = re.compile(
    r"permission denied|operation not permitted|access denied|blocked by sandbox|"
    r"no such file or directory|not a git repository|network is unreachable|"
    r"could not resolve host|command not found|sandbox denied",
    re.I,
)
PATHLIKE = re.compile(r"""(?:~|\$\{?\w+\}?|(?:\.{0,2}/)|[\w.-]+/)[^\s"'<>|;&(),\[\]{}]*""")
VARIABLE = re.compile(r"\$\{(\w+)\}|\$(\w+)")
GIT_READ = re.compile(
    r"(?:^|[/\s])git\s+(?!diff\s+--no-index\b)(?:[^;&|]*?\s)?"
    r"(?:-C|--git-dir(?:=|\s)|show|log|cat-file|rev-list|rev-parse|ls-tree|"
    r"blame|reflog|diff|status|archive|checkout|restore|grep|fetch|clone)\b"
)
NETWORK = re.compile(
    r"(?:^|[/\s;&|])(?:curl|wget|ssh|scp|gh|nc|nslookup|dig)\s|"
    r"https?://|urllib\.request|requests\.(?:get|post)|socket\.create_connection"
)


@dataclass
class Audit:
    status: Literal["clean", "outside_read", "unauditable"] = "clean"
    sha256: str | None = None
    event_ids: list[str] = field(default_factory=list)
    outside_events: list[str] = field(default_factory=list)
    denied_events: list[str] = field(default_factory=list)
    invalid_events: list[str] = field(default_factory=list)


def service_marker(diagnostic: str) -> str | None:
    return next((k for k, pat in SERVICE.items() if re.search(pat, diagnostic, re.I)), None)


@dataclass
class Evidence:
    audit: Audit = field(default_factory=Audit)
    last: str = ""
    diagnostic: str = ""
    terminal_id: str = ""
    active_items: set[str] = field(default_factory=set)
    worked: bool = False
    failed_id: str = ""
    refused_id: str = ""
    service: str | None = None
    service_id: str = ""

    def refusal(self, ref: str) -> None:
        # A previous transient retry cannot attribute a later ambiguous refusal.
        if not self.refused_id and not self.failed_id:
            self.service, self.service_id, self.refused_id = None, "", ref

    def cli_diagnostic(self, event: dict[str, Any], kind: str, ref: str) -> None:
        if self.failed_id:
            return
        if kind == "turn.failed":
            self.failed_id = ref
        if self.refused_id:
            return
        error = event.get("error")
        origin = error.get("source") if isinstance(error, dict) else None
        if (origin or event.get("source")) in ("tool", "command_execution", "tool_output"):
            if kind == "turn.failed":
                self.service, self.service_id = None, ""
            return
        self.diagnostic = json.dumps(
            {
                k: event[k]
                for k in (
                    "error",
                    "message",
                    "code",
                    "status_code",
                    "refusal",
                    "reason",
                    "finish_reason",
                    "status",
                )
                if k in event
            }
        )
        service = service_marker(self.diagnostic)
        if kind in {"retry", "turn.retrying"} and service is None:
            service = "retry"
        if service:
            self.service, self.service_id = service, ref
            if service in {"quota", "auth"} or kind in {"refusal", "turn.refused"}:
                self.refused_id = ref
        elif kind in {"refusal", "turn.refused"} or REFUSAL.search(self.diagnostic):
            self.refusal(ref)


def strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def expand(value: str, env: Mapping[str, str]) -> str:
    value = VARIABLE.sub(lambda m: env.get(m[1] or m[2], m[0]), value)
    if value == "~" or value.startswith("~/"):
        return env.get("HOME", str(Path.home())) + value[1:]
    return value


def within(path: str, root: Path) -> bool:
    base = str(root).casefold()
    return path == base or path.startswith(base + "/")


@dataclass
class Operands:
    tree: Path
    work: Path
    unresolved: bool = False

    def outside(self, value: str, cwd: Path | None, env: Mapping[str, str]) -> bool:
        if not value:
            return False
        raw = expand(value, env)
        if "\x00" in raw or VARIABLE.search(raw) or raw.startswith("~"):
            self.unresolved = True
            return False
        path = Path(raw)
        if cwd is None and not path.is_absolute():
            self.unresolved = True
            return False
        return forbidden(cwd / path if cwd else path, self.tree, self.work)


def forbidden(candidate: Path, tree: Path, work: Path) -> bool:
    path = Path(os.path.normpath(candidate))
    name = str(path).casefold()
    if ".git" in Path(name).parts or re.search(r"/(?:site|dist)-packages/arci(?:/|$)", name):
        return True
    if not within(name, tree) and re.search(r"/\.(?:claude|codex)(?:/|$)", name):
        return True
    try:
        resolved = candidate.resolve()
    except (RuntimeError, OSError, ValueError):
        resolved = path
    runtime = (
        AGENT_PYTHON.parent.parent,
        AGENT_PYTHON.resolve().parents[1],
        Path("/usr/bin"),
        Path("/usr/lib"),
        Path("/bin"),
        Path("/sbin"),
        Path("/dev"),
        Path("/System/Library"),
        Path("/Library/Apple"),
        Path("/etc"),
        Path("/private/etc"),
    )
    # Outside project operands, including paths without a recognizable suffix,
    # are reviewable even when the other copy is stored under an unexpected name.
    for p in (path, resolved):
        name = str(p).casefold()
        if ".git" in Path(name).parts or re.search(r"/(?:site|dist)-packages/arci(?:/|$)", name):
            return True
        if within(name, tree) or within(name, AGENT_PYTHON.parent.parent):
            continue
        if any(within(name, root) for root in (PROJECT, WORKTREES, work)):
            return True
        if not any(within(name, root) for root in runtime):
            return True  # Other external file or directory operand.
    return False


def paths_in(text: str, cwd: Path | None, paths: Operands, env: Mapping[str, str]) -> bool:
    expanded = expand(text, env)
    try:
        words = shlex.split(expanded)
    except ValueError:
        words = []
    candidates = [w for w in words if w.startswith(("/", "./", "../", "~/"))]
    candidates.extend(m.group().rstrip(":.") for m in PATHLIKE.finditer(expanded))
    return any(paths.outside(p, cwd, env) for p in candidates if p)


def search_files(words: list[str]) -> list[str]:
    """Separate rg/grep search expressions from their actual file operands."""
    need_pattern = "--files" not in words
    file_value = False
    skip = False
    literal = False
    paths: list[str] = []
    for word in words[1:]:
        if file_value:
            paths.append(word)
            file_value = False
        elif skip:
            skip = False
        elif not literal and word == "--":
            literal = True
        elif not literal and word in {"-e", "--regexp"}:
            need_pattern, skip = False, True
        elif not literal and word in {"-g", "--glob", "-t", "--type", "-A", "-B", "-C", "-m"}:
            skip = True
        elif not literal and word in {"-f", "--file", "--ignore-file", "--pre"}:
            # The next value is a file the search process will read.
            file_value = True
            if word in {"-f", "--file"}:
                need_pattern = False
        elif not literal and word.startswith(("--regexp=", "-e")):
            need_pattern = False
        elif not literal and word.startswith(("--file=", "--ignore-file=", "--pre=")):
            paths.append(word.split("=", 1)[1])
            if word.startswith("--file="):
                need_pattern = False
        elif not literal and word.startswith("-f"):
            paths.append(word[2:])
            need_pattern = False
        elif not literal and word.startswith("-"):
            continue
        elif need_pattern:
            need_pattern = False
        else:
            paths.append(word)
    return paths


def resolved_directory(path: Path) -> Path | None:
    if not path.is_absolute():
        return None
    try:
        resolved = path.resolve(strict=True)
        return resolved if resolved.is_dir() else None
    except (ValueError, RuntimeError, OSError):
        return None


def command_access(command: str, cwd: Path | None, paths: Operands, env: dict[str, str]) -> bool:
    # CLI command executions often wrap their actual command in a login shell.
    try:
        words = shlex.split(command)
    except ValueError:
        words = []
    if len(words) >= 3 and Path(words[0]).name in {"zsh", "bash", "sh"} and "c" in words[1]:
        command = words[2]
    for segment in re.split(r"&&|\|\||[;\n|]", command):
        try:
            words = shlex.split(segment)
        except ValueError:
            words = segment.split()
        if not words:
            continue
        if words[0] in {"export", "env"}:
            words = words[1:]
        while words and re.match(r"^\w+=", words[0]):
            key, value = words.pop(0).split("=", 1)
            env[key] = expand(value, env)
        if not words:
            continue
        # Literal output and comments are not evidence of a read.
        if words[0] in {"echo", "printf", "#"} and not re.search(r"[<`]|\$\(", segment):
            continue
        if Path(words[0]).name in {"rg", "grep"} and not re.search(r"[<`]|\$\(", segment):
            if any(paths.outside(w, cwd, env) for w in search_files(words) or ["."]):
                return True
            continue
        if words[0] in {"cd", "pushd"} and len(words) > 1:
            if paths.outside(words[1], cwd, env):
                return True
            dest = Path(expand(words[1], env))
            cwd = resolved_directory(cwd / dest if cwd else dest)
            if cwd:
                env["PWD"] = str(cwd)
            else:
                env.pop("PWD", None)
            continue
        if cwd is None and (
            re.search(r"\$\(|`|\b(?:open|Path)\(", segment)
            or Path(words[0]).name in {"pytest", "make"}
        ):
            paths.unresolved = True  # An implicit or computed operand may depend on cwd.
        operands = words if "/" in words[0] else words[1:]
        if Path(words[0]).name in {"ls", "find", "tree", "du"} and not any(
            not w.startswith("-") for w in operands
        ):
            operands = [*operands, "."]
        if (
            words[0] == "arci"  # No project console script in the dependency-only environment.
            or GIT_READ.search(segment)
            or NETWORK.search(segment)
            or REMOTE.search(segment)
            or re.search(r"\bcodex\s+(?:resume|fork)\b", segment)
            or paths_in(segment, cwd, paths, env)
            or any(
                paths.outside(w, cwd, env)
                for w in operands
                if not w.startswith("-") and len(w) < 1024 and not re.search(r"[()\n]", w)
            )
        ):
            return True
    return False


def nonempty(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and bool(value.strip()) and "\x00" not in value


@dataclass(frozen=True)
class Access:
    hit: bool
    denied: bool
    auditable: bool
    work: bool


def access(item: dict[str, Any], tree: Path, work: Path, env: dict[str, str]) -> Access:
    kind = str(item.get("type", ""))
    tool = str(item.get("tool_name") or item.get("tool") or item.get("name") or kind)
    args = item.get("arguments", item.get("input", {}))
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = None
    valid = isinstance(args, dict)
    if not isinstance(args, dict):
        args = {}
    overrides = args.get("env", item.get("env", {}))
    if isinstance(overrides, dict) and all(isinstance(v, str) for v in overrides.values()):
        env = env | overrides
    else:
        valid = False
    env = env.copy()
    env.pop("PWD", None)  # The agent launch directory does not establish the tool's cwd.
    fields = item | args
    directory = fields.get("workdir", fields.get("cwd"))
    cwd = None
    paths = Operands(tree, work)
    outside_directory = False
    if nonempty(directory):
        expanded = expand(directory, env)
        if Path(expanded).is_absolute() and not VARIABLE.search(expanded):
            outside_directory = paths.outside(expanded, None, env)
            cwd = resolved_directory(Path(expanded))
            if cwd:
                env["PWD"] = str(cwd)
    command = item.get("command") or item.get("cmd") or args.get("cmd") or args.get("command") or ""
    cmd = command if isinstance(command, str) else ""
    if isinstance(command, list) and command and all(nonempty(w) for w in command):
        cmd = shlex.join(command)
    wrapper = kind in {"tool_call", "function_call", "custom_tool_call"}
    name = tool if wrapper else kind
    concrete_work = False
    if name in {"command_execution", "exec_command"}:
        concrete_work = nonempty(cmd)
        valid &= concrete_work
        valid &= all(
            isinstance(fields[k], str)
            for k in ("aggregated_output", "stdout", "stderr")
            if k in fields
        )
        code = fields.get("exit_code")
        valid &= code is None or type(code) is int
    elif name == "file_change":
        changes = fields.get("changes")
        concrete_work = (
            isinstance(changes, list)
            and bool(changes)
            and all(
                isinstance(c, dict)
                and nonempty(c.get("path"))
                and c.get("kind") in ("add", "update", "delete")
                for c in changes
            )
        )
        valid &= concrete_work
    elif name in {"read_file", "file_read"}:
        valid &= nonempty(fields.get("file_path") or fields.get("path"))
    elif name == "file_search":
        valid &= nonempty(fields.get("query") or fields.get("pattern"))
        paths.outside(str(fields.get("path", ".")), cwd, env)
    elif name in {"web_search", "web_search_call"}:
        valid &= nonempty(fields.get("query"))
    elif name == "mcp_tool_call":
        valid &= nonempty(item.get("server")) and nonempty(item.get("tool")) and "arguments" in item
    else:
        valid = False
    if wrapper and not ("arguments" in item or "input" in item):
        valid = False
    hit = (
        bool(REMOTE.search(tool) or REMOTE.search(kind))
        or outside_directory
        or command_access(cmd, cwd, paths, env.copy())
    )
    operands = {
        k: v
        for k, v in (item | args).items()
        if k
        not in {
            "command",
            "cmd",
            "arguments",
            "env",
            "input",
            "aggregated_output",
            "stdout",
            "stderr",
            "output",
            "result",
            "error",
            "text",
            "message",
            "type",
            "id",
            "name",
            "tool_name",
            "tool",
            "cwd",
            "workdir",
            "server",
            "query",
            "pattern",
            "changes",
            "status",
            "exit_code",
        }
    }
    changes = fields.get("changes")
    if isinstance(changes, list):
        operands["changed_paths"] = [c.get("path") for c in changes if isinstance(c, dict)]
    for raw in strings(operands):
        if paths.outside(raw, cwd, env) or paths_in(raw, cwd, paths, env):
            hit = True
    if args.get("text") and command_access(str(args["text"]), cwd, paths, env.copy()):
        hit = True
    output = "\n".join(
        strings(
            [
                item.get(k)
                for k in ("aggregated_output", "stdout", "stderr", "output", "result", "error")
            ]
        )
    )
    # A traceback, source match or listing can reveal an indirect project read.
    # A printed path in an otherwise unrelated banner is insufficient.
    listing = bool(
        re.search(
            r"(?:^|[\s/])(?:ls|find|realpath|readlink)(?:\s|$)|"
            r"(?:rg|grep)\s+(?:--files(?:-with-matches)?|-l)\b|__file__|inspect\.",
            cmd,
        )
    )
    for line in output.splitlines():
        # rg/file:line results contain arbitrary source text after the location.
        # Scanning that text as a file operand would count innocent local searches.
        trace = re.search(r'^\s*File ["\x27]([^"\x27]+)["\x27]', line)
        location = re.match(r"^([^:]+):\d+(?::|$)", line)
        opened = re.match(r"^(?:reading|opened|loaded)\s+(.+)$", line, re.I)
        if trace or location or opened:
            match = trace or location or opened
            assert match is not None
            if paths.outside(match[1].strip(), cwd, env):
                hit = True
        elif DENIAL.search(line) or (listing and not re.match(r"^\w+[ :]+", line)):
            if paths_in(line, cwd, paths, env):
                hit = True
    failed = (
        item.get("status") in ("failed", "denied")
        or item.get("exit_code") not in (None, 0)
        or bool(item.get("error"))
    )
    denied = item.get("status") == "denied" or (
        failed
        and bool(output.strip())
        and all(DENIAL.search(line) for line in output.splitlines() if line.strip())
    )
    if re.search(r"&&|\|\||[;\n|]", cmd) and item.get("status") != "denied":
        denied = False  # A later failure cannot clear an earlier command.
    return Access(hit, bool(denied), valid and not paths.unresolved, valid and concrete_work)


def inspect_stream(log: Path, tree: Path, work: Path, env: dict[str, str]) -> Evidence:
    result = Evidence()
    audit = result.audit
    pending: dict[str, str] = {}
    item_types: dict[str, str] = {}
    closed: set[str] = set()
    started = False
    digest = hashlib.sha256()
    if not log.is_file():
        audit.status = "unauditable"
        return result
    with log.open("rb") as stream:
        for number, raw in enumerate(stream, 1):
            digest.update(raw)
            ref = f"L{number}"
            try:
                event = json.loads(raw)
                if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                    raise ValueError
            except (ValueError, RecursionError):
                audit.invalid_events.append(ref)
                continue
            kind = event["type"]
            item = event.get("item")
            item_event = kind in {"item.started", "item.updated", "item.completed"}
            item_id = item.get("id") if isinstance(item, dict) else None
            key = item_id if nonempty(item_id) else ref
            ref = f"{ref}/{key}"
            audit.event_ids.append(ref)
            if not result.failed_id:
                result.last, result.terminal_id = kind, ref
            if kind in CLI_ERRORS:
                result.cli_diagnostic(event, kind, ref)
                continue
            if kind in META:
                if kind == "turn.started":
                    started = True
                    result.worked = False
                    result.active_items.clear()
                elif kind == "turn.completed":
                    started = False
                    message = str(event.get("message", ""))
                    if not result.failed_id and (
                        event.get("refusal")
                        or event.get("error")
                        or event.get("status") in ("failed", "refused", "incomplete")
                        or event.get("finish_reason") in ("refusal", "content_filter")
                        or REFUSAL.search(message)
                        or service_marker(message)
                    ):
                        result.cli_diagnostic(event, kind, ref)
                        result.refused_id = ref
                continue
            if not item_event or not isinstance(item, dict) or not nonempty(item.get("type")):
                audit.invalid_events.append(ref)
                if re.search(r"refus|denied|reject", kind, re.I):
                    result.refusal(ref)
                continue
            item_type = item["type"]
            valid_id = (
                nonempty(item_id)
                and key not in closed
                and item_types.get(key, item_type) == item_type
                and not (kind == "item.started" and key in item_types)
            )
            if not valid_id or not isinstance(item.get("status", ""), str):
                audit.invalid_events.append(ref)
            item_types[key] = item_type
            if kind == "item.completed":
                closed.add(key)
                result.active_items.discard(key)
            work_item = False
            if item_type in {"agent_message", "reasoning", "error", "refusal"}:
                message = item.get("text", item.get("message"))
                if not nonempty(message):
                    audit.invalid_events.append(ref)
                if (
                    item.get("refusal")
                    or item_type in {"error", "refusal"}
                    or (item_type == "agent_message" and REFUSAL.search(str(message)))
                ):
                    # Model/item text can report a refusal but cannot establish its origin.
                    result.refusal(ref)
                work_item = nonempty(message) and item_type in {"agent_message", "reasoning"}
            elif item_type in {"todo_list", "plan"}:
                entries = item.get("items")
                if not isinstance(entries, list) or not all(
                    isinstance(entry, dict)
                    and nonempty(entry.get("text"))
                    and type(entry.get("completed")) is bool
                    for entry in entries
                ):
                    audit.invalid_events.append(ref)
            else:
                access_record = access(item, tree, work, env)
                if not access_record.auditable:
                    audit.invalid_events.append(ref)
                work_item = access_record.work
                if kind == "item.completed":
                    earlier = pending.pop(key, None) if valid_id else None
                    if access_record.hit or earlier:
                        target = (
                            audit.denied_events
                            if access_record.denied and valid_id
                            else audit.outside_events
                        )
                        target.append(ref)
                elif access_record.hit:
                    pending[key] = ref
            if item_type in {
                "agent_message",
                "reasoning",
                "error",
                "refusal",
                "todo_list",
                "plan",
            } and any(k in item for k in ("arguments", "input", "command", "cmd")):
                audit.invalid_events.append(ref)
                work_item = False
            if started and valid_id and work_item and not (result.failed_id or result.refused_id):
                result.worked = True
                if kind != "item.completed" and item.get("status") in (
                    None,
                    "in_progress",
                    "running",
                    "started",
                ):
                    result.active_items.add(key)
                else:
                    result.active_items.discard(key)
                # Only fresh agent work can demonstrate recovery from a transient diagnostic.
                if result.service:
                    result.service, result.service_id, result.diagnostic = None, "", ""
    audit.sha256 = digest.hexdigest()
    audit.outside_events.extend(pending.values())
    if audit.outside_events:
        audit.status = "outside_read"
    elif not audit.event_ids or audit.invalid_events:
        audit.status = "unauditable"
    return result


def classify(data: Evidence, rc: int | None) -> tuple[Grade | None, str | None]:
    event = data.terminal_id
    if data.service:
        return Grade(
            "error", f"service marker {data.service} at {data.service_id}, terminal {event}"
        ), data.service
    if data.failed_id or data.refused_id:
        return Grade(
            "error", f"unattributed termination at {data.failed_id or data.refused_id}"
        ), "unattributed"
    if rc == 0 and data.last == "turn.completed" and data.worked and not data.diagnostic:
        return None, None
    if rc is None and data.active_items and not data.diagnostic and data.last.startswith("item."):
        return Grade("fail", f"agent wall-clock limit after {event}"), "deadline"
    if rc not in (0, None) and re.search(
        r"\b(?:agent|worker|model process) (?:crash(?:ed)?|panicked)\b", data.diagnostic, re.I
    ):
        return Grade("fail", f"agent crash at {event}"), "crash"
    return Grade("error", f"unattributed termination at {event or 'no event'}"), "unattributed"
