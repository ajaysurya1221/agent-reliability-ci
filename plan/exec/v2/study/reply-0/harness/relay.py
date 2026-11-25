"""Read-only stdio MCP relay. Normalisation follows the Task C relay N1 through N9."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import selectors
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

STUDY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDY))
from tasks.f2_parity import relay_result  # noqa: E402

Json = Any
Row = dict[str, Any]
ALLOWED_CODES = {-32600, -32601, -32602}
DROPPED_CAPABILITIES = ("roots", "sampling", "elicitation")
DENY = "(version 1)(allow default)(deny network*)"


def mapping(items: list[str]) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for item in items:
        name, sep, value = item.partition("=")
        if not sep or name in pairs:
            raise ValueError("expected unique NAME=VALUE")
        pairs[name] = value
    return pairs


def rewrite(rule: Row, name: str, arguments: Row, result: Row) -> Row:
    if name != rule["tool"] or result.get("isError") is not rule["is_error"]:
        return result
    if rule["tool"] == "search_files":
        if not isinstance(arguments.get("pattern"), str):
            return result
        cell = {
            "tool": name,
            "reply_pattern": rule["text_matches"],
            "reply_is_error": rule["is_error"],
            "sentence": rule["replace_text"],
            "sentence_when": rule["when"],
        }
        return relay_result(cell, {"name": name, "arguments": arguments}, result)
    blocks = result.get("content")
    if not isinstance(blocks, list) or len(blocks) != 1 or blocks[0].get("type") != "text":
        return result
    old = blocks[0]["text"]
    when = rule["when"]
    if not re.search(rule["text_matches"], old):
        return result
    if any(arguments.get(k) is None for k in when.get("arg_present", [])):
        return result
    for k, pattern in when.get("arg_matches", {}).items():
        if not isinstance(arguments.get(k), str) or not re.fullmatch(pattern, arguments[k]):
            return result

    def fill(match: re.Match[str]) -> str:
        value = arguments[match[2]]
        text = value if isinstance(value, str) else json.dumps(value)
        return os.path.dirname(text) if match[1] == "parent" else text

    text = re.sub(r"\{(arg|parent):([A-Za-z_]+)\}", fill, rule["replace_text"])
    delivered = copy.deepcopy(result)
    delivered["content"][0]["text"] = text
    if isinstance(delivered.get("structuredContent"), dict) and (
        delivered["structuredContent"].get("content") == old
    ):
        delivered["structuredContent"]["content"] = text
    return delivered


def provenance(command: list[str], env: dict[str, str]) -> dict[str, str]:
    """Hash the executable and the source files resolved by the selected entry point."""
    program = Path(command[0])
    executable = shutil.which(
        str(STUDY / program) if program.parent != Path(".") else command[0], path=env["PATH"]
    )
    if not executable:
        raise ValueError("server executable missing")
    files = {"executable": Path(executable)}
    if "-m" in command:
        module = command[command.index("-m") + 1]
        roots = [STUDY / p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]
        roots.extend(sorted(Path(executable).parent.parent.glob("lib/python*/site-packages")))
        if module == "mcp_server_git":
            package = next(root / module for root in roots if (root / module).is_dir())
            files.update({f"{module}/{f.name}": f for f in package.glob("*.py")})
        elif module == "arci.mcp_toolset_server":
            for rel in ("arci/mcp_toolset_server.py", "orderdesk_world.py"):
                files[rel] = next(root / rel for root in roots if (root / rel).is_file())
        else:
            raise ValueError("unsupported module entry point")
    else:
        entry = next(STUDY / p for p in command[1:] if p.endswith((".py", ".js")))
        files[entry.name] = entry
        if entry.name == "index.js":
            files["server.js"] = entry.with_name("server.js")
    return {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in files.items()}


class Relay:
    def __init__(self, args: argparse.Namespace, command: list[str]) -> None:
        self.args = args
        self.workdir = Path(os.environ["ARCI_WORKDIR"])
        self.ledger = (self.workdir / "ledger.jsonl").open("x", encoding="utf-8")
        self.selector = selectors.DefaultSelector()
        self.upstream: subprocess.Popen[bytes] | None = None
        self.commands = {key: json.loads(value) for key, value in mapping(args.server).items()}
        if command:
            if "shipped" in self.commands:
                raise ValueError("duplicate shipped server")
            self.commands["shipped"] = command
        self.rule_paths = mapping(args.rules)
        self.module_roots = mapping(args.module_root)
        self.rules: list[Row] = []
        self.pending: dict[str, Row] = {}
        self.own_ids = self.seq = 0
        self.allowed: set[str] = set()
        self.arm: Row = {}
        self.launch: Row = {}

    def note(self, record: Row) -> None:
        self.ledger.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
        self.ledger.flush()

    def count(self, what: str, **more: Any) -> None:
        code, _, detail = what.partition(" ")
        self.note({"record": "norm", "code": code, "detail": detail, **more})

    @property
    def server(self) -> subprocess.Popen[bytes]:
        assert self.upstream is not None
        return self.upstream

    def ensure_server(self) -> None:
        if self.upstream is not None:
            return
        try:
            arm = json.loads((self.workdir / "reply0-arm.json").read_bytes())
            if set(arm) != {"arm", "server", "rules"} or not isinstance(arm["arm"], str):
                raise ValueError("bad arm file")
            if arm["server"] not in ("edited", "shipped") or arm["rules"] not in (
                "none",
                "naming",
                "generic",
            ):
                raise ValueError("bad arm selection")
            self.arm = arm
            self.note({"record": "arm", **arm})
            if arm["rules"] != "none":
                self.rules = json.loads(Path(self.rule_paths[arm["rules"]]).read_bytes())
                if not self.rules:
                    raise ValueError("empty rule set")
            command: list[str] = self.commands[arm["server"]]
        except (OSError, TypeError, KeyError, ValueError):
            self.note({"record": "error", "reason": "invalid arm or configuration"})
            raise
        task = json.loads(Path(os.environ["ARCI_TASK_FILE"]).read_bytes())
        self.note({"record": "task", "key_id": task["key_id"]})
        env = {"PATH": os.environ.get("PATH", os.defpath), **mapping(self.args.env)}
        if arm["server"] in self.module_roots:
            env["PYTHONPATH"] = self.module_roots[arm["server"]]
        hashes = provenance(command, env)
        prefix = [] if os.environ.get("REPLY0_NO_SANDBOX") == "1" else ["sandbox-exec", "-p", DENY]
        actual = prefix + command
        stable = [
            "{task_file}"
            if p == os.environ["ARCI_TASK_FILE"]
            else "{workdir}"
            if p == str(self.workdir)
            else p
            for p in actual
        ]
        self.launch = {"argv": stable, "sha256": hashes, "module_root": env.get("PYTHONPATH")}
        self.upstream = subprocess.Popen(
            actual, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env
        )
        assert self.upstream.stdout is not None
        self.selector.register(self.upstream.stdout.fileno(), selectors.EVENT_READ, "server")
        self.count("N9 minimal server environment", names=sorted(env))

    def to_server(self, message: Row) -> None:
        assert self.server.stdin is not None
        self.server.stdin.write((json.dumps(message) + "\n").encode())
        self.server.stdin.flush()

    def to_client(self, message: Row) -> None:
        print(json.dumps(message), flush=True)

    def from_client(self, raw: bytes) -> None:
        message: Json = json.loads(raw)
        method = message.get("method")
        self.ensure_server()
        if "id" not in message:  # the client's own notification
            self.to_server(message)
            return
        asked: dict[str, Json] = {"method": method, "id": message["id"]}
        if method == "initialize":
            capabilities = (message.get("params") or {}).get("capabilities")
            if isinstance(capabilities, dict):
                for name in DROPPED_CAPABILITIES:
                    if name in capabilities:
                        del capabilities[name]
                        self.count(f"N1 capability removed: {name}")
        if method == "tools/list":
            asked["tools"] = []
        if method == "tools/call":
            params = message.get("params") or {}
            name = params.get("name")
            if name not in self.allowed:
                self.count("N7 call to a hidden tool refused")
                self.note(
                    {"record": "refused", "tool": name, "arguments": params.get("arguments", {})}
                )
                error = {"code": -32601, "message": f"unknown tool {name}"}
                self.to_client({"jsonrpc": "2.0", "id": message["id"], "error": error})
                return
            asked["tool"] = name
            asked["arguments"] = params.get("arguments", {})
        self.pending[json.dumps(message["id"])] = asked
        self.to_server(message)

    # ----- server -> client ------------------------------------------------------------------
    def from_server(self, raw: bytes) -> None:
        try:
            message: Json = json.loads(raw)
        except ValueError:
            message = None
        if not isinstance(message, dict):
            self.count("N8 line that is not a JSON object dropped")
            return
        if isinstance(message.get("method"), str):
            if "id" in message:
                self.count(f"N2 server request answered by the relay: {message['method']}")
                reply: dict[str, Json] = {"jsonrpc": "2.0", "id": message["id"]}
                if message["method"] == "ping":
                    reply["result"] = {}
                else:
                    reply["error"] = {"code": -32601, "message": "Method not found"}
                self.to_server(reply)
            else:
                self.count(f"N3 server notification dropped: {message['method']}")
            return
        asked = self.pending.pop(json.dumps(message.get("id")), None)
        if asked is None:  # nothing was asked under this id; let the boundary judge it
            self.to_client(message)
            return
        if asked["method"] == "initialize" and isinstance(message.get("result"), dict):
            result = message["result"]
            self.note(
                {
                    "record": "start",
                    **self.launch,
                    "protocolVersion": result.get("protocolVersion"),
                    "serverInfo": result.get("serverInfo"),
                }
            )
        if asked["method"] == "tools/list" and isinstance(message.get("result"), dict):
            self.tools_page(asked, message)
            return
        if asked["method"] == "tools/call":
            message = self.tool_reply(asked, message)
        message["id"] = asked["id"]
        self.to_client(message)

    def tools_page(self, asked: dict[str, Json], message: dict[str, Json]) -> None:
        result = message["result"]
        asked["tools"].extend(result.get("tools") or [])
        cursor = result.get("nextCursor")
        if cursor:  # N6: fetch the next page ourselves
            self.count("N6 further tools/list page fetched by the relay")
            self.own_ids += 1
            own_id = f"relay-{self.own_ids}"
            self.pending[json.dumps(own_id)] = asked
            self.to_server(
                {
                    "jsonrpc": "2.0",
                    "id": own_id,
                    "method": "tools/list",
                    "params": {"cursor": cursor},
                }
            )
            return
        kept = []
        for tool in asked["tools"]:
            name = tool.get("name")
            read_only = (tool.get("annotations") or {}).get("readOnlyHint") is True
            orderdesk_lookup = "orderdesk_world.py" in self.launch["sha256"] and name in (
                "lookup_order",
                "check_stock",
            )
            selected = not self.args.allow_tool or name in self.args.allow_tool
            if selected and (read_only or orderdesk_lookup):
                kept.append(tool)
        self.allowed = {tool["name"] for tool in kept}
        hidden = [
            tool.get("name") for tool in asked["tools"] if tool.get("name") not in self.allowed
        ]
        if hidden:
            self.count("N7 tools hidden from tools/list", names=hidden)
        merged = {key: value for key, value in result.items() if key != "nextCursor"}
        merged["tools"] = kept
        self.to_client({"jsonrpc": "2.0", "id": asked["id"], "result": merged})

    def tool_reply(self, asked: dict[str, Json], message: dict[str, Json]) -> dict[str, Json]:
        fired = None
        from_server: Json = (
            message.get("result") if "result" in message else {"error": message.get("error")}
        )
        from_server = json.loads(json.dumps(from_server))
        error = message.get("error")
        if isinstance(error, dict) and error.get("code") not in ALLOWED_CODES:
            self.count(f"N5 JSON-RPC error {error.get('code')} -> isError result")
            text = str(error.get("message", ""))
            message = {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {"content": [{"type": "text", "text": text}], "isError": True},
            }
        result = message.get("result")
        if isinstance(result, dict):
            if "isError" not in result:
                result["isError"] = False
                self.count("N4 isError: false added")
            for index, rule in enumerate(self.rules):
                delivered = rewrite(rule, asked["tool"], asked["arguments"], result)
                if delivered != result:
                    message["result"] = delivered
                    fired = f"{self.arm['rules']}:{index}"
                    break
        self.note(
            {
                "record": "call",
                "seq": self.seq,
                "tool": asked["tool"],
                "arguments": asked["arguments"],
                "server_reply": from_server,
                "passed_on": message.get("result", {"error": message.get("error")}),
                "rule": fired,
            }
        )
        self.seq += 1
        return message

    def run(self) -> int:
        selector = self.selector
        selector.register(sys.stdin.buffer.fileno(), selectors.EVENT_READ, "client")
        buffers = {"client": bytearray(), "server": bytearray()}
        client_open = True
        while True:
            # Once the boundary has closed our input, give the real server two seconds to leave
            # by itself, then stop it. (After a clean trial the boundary kills this relay at
            # once with SIGKILL, so this path is taken only after a fault or an unanswered call.)
            if not client_open and self.upstream is None:
                return 0
            events = selector.select(timeout=None if client_open else 2.0)
            if not events:
                self.server.terminate()
                return 0
            for key, _ in events:
                source: str = key.data
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fd)
                    if source == "server":  # the real server is gone
                        return 0 if not client_open else 1
                    client_open = False
                    if self.upstream is not None and self.upstream.stdin is not None:
                        self.upstream.stdin.close()  # the stdio way to ask a server to leave
                    continue
                buffers[source].extend(chunk)
                if len(buffers[source]) > 1048576 and b"\n" not in buffers[source]:
                    raise ValueError("MCP line exceeds 1 MiB")
                while (newline := buffers[source].find(b"\n")) >= 0:
                    if newline > 1048576:
                        raise ValueError("MCP line exceeds 1 MiB")
                    line = bytes(buffers[source][: newline + 1])
                    del buffers[source][: newline + 1]
                    if not line.strip():
                        continue
                    if source == "client":
                        self.from_client(line)
                    else:
                        self.from_server(line)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", action="store_true", help="ledger is always enabled")
    parser.add_argument("--rules", action="append", default=[])
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument("--module-root", action="append", default=[])
    parser.add_argument("--allow-tool", action="append", default=[])
    parser.add_argument("--server", action="append", default=[])
    argv = sys.argv[1:]
    split = argv.index("--") if "--" in argv else len(argv)
    os.chdir(STUDY)  # Study-relative rehearsal inputs have one working directory.
    relay = Relay(parser.parse_args(argv[:split]), argv[split + 1 :])
    try:
        return relay.run()
    finally:
        relay.selector.close()
        relay.ledger.close()
        if relay.upstream is not None:
            if relay.server.stdin:
                relay.server.stdin.close()
            try:
                relay.server.wait(timeout=2)
            except subprocess.TimeoutExpired:
                relay.server.kill()
                relay.server.wait()
            if relay.server.stdout:
                relay.server.stdout.close()


if __name__ == "__main__":
    raise SystemExit(main())
