"""Provoke a stdio MCP server's own failure replies (benchmark Reply-0, study code).

Standard library only. No model is called: this is a scripted client.

    python3 probe.py --server NAME --plan PLAN.json --out-dir DIR \
        [--var KEY=VALUE ...] [--env KEY=VALUE ...] [--redact PATH=NAME ...] [--cwd DIR] \
        -- COMMAND [ARG ...]

`--redact PATH=NAME` replaces that absolute path by NAME in everything written to DIR (the
longest path first), so no output file carries a personal directory name. It changes only the
written files, never what is sent to the server.

What it does, in order:

1. starts COMMAND with a small, fixed environment (PATH, plus every --env) and talks
   newline-delimited JSON-RPC 2.0 over its standard input and output;
2. sends `initialize`, `notifications/initialized` and `tools/list` (following `nextCursor`);
3. for every READ-ONLY tool sends one GOOD call and up to four BAD calls:
       missing_required   the good arguments with one required argument left out
       wrong_type         the good arguments with one argument of the wrong JSON type
       bad_enum           the good arguments with a value outside an enum
       unknown_value      the good arguments with a value that does not exist (a path, a branch,
                          a commit, an order id): the plan names it
4. writes DIR/NAME.jsonl (every raw request and reply, one JSON object per line),
   DIR/NAME.md (the tables) and DIR/NAME.stderr.txt (what the server wrote to stderr).

A tool is read-only when the server says so (`annotations.readOnlyHint` is true). A server that
sends no annotations has no read-only tools by its own account; the plan may then name them in
`read_only_tools`, and the output says that the plan, not the server, made the claim. A tool that
is not read-only is never called.

The plan (JSON; `${KEY}` in any string is replaced by the --var of that name):

    {
      "read_only_tools": ["..."],            optional, see above
      "tools": {
        "TOOL": {
          "good": {...},                     the arguments of the good call (required)
          "unknown_value": {"args": {...}, "what": "a file that does not exist"},
                                             (or a list of these; a tool never gets more than
                                             four bad calls in all)
          "missing_required": "ARG",         optional: which required argument to leave out
          "wrong_type": {"args": {...}, "what": "..."},     optional: instead of the derived one
          "bad_enum": {"args": {...}, "what": "..."}        optional: when the allowed values are
        }                                                   named only in a description
      }
    }

`args` are merged over the good arguments. What the plan does not give is derived from the tool's
input schema: the first required argument is left out; the first argument with a simple declared
type gets a value of another type; the first argument with an `enum` gets a value outside it.
A bad call that cannot be built (no required argument, no enum) is listed as "not sent" with the
reason; it is never invented.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

PROTOCOL_REQUESTED = "2025-11-25"
CLIENT_INFO = {"name": "reply0-probe", "version": "0.1"}
KINDS = ("good", "missing_required", "wrong_type", "bad_enum", "unknown_value")
NOT_IN_ENUM = "__reply0_not_in_enum__"
GOOD_TEXT_LIMIT = 200
MAX_BAD = 4

Json = Any


# --------------------------------------------------------------------------------------------
# The server process
# --------------------------------------------------------------------------------------------
class Server:
    def __init__(self, command: list[str], env: dict[str, str], cwd: str | None, timeout: float):
        self._timeout = timeout
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=cwd,
        )
        self._lines: queue.Queue[bytes | None] = queue.Queue()
        self._stderr: list[bytes] = []
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        self._next_id = 0

    def _read_stdout(self) -> None:
        assert self._process.stdout is not None
        for line in self._process.stdout:
            self._lines.put(line)
        self._lines.put(None)

    def _read_stderr(self) -> None:
        assert self._process.stderr is not None
        for line in self._process.stderr:
            self._stderr.append(line)

    def send(self, message: Json) -> None:
        assert self._process.stdin is not None
        data = json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n"
        self._process.stdin.write(data.encode("utf-8"))
        self._process.stdin.flush()

    def request(
        self, method: str, params: Json
    ) -> tuple[Json, Json | None, list[Json], str | None]:
        """Send one request. Returns (request, reply, other messages seen meanwhile, problem)."""
        self._next_id += 1
        message = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        others: list[Json] = []
        try:
            self.send(message)
        except (BrokenPipeError, OSError) as exc:
            return message, None, others, f"could not write to the server: {exc}"
        deadline = time.monotonic() + self._timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return message, None, others, f"no reply within {self._timeout:g} seconds"
            try:
                line = self._lines.get(timeout=remaining)
            except queue.Empty:
                return message, None, others, f"no reply within {self._timeout:g} seconds"
            if line is None:
                return message, None, others, "the server closed its output"
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            try:
                received = json.loads(text)
            except json.JSONDecodeError:
                others.append({"not_json": text})
                continue
            if (
                isinstance(received, dict)
                and received.get("id") == message["id"]
                and ("result" in received or "error" in received)
            ):
                return message, received, others, None
            others.append(received)
            # A request from the server to this client: answer so that it does not wait.
            if isinstance(received, dict) and "method" in received and "id" in received:
                if received["method"] == "ping":
                    answer: Json = {"jsonrpc": "2.0", "id": received["id"], "result": {}}
                else:
                    answer = {
                        "jsonrpc": "2.0",
                        "id": received["id"],
                        "error": {"code": -32601, "message": "reply0-probe does not serve this"},
                    }
                others.append({"probe_answered": answer})
                self.send(answer)

    def stop(self) -> tuple[int | None, bytes]:
        try:
            assert self._process.stdin is not None
            self._process.stdin.close()
        except OSError:
            pass
        try:
            self._process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        time.sleep(0.1)
        return self._process.returncode, b"".join(self._stderr)


# --------------------------------------------------------------------------------------------
# Building the calls
# --------------------------------------------------------------------------------------------
def as_dict(value: Json) -> dict[str, Json]:
    """`value` when it is a JSON object, else an empty one."""
    return value if isinstance(value, dict) else {}


def substitute(value: Json, variables: dict[str, str]) -> Json:
    if isinstance(value, str):
        for key, replacement in variables.items():
            value = value.replace("${" + key + "}", replacement)
        return value
    if isinstance(value, list):
        return [substitute(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: substitute(item, variables) for key, item in value.items()}
    return value


def wrong_value(schema: Json) -> tuple[Json, str] | None:
    """A value of another JSON type than the one `schema` declares, and words for it."""
    declared = schema.get("type") if isinstance(schema, dict) else None
    if declared == "string":
        return 12345, "a number where a string is declared"
    if declared in ("integer", "number"):
        return "twelve", f"a string where {declared} is declared"
    if declared == "boolean":
        return "maybe", "a string where a boolean is declared"
    if declared == "array":
        return "not-a-list", "a string where an array is declared"
    if declared == "object":
        return "not-an-object", "a string where an object is declared"
    return None


def find_enum(schema: Json) -> tuple[Json, list[Json]] | None:
    """(a value outside the enum in the shape the argument takes, the enum) or None."""
    if not isinstance(schema, dict):
        return None
    if isinstance(schema.get("enum"), list):
        return NOT_IN_ENUM, schema["enum"]
    items = schema.get("items")
    if isinstance(items, dict) and isinstance(items.get("enum"), list):
        return [NOT_IN_ENUM], items["enum"]
    for key in ("anyOf", "oneOf"):
        for branch in schema.get(key, []) if isinstance(schema.get(key), list) else []:
            if isinstance(branch, dict) and isinstance(branch.get("enum"), list):
                return NOT_IN_ENUM, branch["enum"]
    return None


def build_calls(tool: Json, entry: Json) -> list[dict[str, Json]]:
    """The five calls for one tool: each is sent, or carries the reason it is not sent."""
    schema = as_dict(tool.get("inputSchema"))
    properties = as_dict(schema.get("properties"))
    required = [name for name in schema.get("required", []) if isinstance(name, str)]
    good = entry.get("good")
    calls: list[dict[str, Json]] = []
    if not isinstance(good, dict):
        return [{"kind": kind, "skip": "the plan has no good call for this tool"} for kind in KINDS]
    calls.append(
        {"kind": "good", "arguments": dict(good), "what": "the good call", "changed": None}
    )

    # missing_required
    chosen = entry.get("missing_required")
    if not isinstance(chosen, str):
        chosen = next((name for name in required if name in good), None)
    if chosen is None:
        calls.append({"kind": "missing_required", "skip": "the schema has no required argument"})
    else:
        arguments = {key: value for key, value in good.items() if key != chosen}
        calls.append({
            "kind": "missing_required", "arguments": arguments,
            "what": f"`{chosen}` left out", "changed": chosen,
        })  # fmt: skip

    # wrong_type
    override = entry.get("wrong_type")
    if isinstance(override, dict) and isinstance(override.get("args"), dict):
        calls.append({
            "kind": "wrong_type", "arguments": {**good, **override["args"]},
            "what": str(override.get("what", "wrong type (from the plan)")),
            "changed": next(iter(override["args"]), None),
        })  # fmt: skip
    else:
        order = [*required, *[k for k in good if k not in required], *properties]
        derived = None
        for name in order:
            found = wrong_value(properties.get(name))
            if found is not None:
                derived = (name, *found)
                break
        if derived is None:
            calls.append({"kind": "wrong_type", "skip": "no argument has a simple declared type"})
        else:
            name, value, words = derived
            calls.append({
                "kind": "wrong_type", "arguments": {**good, name: value},
                "what": f"`{name}`: {words}", "changed": name,
            })  # fmt: skip

    # bad_enum
    override = entry.get("bad_enum")
    if isinstance(override, dict) and isinstance(override.get("args"), dict):
        calls.append({
            "kind": "bad_enum", "arguments": {**good, **override["args"]},
            "what": str(override.get("what", "outside the allowed values (from the plan)")),
            "changed": next(iter(override["args"]), None),
        })  # fmt: skip
    else:
        derived_enum = None
        for name, prop in properties.items():
            found_enum = find_enum(prop)
            if found_enum is not None:
                derived_enum = (name, *found_enum)
                break
        if derived_enum is None:
            calls.append({"kind": "bad_enum", "skip": "the schema has no enum"})
        else:
            name, value, allowed = derived_enum
            calls.append({
                "kind": "bad_enum", "arguments": {**good, name: value},
                "what": f"`{name}` outside the schema's enum {json.dumps(allowed)}",
                "changed": name,
            })  # fmt: skip

    # unknown_value: one entry, or a list of them; never more than four bad calls per tool
    override = entry.get("unknown_value")
    entries = override if isinstance(override, list) else [override]
    entries = [
        item for item in entries if isinstance(item, dict) and isinstance(item.get("args"), dict)
    ]
    if not entries:
        calls.append({"kind": "unknown_value", "skip": "the plan names no unknown value"})
    for item in entries:
        if sum(1 for call in calls if call["kind"] != "good" and "skip" not in call) >= MAX_BAD:
            calls.append(
                {"kind": "unknown_value", "skip": f"already {MAX_BAD} bad calls for this tool"}
            )
            break
        calls.append({
            "kind": "unknown_value", "arguments": {**good, **item["args"]},
            "what": str(item.get("what", "a value that does not exist")),
            "changed": next(iter(item["args"]), None),
        })  # fmt: skip
    return calls


# --------------------------------------------------------------------------------------------
# Reading a reply
# --------------------------------------------------------------------------------------------
def outcome_of(reply: Json | None, problem: str | None) -> tuple[str, str]:
    """(outcome label, exact reply text) of one tools/call reply."""
    if reply is None:
        return f"no reply ({problem})", ""
    if "error" in reply:
        error = reply["error"] if isinstance(reply["error"], dict) else {}
        text = str(error.get("message", ""))
        if "data" in error:
            text += "\n[error.data] " + json.dumps(error["data"], ensure_ascii=False)
        return f"JSON-RPC error {error.get('code')}", text
    result = reply.get("result") if isinstance(reply.get("result"), dict) else {}
    if "isError" not in result:
        label = "isError absent"
    else:
        label = (
            "isError true"
            if result["isError"] is True
            else f"isError {json.dumps(result['isError'])}"
        )
    parts: list[str] = []
    content = result.get("content")
    for item in content if isinstance(content, list) else []:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text", "")))
        elif isinstance(item, dict):
            parts.append(f"[{item.get('type')} content, not text]")
    if "structuredContent" in result:
        label += ", structuredContent"
    if not isinstance(content, list) or not content:
        label += ", no content"
    return label, "\n".join(parts)


def value_in_text(call: dict[str, Json], text: str) -> bool | None:
    """Is the bad value that was sent quoted back in the reply text? None when nothing was sent
    in place of the argument (a missing argument) or the value is not a string or a number."""
    changed = call.get("changed")
    arguments = call.get("arguments")
    if not isinstance(changed, str) or not isinstance(arguments, dict) or changed not in arguments:
        return None
    value = arguments[changed]
    if isinstance(value, list) and value:
        value = value[-1]
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    return str(value) in text


def code_span(text: str) -> str:
    """Exact text for a Markdown table cell: JSON string escapes, pipes escaped for the table."""
    encoded = json.dumps(text, ensure_ascii=False).replace("|", "\\|")
    fence = "``" if "`" in encoded else "`"
    pad = " " if "`" in encoded else ""
    return f"{fence}{pad}{encoded}{pad}{fence}"


# --------------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------------
def parse_pairs(pairs: list[str], flag: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for pair in pairs:
        key, separator, value = pair.partition("=")
        if not separator or not key:
            raise SystemExit(f"{flag} wants KEY=VALUE, got {pair!r}")
        parsed[key] = value
    return parsed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--server", required=True, help="a short name; names the output files")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--var", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--env", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--redact", action="append", default=[], metavar="PATH=NAME")
    parser.add_argument("--cwd")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv[1:])
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        raise SystemExit("give the server command after --")

    variables = parse_pairs(args.var, "--var")
    redactions = sorted(parse_pairs(args.redact, "--redact").items(), key=lambda p: -len(p[0]))

    def hide(text: str) -> str:
        for path, name in redactions:
            text = text.replace(path, name)
        return text

    plan_bytes = Path(args.plan).read_bytes()
    plan = substitute(json.loads(plan_bytes), variables)
    plan_tools: dict[str, Json] = plan.get("tools", {})
    declared_read_only = plan.get("read_only_tools")
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        **parse_pairs(args.env, "--env"),
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records: list[Json] = [{
        "record": "meta",
        "server": args.server,
        "command": command,
        "cwd": args.cwd,
        "environment": environment,
        "variables": variables,
        "protocol_requested": PROTOCOL_REQUESTED,
        "plan_file": str(Path(args.plan).resolve()),
        "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }]  # fmt: skip
    sequence = 0

    def exchange(phase: str, method: str, params: Json, **extra: Json) -> Json | None:
        nonlocal sequence
        sequence += 1
        request, reply, others, problem = server.request(method, params)
        records.append({
            "record": "exchange", "seq": sequence, "phase": phase, **extra,
            "request": request, "reply": reply, "problem": problem, "other_messages": others,
        })  # fmt: skip
        return reply

    server = Server(command, environment, args.cwd, args.timeout)
    rows: list[dict[str, Json]] = []
    tools: list[Json] = []
    server_info: Json = None
    protocol_answered: Json = None
    fatal: str | None = None
    try:
        reply = exchange(
            "initialize", "initialize",
            {"protocolVersion": PROTOCOL_REQUESTED, "capabilities": {}, "clientInfo": CLIENT_INFO},
        )  # fmt: skip
        if reply is None or "result" not in reply:
            fatal = "initialize did not succeed"
        else:
            server_info = reply["result"].get("serverInfo")
            protocol_answered = reply["result"].get("protocolVersion")
            notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
            server.send(notification)
            records.append({"record": "notification_sent", "message": notification})
            cursor: Json = None
            while True:
                reply = exchange("tools/list", "tools/list", {"cursor": cursor} if cursor else {})
                if reply is None or "result" not in reply:
                    fatal = "tools/list did not succeed"
                    break
                tools.extend(reply["result"].get("tools", []))
                cursor = reply["result"].get("nextCursor")
                if not cursor:
                    break
        if fatal is None:
            for tool in tools:
                name = tool.get("name")
                annotations = tool.get("annotations")
                hint = annotations.get("readOnlyHint") if isinstance(annotations, dict) else None
                if hint is True:
                    read_only, source = True, "server: readOnlyHint true"
                elif hint is False:
                    read_only, source = False, "server: readOnlyHint false"
                elif isinstance(declared_read_only, list) and name in declared_read_only:
                    read_only, source = True, "plan (the server sends no readOnlyHint)"
                else:
                    read_only, source = False, "no readOnlyHint, and the plan does not name it"
                tool["_read_only"], tool["_read_only_source"] = read_only, source
                records.append({
                    "record": "tool", "name": name, "inputSchema": tool.get("inputSchema"),
                    "annotations": annotations, "read_only": read_only, "read_only_source": source,
                })  # fmt: skip
            for tool in tools:
                if not tool["_read_only"]:
                    continue
                name = tool["name"]
                for call in build_calls(tool, plan_tools.get(name, {})):
                    row: dict[str, Json] = {"tool": name, "kind": call["kind"]}
                    if "skip" in call:
                        row.update(sent=False, outcome="not sent", text="", what=call["skip"])
                        records.append({
                            "record": "not_sent", "tool": name, "kind": call["kind"],
                            "reason": call["skip"],
                        })  # fmt: skip
                    else:
                        reply = exchange(
                            "tools/call", "tools/call",
                            {"name": name, "arguments": call["arguments"]},
                            tool=name, kind=call["kind"], what=call["what"],
                            changed=call["changed"],
                        )  # fmt: skip
                        outcome, text = outcome_of(reply, records[-1]["problem"])
                        changed = call["changed"]
                        row.update(
                            sent=True, outcome=outcome, text=text, what=call["what"],
                            arguments=call["arguments"], changed=changed,
                            names_changed=(changed in text) if isinstance(changed, str) else None,
                            names_value=value_in_text(call, text),
                            names_tool=name in text,
                        )  # fmt: skip
                    rows.append(row)
    finally:
        return_code, stderr = server.stop()
    records.append({"record": "end", "server_return_code": return_code, "fatal": fatal})

    base = out_dir / args.server
    records[0]["redactions"] = dict(redactions)
    with open(f"{base}.jsonl", "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(hide(json.dumps(record, ensure_ascii=False, sort_keys=True)) + "\n")
    Path(f"{base}.stderr.txt").write_bytes(
        hide(stderr.decode("utf-8", "surrogateescape")).encode("utf-8", "surrogateescape")
    )

    # ---------------------------------------------------------------------------- the tables
    lines: list[str] = [f"# Probe of `{args.server}`", ""]
    lines += [
        f"- Command: `{' '.join(command)}`",
        f"- Server says it is: `{json.dumps(server_info, ensure_ascii=False)}`",
        f"- Protocol version asked for `{PROTOCOL_REQUESTED}`, answered `{protocol_answered}`",
        f"- Plan: `{Path(args.plan).name}` (sha256 `{records[0]['plan_sha256']}`)",
        f"- Started (UTC): {records[0]['started_utc']}",
        f"- Raw requests and replies: `{args.server}.jsonl`; "
        f"server stderr: `{args.server}.stderr.txt`",
        "- No model was called. Only read-only tools were called.",
        "",
    ]
    if fatal:
        lines += [f"**The probe stopped: {fatal}.**", ""]
    read_only_tools = [tool for tool in tools if tool.get("_read_only")]
    lines += [
        "## Tools",
        "",
        "| tool | read-only | why | required arguments | all arguments |",
        "|---|---|---|---|---|",
    ]
    for tool in tools:
        schema = as_dict(tool.get("inputSchema"))
        properties = as_dict(schema.get("properties"))
        lines.append(
            f"| `{tool.get('name')}` | {'yes' if tool['_read_only'] else 'no'} | "
            f"{tool['_read_only_source']} | {', '.join(schema.get('required', [])) or '(none)'} | "
            f"{', '.join(properties) or '(none)'} |"
        )
    sent_bad = [row for row in rows if row["sent"] and row["kind"] != "good"]
    sent_good = [row for row in rows if row["sent"] and row["kind"] == "good"]
    lines += [
        "",
        f"{len(tools)} tools listed, {len(read_only_tools)} read-only. "
        f"{len(sent_good)} good calls and {len(sent_bad)} bad calls sent.",
        "",
        "## Calls",
        "",
        "The reply text is exact, written as a JSON string (so `\\n` is a line break). The text of "
        f"a good call is cut after {GOOD_TEXT_LIMIT} characters; the text of a bad call is never "
        "cut. The last column is three plain substring tests, not a judgement: is the name of the "
        "argument "
        "that was left out or changed in the reply text; is the bad value that was sent in it "
        "(n/a when an argument was left out); is the tool's name in it. A word such as `path` can "
        "be in a reply without the reply saying which argument was wrong: read the text.",
        "",
        "| tool | call | what was sent | outcome | exact reply text "
        "| argument name / bad value / tool name in the text |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        if not row["sent"]:
            lines.append(f"| `{row['tool']}` | {row['kind']} | not sent: {row['what']} | | | |")
            continue
        text = row["text"]
        if row["kind"] == "good" and len(text) > GOOD_TEXT_LIMIT:
            shown = code_span(text[:GOOD_TEXT_LIMIT]) + f" ... ({len(text)} characters in all)"
        else:
            shown = code_span(text)
        sent_words = f"{row['what']}: `{json.dumps(row['arguments'], ensure_ascii=False)}`".replace(
            "|", "\\|"
        )
        if row["kind"] == "good":
            named = ""
        else:
            flags = (row["names_changed"], row["names_value"], row["names_tool"])
            named = " / ".join("n/a" if flag is None else "yes" if flag else "no" for flag in flags)
        lines.append(
            f"| `{row['tool']}` | {row['kind']} | {sent_words} | {row['outcome']} "
            f"| {shown} | {named} |"
        )

    lines += [
        "",
        "## Counts",
        "",
        "| call kind | sent | not sent | outcomes |",
        "|---|---|---|---|",
    ]
    for kind in KINDS:
        of_kind = [row for row in rows if row["kind"] == kind]
        tally: dict[str, int] = {}
        for row in of_kind:
            if row["sent"]:
                tally[row["outcome"]] = tally.get(row["outcome"], 0) + 1
        words = "; ".join(f"{count} x {label}" for label, count in sorted(tally.items()))
        lines.append(
            f"| {kind} | {sum(1 for row in of_kind if row['sent'])} | "
            f"{sum(1 for row in of_kind if not row['sent'])} | {words} |"
        )
    failed_good = [
        row
        for row in sent_good
        if not row["outcome"].startswith(("isError false", "isError absent"))
    ]
    if failed_good:
        lines += [
            "",
            "**Good calls that did not succeed (check the plan):** "
            + ", ".join(f"`{row['tool']}`" for row in failed_good),
        ]
    Path(f"{base}.md").write_text(hide("\n".join(lines) + "\n"), encoding="utf-8")

    print(
        f"{args.server}: {len(tools)} tools, {len(read_only_tools)} read-only, "
        f"{len(sent_good)} good calls, {len(sent_bad)} bad calls"
        + (
            f", good calls that failed: {[row['tool'] for row in failed_good]}"
            if failed_good
            else ""
        )
        + (f"; STOPPED: {fatal}" if fatal else "")
    )
    print(f"wrote {base}.jsonl, {base}.md, {base}.stderr.txt")
    return 1 if fatal else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
