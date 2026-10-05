# ruff: noqa
# fmt: off
# Verbatim copy of frontier-scout frontier_scout/agent_firewall/hook_runtime.py at commit 58b0b17
# (sha256 of the original 0e38c80304eed706a179ed24f2970e1d31e534820ecdd7bb45ec8cad5ae22a63); the two
# directives above keep this repository's linters off it. Everything below this line is byte-identical.
"""Self-contained, stdlib-only runtime for Frontier Scout's Claude Code hooks.

THIS MODULE IS COPIED VERBATIM by the compiler into a target repo's
``.claude/hooks/_fs_guard.py`` and imported by the generated ``pre_tool_use.py`` /
``post_tool_use.py``. It therefore MUST NOT import anything from ``frontier_scout``
(it runs wherever Claude Code runs, which need not have the package installed) and
MUST stay pure standard library.

Responsibilities:
  * ``decide(tool_name, tool_input, policy)`` — map a real tool call to a native
    Claude permission decision (``allow`` | ``deny`` | ``ask``), fail-closed.
  * ``handle_pre_tool_use`` — return the PreToolUse ``hookSpecificOutput`` JSON and
    write a redacted action receipt binding the call to the policy hash.
  * ``handle_post_tool_use`` — write a receipt recording the realized outcome.

Frontier Scout emits this; Claude Code enforces it. It never executes the tool.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shlex
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# --- redaction (vendored: stdlib only, no frontier_scout import) -----------------

_SECRET_PATTERNS = [
    (re.compile(r"sk-ant-[A-Za-z0-9\-_]+"), "sk-ant-REDACTED"),
    (re.compile(r"sk-[A-Za-z0-9]+"), "sk-REDACTED"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]+"), "xox*-REDACTED"),
    (re.compile(r"ghp_[A-Za-z0-9]+"), "ghp_REDACTED"),
    (re.compile(r"github_pat_[A-Za-z0-9_]+"), "github_pat_REDACTED"),
    (re.compile(r"ATATT[A-Za-z0-9\-_=]+"), "ATATT-REDACTED"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA-REDACTED"),
    (re.compile(r"npm_[A-Za-z0-9]+"), "npm_REDACTED"),
    (re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"), "Bearer REDACTED"),
]


def scrub(text: str) -> str:
    """Redact common secret shapes from a durable/emitted string."""

    out = text or ""
    for pattern, repl in _SECRET_PATTERNS:
        out = pattern.sub(repl, out)
    return out


# --- path / glob helpers (recursive-glob approximation, no I/O) -------------------

def _normalise_path(path: str) -> str:
    normalised = path.replace("\\", "/")
    while normalised.startswith("./"):
        normalised = normalised[2:]
    return normalised


def _path_matches_glob(path: str, glob: str) -> bool:
    """Approximate ``**`` recursive-glob semantics with stdlib ``fnmatch``."""

    normalised = _normalise_path(path)
    candidates = [glob]
    if glob.startswith("**/"):
        candidates.append(glob[3:])
    parts = normalised.split("/")
    suffixes = ["/".join(parts[i:]) for i in range(len(parts))]
    for candidate in candidates:
        for suffix in suffixes:
            if fnmatch.fnmatch(suffix, candidate):
                return True
    return False


# --- tool-call classification ----------------------------------------------------

_READ_TOOLS = {"Read", "Glob", "Grep", "LS", "NotebookRead"}
_WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
_NETWORK_TOOLS = {"WebFetch", "WebSearch"}


def _file_path_of(tool_input: dict[str, Any]) -> str:
    for key in ("file_path", "path", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def repo_relative(path: str, repo: str) -> str:
    """Normalise a tool-input path to the repo-relative POSIX form ``git diff`` reports.

    Claude Code sends absolute ``file_path`` values, while ``verify-pr`` matches receipts
    against ``git diff --name-only``, which is repo-relative. Receipts therefore record
    paths in the latter form. A path outside ``repo`` (or one that cannot be resolved) is
    returned unchanged rather than dropped, so the verifier simply finds no receipt for it.
    """
    if not path:
        return path
    try:
        candidate = Path(path)
        if not candidate.is_absolute():
            return Path(os.path.normpath(path)).as_posix()
        return candidate.resolve().relative_to(Path(repo).resolve()).as_posix()
    except (ValueError, OSError, RuntimeError):
        return path


# --- Bash command-structure matching --------------------------------------------
# Decisions key off the *executed command structure*, not raw substring over the
# whole command string. A blocked token inside a quoted message/argument (e.g.
# `git commit -m "...rm -rf..."`) must never trigger a deny, because shlex keeps a
# quoted string as a single token. This is a policy matcher, not a shell.

_SHELL_OPERATORS = {"|", "||", "&&", ";", "&"}
_BENIGN_WRAPPERS = {"env", "command", "nice", "nohup", "time", "doas", "xargs", "stdbuf", "setsid"}
_SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}


def _shlex_split(text: str) -> list[str] | None:
    """Quote-aware tokenization; ``None`` if unparseable (e.g. unbalanced quotes)."""

    try:
        return shlex.split(text, posix=True)
    except ValueError:
        return None


def _raw_segments(command: str) -> list[str] | None:
    """Split a raw command into segments at UNQUOTED shell control operators
    (``| || && ; &``), quote-aware. ``None`` if a quote is left open. Redirects
    (``> <``) are NOT split points — they stay in a segment so redirect patterns can
    match. Splitting the raw string (not post-shlex tokens) catches no-space pipes like
    ``curl ...|sh`` that token-level splitting misses."""

    segments: list[str] = []
    current: list[str] = []
    quote: str | None = None
    i, n = 0, len(command)
    while i < n:
        c = command[i]
        if quote is not None:
            current.append(c)
            if c == quote:
                quote = None
            i += 1
            continue
        if c in ("'", '"'):
            quote = c
            current.append(c)
            i += 1
            continue
        if c in "|&" and i + 1 < n and command[i + 1] == c:  # || or &&
            segments.append("".join(current))
            current = []
            i += 2
            continue
        if c in "|;&":  # | ; &
            segments.append("".join(current))
            current = []
            i += 1
            continue
        current.append(c)
        i += 1
    if quote is not None:
        return None
    segments.append("".join(current))
    return [s for s in segments if s.strip()]


def _tokenize_segments(command: str) -> list[list[str]] | None:
    """Quote-aware segment split, then shlex each segment into argv. ``None`` if any
    part is unparseable (unbalanced quotes)."""

    raw = _raw_segments(command)
    if raw is None:
        return None
    out: list[list[str]] = []
    for seg in raw:
        toks = _shlex_split(seg)
        if toks is None:
            return None
        if toks:
            out.append(toks)
    return out


def _peel_wrappers(argv: list[str]) -> list[str]:
    """Strip leading benign wrappers (``env VAR=val``, ``command``, ``nice``, …).
    Keeps ``sudo`` (it is itself a policy target)."""

    i = 0
    while i < len(argv):
        head = argv[i]
        if head in _BENIGN_WRAPPERS:
            i += 1
            if head == "env":
                while i < len(argv) and "=" in argv[i] and not argv[i].startswith("-"):
                    i += 1
            continue
        break
    return argv[i:]


def _shell_c_script(argv: list[str]) -> str | None:
    """If ``argv`` invokes a shell with a ``-c``/``-lc``/``-ic`` flag, return the
    script-string it would run; else ``None``."""

    if not argv or argv[0] not in _SHELLS:
        return None
    for i in range(1, len(argv)):
        a = argv[i]
        if a.startswith("-"):
            if "c" in a:
                return argv[i + 1] if i + 1 < len(argv) else None
        else:
            break
    return None


def _resolve_units(segments: list[list[str]], _depth: int = 0) -> tuple[list[list[str]], bool]:
    """Resolve segments into argv units (wrappers peeled, shell ``-c`` scripts
    recursed into). Returns ``(units, shell_c_used)``."""

    units: list[list[str]] = []
    shell_c = False
    for seg in segments:
        argv = _peel_wrappers(seg)
        if not argv:
            continue
        units.append(argv)
        script = _shell_c_script(argv)
        if script is not None and _depth < 3:
            shell_c = True
            inner = _tokenize_segments(script)
            if inner:
                inner_units, inner_c = _resolve_units(inner, _depth + 1)
                units.extend(inner_units)
                shell_c = shell_c or inner_c
    return units, shell_c


def _is_command_token(tok: str) -> bool:
    """True if ``tok`` looks like a command/executable name — not a shell-syntax
    construct like ``>`` or ``:(){``. Determines whether a plain blocked pattern is a
    command-position pattern or a shell-syntax pattern."""

    return bool(tok) and re.fullmatch(r"[A-Za-z0-9_./-]+", tok) is not None


def _command_position_match(ptoks: list[str], unit: list[str]) -> bool:
    """Anchored argv-prefix match: ``unit[0]`` must equal ``ptoks[0]`` (the executed
    command), and each remaining pattern token must equal the argv token at the same
    position — EXACTLY, except a pattern token ending in ``=`` matches as a prefix (so
    ``dd if=`` catches ``dd if=/dev/zero``). A blocked command token therefore never
    matches a safe command's later arguments (``eval`` ≠ ``pytest -k evaluate``)."""

    if len(unit) < len(ptoks) or unit[0] != ptoks[0]:
        return False
    for i in range(1, len(ptoks)):
        p = ptoks[i]
        if p.endswith("="):
            if not unit[i].startswith(p):
                return False
        elif unit[i] != p:
            return False
    return True


def _exact_subseq(ptoks: list[str], unit: list[str]) -> bool:
    """``ptoks`` appear as a contiguous run of EXACT tokens anywhere in ``unit`` — used
    for shell-syntax patterns whose first token is not a command (e.g. ``> /dev/sda``)."""

    n = len(ptoks)
    if not n:
        return False
    for i in range(len(unit) - n + 1):
        if unit[i : i + n] == ptoks:
            return True
    return False


def _blocked_hit(pattern: str, segments: list[list[str]], units: list[list[str]]) -> bool:
    """True if a blocked ``pattern`` matches the command structure (never raw text)."""

    parts = pattern.split()
    if set(parts) & _SHELL_OPERATORS:
        # Pipe/sequence pattern (e.g. "curl | sh"): sub-prefixes must appear as
        # segment prefixes, in order.
        subs: list[list[str]] = []
        cur: list[str] = []
        for tok in parts:
            if tok in _SHELL_OPERATORS:
                if cur:
                    subs.append(cur)
                    cur = []
            else:
                cur.append(tok)
        if cur:
            subs.append(cur)
        si = 0
        for seg in segments:
            if si < len(subs) and seg[: len(subs[si])] == subs[si]:
                si += 1
        return si == len(subs) and bool(subs)
    ptoks = _shlex_split(pattern)
    if not ptoks:  # exotic pattern that won't shlex (e.g. ":(){"): per-token substring
        return any(any(pattern in tok for tok in u) for u in units)
    if _is_command_token(ptoks[0]):
        # Command-danger pattern (rm -rf, sudo, eval, dd if=, …): match ONLY at command
        # position, so a blocked token can't match a safe command's args/flags/text.
        return any(_command_position_match(ptoks, u) for u in units)
    # Shell-syntax pattern (redirect / fork-bomb): exact contiguous token subsequence.
    return any(_exact_subseq(ptoks, u) for u in units)


def decide(tool_name: str, tool_input: dict[str, Any], policy: dict[str, Any]) -> tuple[str, str]:
    """Return ``(decision, reason)`` for a tool call. ``decision`` is allow|deny|ask.

    Fail-closed: anything not provably safe escalates to ``ask`` (and off-policy MCP
    or blocked commands/tools hard-``deny``).
    """

    tool_input = tool_input or {}

    # 1. Hard blocks: an explicitly blocked tool, regardless of args.
    if tool_name in set(policy.get("blocked_tools", [])):
        return "deny", f"Tool '{tool_name}' is on the blocked list."

    # 2. MCP tools (``mcp__<server>__<tool>``): deny-by-default off the allowlist.
    if tool_name.startswith("mcp__"):
        parts = tool_name.split("__")
        server = parts[1] if len(parts) > 1 else ""
        if server in set(policy.get("mcp_server_allowlist", [])):
            return "allow", f"MCP server '{server}' is allowlisted."
        return "deny", f"MCP server '{server}' is not on the allowlist (deny-by-default)."

    # 3. Bash: match the executed command STRUCTURE (not raw substring).
    #    blocked structure -> deny; allowlisted first-command prefix -> allow;
    #    shell -c / unparseable / unknown -> ask (fail-closed).
    if tool_name == "Bash":
        command = str(tool_input.get("command", ""))
        segments = _tokenize_segments(command)
        if segments is None:
            return "ask", "Command could not be parsed safely; approval required (fail-closed)."
        units, shell_c = _resolve_units(segments)
        for blocked in policy.get("blocked_shell_commands", []):
            if blocked and _blocked_hit(blocked, segments, units):
                return "deny", f"Command matches a blocked pattern: {blocked}"
        if units and not shell_c:
            first = units[0]
            for allowed in policy.get("allowed_shell_commands", []):
                atoks = _shlex_split(allowed) or []
                if atoks and first[: len(atoks)] == atoks:
                    return "allow", f"Command matches an allowlisted prefix: {allowed}"
        if shell_c:
            return "ask", "Shell -c invocation; approval required (fail-closed)."
        return "ask", "Command is not on the allowlist; approval required (fail-closed)."

    # 4. File writes/edits: protected glob -> ask; allowed glob -> allow; else ask.
    if tool_name in _WRITE_TOOLS:
        path = _file_path_of(tool_input)
        if any(_path_matches_glob(path, g) for g in policy.get("protected_file_globs", [])):
            return "ask", f"Write touches a protected path: {path}"
        if any(_path_matches_glob(path, g) for g in policy.get("allowed_file_globs", [])):
            return "allow", f"Write is within an allowed path: {path}"
        return "ask", f"Write target is outside any allowed path: {path} (fail-closed)."

    # 5. Reads are allowed (read-only surface).
    if tool_name in _READ_TOOLS:
        return "allow", "Read-only tool."

    # 6. Network egress: approval-gated.
    if tool_name in _NETWORK_TOOLS:
        return "ask", "Network egress requires approval."

    # 7. Explicitly allowlisted tool.
    if tool_name in set(policy.get("allowed_tools", [])):
        return "allow", f"Tool '{tool_name}' is allowlisted."

    # 8. Unknown tool: fail-closed.
    return "ask", f"Tool '{tool_name}' is not classified; approval required (fail-closed)."


# --- optional decision model (opt-in; advisory; fail-closed) ----------------------
# When the policy carries a ``decision_model`` section (see models.DecisionModelSpec), the
# hook asks a System One decision endpoint about a Bash call AFTER the static decision.
# The answers can only tighten an allow to ask or an allow/ask to deny, or relax an ask to
# allow; a static deny stands, and any failure (no key, timeout, bad or wrong-model
# response) leaves the static decision in force. The key is read from the environment at hook time and is
# never written. Stdlib only: urllib with a short timeout. The questions below are the
# contract; keep them literal (the model answers the question as written).

_EFFECT_CRITERIA: dict[str, str] = {
    "read_only": "only reads or prints information; changes no file, setting, process or remote state",
    "build_or_test": (
        "compiles, builds, lints, format-checks or runs tests for the project; may write build artefacts"
    ),
    "writes_inside_repo": (
        "creates or changes files, or local git state, inside the project directory, "
        "without permanently discarding anything"
    ),
    "writes_outside_repo": (
        "installs packages or changes files or settings outside the project directory, "
        "without permanently discarding anything"
    ),
    "network_egress": "sends requests to, or fetches from, a remote host or service",
    "destructive": (
        "permanently deletes, overwrites or discards data, files, git history, branches, "
        "uncommitted work, or destroys infrastructure"
    ),
    "privilege_escalation": (
        "runs as another user, uses sudo, or changes permissions, owners or system configuration"
    ),
    "other": "starts a program or service, changes the shell session, or does not fit the other options",
}

_MODEL_QUESTIONS: dict[str, Any] = {
    "effect": {
        "type": "choice",
        "instructions": "What is the main effect of running `command` in a software project's shell?",
        "criteria": _EFFECT_CRITERIA,
    },
    "destructive": {
        "type": "noul",
        "instructions": (
            "Does running `command` permanently delete, overwrite or discard data, files, git history, "
            "branches or uncommitted work, or destroy infrastructure?"
        ),
        "criteria": {
            "true": "yes, it permanently deletes, overwrites, discards or destroys something",
            "false": "no, nothing is permanently lost",
        },
    },
    "secret_exposure": {
        "type": "noul",
        "instructions": (
            "Does running `command` print, upload, copy or send credentials, API keys, tokens, "
            "private keys or password files?"
        ),
        "criteria": {
            "true": "yes, credentials, keys, tokens or password files are printed, copied or sent",
            "false": "no credential, key, token or password file is exposed",
        },
    },
    "privilege": {
        "type": "noul",
        "instructions": (
            "Does running `command` escalate privileges, run as another user, or change permissions, "
            "owners or system configuration?"
        ),
        "criteria": {
            "true": "yes, it escalates privileges or changes permissions, owners or system configuration",
            "false": "no, it runs as the current user without changing permissions or system configuration",
        },
    },
}
_RELAXABLE_EFFECTS = {"read_only", "build_or_test"}
_RISK_QUESTIONS = ("destructive", "secret_exposure", "privilege")
_MODEL_DEFAULTS: dict[str, Any] = {
    "model": "jev-1.13.0",
    "base_url": "https://api.typesafe.ai",
    "key_env": "TYPESAFE_API_KEY",
    "timeout_seconds": 3.0,
    "relax_ask_to_allow_at": 0.95,
    "deny_at": 0.9,
    "ask_at": 0.5,
}


def _spec_value(spec: dict[str, Any], key: str) -> Any:
    value = spec.get(key)
    return _MODEL_DEFAULTS[key] if value is None else value


def _unit_interval(value: Any) -> float | None:
    """``value`` as a float in [0, 1], else ``None`` (the API returns rounded floats)."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if 0.0 <= number <= 1.0 else None


def _parse_answers(payload: Any, model: str) -> dict[str, Any] | None:
    """Validate the response shape strictly; anything unexpected is ``None`` (fail-closed)."""

    if not isinstance(payload, dict) or payload.get("model") != model:
        return None
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        return None
    effect = answers.get("effect")
    if not isinstance(effect, dict) or effect.get("choice") not in _EFFECT_CRITERIA:
        return None
    confidence = _unit_interval(effect.get("confidence"))
    if confidence is None:
        return None
    parsed: dict[str, Any] = {"effect": {"choice": str(effect["choice"]), "confidence": confidence}}
    for name in _RISK_QUESTIONS:
        answer = answers.get(name)
        value = _unit_interval(answer.get("noul")) if isinstance(answer, dict) else None
        if value is None:
            return None
        parsed[name] = value
    return parsed


def ask_decision_model(command: str, spec: dict[str, Any], key: str) -> dict[str, Any] | None:
    """One request to the decision endpoint; ``None`` on any failure or unexpected answer."""

    model = str(_spec_value(spec, "model"))
    url = f"{str(_spec_value(spec, 'base_url')).rstrip('/')}/v1/systemone"
    timeout = float(_spec_value(spec, "timeout_seconds"))
    body = json.dumps(
        {"state": {"command": command}, "model": model, "questions": _MODEL_QUESTIONS}
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "frontier-scout-hook/1",
        },
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 — https API URL from the policy
            payload = json.loads(response.read())
            request_id = response.headers.get("x-typesafe-request-id")
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None
    answers = _parse_answers(payload, model)
    if answers is None:
        return None
    return {
        "model": model,
        "request_id": request_id,
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "answers": answers,
    }


def combine_with_model(decision: str, answers: dict[str, Any], spec: dict[str, Any]) -> tuple[str, str]:
    """Apply validated answers to a static ``decision``; return ``(decision, applied)``.

    ``applied`` is one of ``static-deny`` (a deny is never relaxed), ``tightened`` (the model
    is confident the call is risky: deny), ``tightened-to-ask`` (an allow became an ask because
    the model rates the call possibly risky), ``relaxed`` (an ask became an allow because the
    model is confident the call is read-only or build/test and not risky) or ``abstained``.
    """

    if decision == "deny":
        return "deny", "static-deny"
    deny_at = float(_spec_value(spec, "deny_at"))
    ask_at = float(_spec_value(spec, "ask_at"))
    relax_at = float(_spec_value(spec, "relax_ask_to_allow_at"))
    risk = max(float(answers[name]) for name in _RISK_QUESTIONS)
    if risk >= deny_at:
        return "deny", "tightened"
    if decision == "allow" and risk >= ask_at:
        return "ask", "tightened-to-ask"
    effect = answers["effect"]
    if (
        decision == "ask"
        and effect["choice"] in _RELAXABLE_EFFECTS
        and float(effect["confidence"]) >= relax_at
        and risk <= (1.0 - relax_at) + 1e-9  # tolerance: 1 - 0.8 is not exactly 0.2 in binary
    ):
        return "allow", "relaxed"
    return decision, "abstained"


def consult_decision_model(
    tool_name: str, tool_input: dict[str, Any], policy: dict[str, Any], decision: str
) -> tuple[str, str | None, dict[str, Any] | None]:
    """Return ``(decision, note, receipt_block)``; all unchanged/``None`` when not opted in."""

    spec = policy.get("decision_model")
    if not isinstance(spec, dict) or tool_name != "Bash":
        return decision, None, None
    scope = spec.get("scope")
    if isinstance(scope, list) and tool_name not in scope:
        return decision, None, None
    model = str(_spec_value(spec, "model"))
    key = os.environ.get(str(_spec_value(spec, "key_env")), "")
    if not key:
        return decision, None, {"model": model, "applied": "unavailable", "reason": "no key in the environment"}
    result = ask_decision_model(str(tool_input.get("command", "")), spec, key)
    if result is None:
        return (
            decision,
            None,
            {"model": model, "applied": "unavailable", "reason": "no valid answer within the timeout"},
        )
    final, applied = combine_with_model(decision, result["answers"], spec)
    risk = max(float(result["answers"][name]) for name in _RISK_QUESTIONS)
    effect = result["answers"]["effect"]
    notes = {
        "tightened": (
            f"Decision model rates the call risky (risk {risk:.2f} >= {_spec_value(spec, 'deny_at')}); denied."
        ),
        "tightened-to-ask": (
            f"Decision model rates the call possibly risky (risk {risk:.2f} >= "
            f"{_spec_value(spec, 'ask_at')}); approval required."
        ),
        "relaxed": (
            f"Decision model is confident the call is {effect['choice']} "
            f"(confidence {effect['confidence']:.2f}, risk {risk:.2f}); allowed."
        ),
    }
    block = {
        "model": result["model"],
        "request_id": result["request_id"],
        "latency_ms": result["latency_ms"],
        "answers": result["answers"],
        "applied": applied,
    }
    return final, notes.get(applied), block


# --- receipts (raw JSON; schema-compatible with frontier_scout Receipt) ----------

_VERDICT_OF = {"allow": "allow", "ask": "needs_approval", "deny": "block"}
_SLUG_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text).lower()[:40].strip("-") or "action"


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S-%fZ")


def _input_hash(tool_input: dict[str, Any]) -> str:
    canonical = json.dumps(tool_input or {}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def receipts_dir(repo: str) -> Path:
    return Path(repo) / ".frontier-scout" / "receipts"


def _write(repo: str, receipt: dict[str, Any], phase: str) -> str:
    directory = receipts_dir(repo)
    directory.mkdir(parents=True, exist_ok=True)
    receipt_id = receipt["receipt_id"]
    path = directory / f"{receipt_id}-{phase}.json"
    path.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
    return str(path)


def handle_pre_tool_use(
    event: dict[str, Any],
    *,
    policy: dict[str, Any],
    policy_hash: str,
    repo: str,
    version: str | None = None,
) -> dict[str, Any]:
    """Decide on a PreToolUse event, write an action receipt, return the hook JSON."""

    tool_name = str(event.get("tool_name", ""))
    tool_input = event.get("tool_input") or {}
    static_decision, reason = decide(tool_name, tool_input, policy)
    decision, model_note, model_block = consult_decision_model(
        tool_name, tool_input, policy, static_decision
    )
    reasons = [{"severity": "info", "rule_id": f"tool.{static_decision}", "message": scrub(reason)}]
    if model_note:
        reason = f"{reason} {model_note}"
        reasons.append(
            {
                "severity": "info",
                "rule_id": f"decision_model.{(model_block or {}).get('applied', 'abstained')}",
                "message": scrub(model_note),
            }
        )
    file_path = repo_relative(_file_path_of(tool_input), repo)
    files = [file_path] if file_path else []
    receipt = {
        "receipt_id": f"{_stamp()}-{_slug(tool_name)}",
        "timestamp": datetime.now(UTC).isoformat(),
        "repo": repo,
        "task_summary": scrub(f"{tool_name}: {json.dumps(tool_input, default=str)}")[:500],
        "verdict": _VERDICT_OF.get(decision, "needs_approval"),
        "decision": decision,
        "kind": "agent-action",
        "policy_hash": policy_hash,
        "tool_name": tool_name,
        "tool_input_hash": _input_hash(tool_input),
        "reasons": reasons,
        "files_considered": [scrub(f) for f in files],
        "required_checks": list(policy.get("required_checks", [])),
        "warnings": [],
        "frontier_scout_version": version,
        "realized": None,
        "decision_model": model_block,
    }
    _write(repo, receipt, phase="pre")
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": scrub(reason),
        }
    }


def handle_post_tool_use(
    event: dict[str, Any],
    *,
    policy_hash: str,
    repo: str,
    version: str | None = None,
) -> dict[str, Any]:
    """Record the realized outcome of a completed tool call as an action receipt."""

    tool_name = str(event.get("tool_name", ""))
    tool_input = event.get("tool_input") or {}
    tool_output = event.get("tool_output")
    file_path = repo_relative(_file_path_of(tool_input), repo)
    files = [file_path] if file_path else []
    realized: dict[str, Any] = {"completed": True}
    if isinstance(tool_output, dict):
        realized["status"] = tool_output.get("status")
    receipt = {
        "receipt_id": f"{_stamp()}-{_slug(tool_name)}",
        "timestamp": datetime.now(UTC).isoformat(),
        "repo": repo,
        "task_summary": scrub(f"{tool_name}: {json.dumps(tool_input, default=str)}")[:500],
        "verdict": "allow",
        "decision": "allow",
        "kind": "agent-action",
        "policy_hash": policy_hash,
        "tool_name": tool_name,
        "tool_input_hash": _input_hash(tool_input),
        "reasons": [],
        "files_considered": [scrub(f) for f in files],
        "required_checks": [],
        "warnings": [],
        "frontier_scout_version": version,
        "realized": realized,
    }
    _write(repo, receipt, phase="post")
    return {}
