"""Reply-0 scripted opening, stdio MCP tool loop and byte-level chat receipts."""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol, TypeAlias, cast
from urllib.parse import urlparse

OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
REQUEST_TIMEOUT_SECONDS = 60.0
JsonPrimitive: TypeAlias = bool | int | float | str | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
Capture = Callable[[bytes], None]
Transport = Callable[[int, bytes, Capture], tuple[int, bytes]]


def _object(value: object, label: str) -> JsonObject:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise TypeError(f"{label} must be a JSON object")
    return cast(JsonObject, value)


def validate_ollama_url(url: str) -> None:
    """Reject every destination except Ollama's literal IPv4 loopback endpoint."""
    parsed = urlparse(url)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port != 11434
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != "/api/chat"
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Ollama chat URL must be http://127.0.0.1:11434/api/chat")


def ollama_chat(
    body: bytes, capture: Capture, receipt: Receipt, task: JsonObject, model: str, prompt: str
) -> tuple[int, bytes]:
    """Send the same immutable body observed at the HTTP connection's write boundary."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from harness.wiring_check import authorize_trial

    try:
        authorize_trial(receipt.state, task, model, prompt)
    except (KeyError, ValueError, OSError) as exc:
        raise BackendError("live trial admission failed") from exc
    validate_ollama_url(OLLAMA_CHAT_URL)
    connection = http.client.HTTPConnection("127.0.0.1", 11434, timeout=REQUEST_TIMEOUT_SECONDS)
    try:
        connection.putrequest("POST", "/api/chat")
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", str(len(body)))
        connection.endheaders()
        capture(body)
        connection.send(body)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


class McpClient(Protocol):
    def list_tools(self) -> list[JsonObject]: ...

    def call_tool(self, name: str, arguments: JsonObject) -> tuple[str, bool]: ...


EX_TEMPFAIL = 75


class McpRpcError(RuntimeError):
    """An MCP JSON-RPC error that should be shown to the model as a tool error."""


class McpSession:
    """Synchronous MCP client for the single configured stdio server."""

    def __init__(self, config_path: str | Path) -> None:
        config_value: Any = json.loads(Path(config_path).read_text(encoding="utf-8"))
        config = _object(config_value, "MCP config")
        servers = _object(config.get("mcpServers"), "mcpServers")
        if len(servers) != 1:
            raise ValueError("MCP config must contain exactly one server")
        entry = _object(next(iter(servers.values())), "MCP server entry")
        command = entry.get("command")
        raw_args = entry.get("args", [])
        raw_env = entry.get("env", {})
        if not isinstance(command, str):
            raise TypeError("MCP server command must be a string")
        if not isinstance(raw_args, list) or any(not isinstance(item, str) for item in raw_args):
            raise TypeError("MCP server args must be strings")
        env_values = _object(raw_env, "MCP server env")
        if any(not isinstance(value, str) for value in env_values.values()):
            raise TypeError("MCP server env values must be strings")
        args = cast(list[str], raw_args)
        env = cast(dict[str, str], env_values)
        self._process = subprocess.Popen(
            [command, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env={**os.environ, **env},
        )
        self._next_id = 0
        try:
            self._rpc(
                "initialize",
                {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "arci-ollama-agent", "version": "0.2"},
                },
            )
            self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        except BaseException:
            self.close()
            raise

    def _send(self, message: JsonObject) -> None:
        stream = self._process.stdin
        if stream is None:
            raise RuntimeError("MCP server stdin is unavailable")
        stream.write(json.dumps(message, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()

    def _rpc(self, method: str, params: JsonObject | None = None) -> JsonObject:
        self._next_id += 1
        request_id = f"req-{self._next_id}"
        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params or {},
            }
        )
        stream = self._process.stdout
        if stream is None:
            raise RuntimeError("MCP server stdout is unavailable")
        while True:
            line = stream.readline()
            if not line:
                raise RuntimeError("MCP server exited before replying")
            value: Any = json.loads(line)
            reply = _object(value, "MCP reply")
            if reply.get("id") == request_id:
                if "error" in reply:
                    raise McpRpcError(f"MCP RPC error: {reply['error']}")
                return _object(reply.get("result"), "MCP result")

    def list_tools(self) -> list[JsonObject]:
        result = self._rpc("tools/list")
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise TypeError("tools/list result must contain a tool list")
        return [_object(tool, "tool definition") for tool in tools]

    def call_tool(self, name: str, arguments: JsonObject) -> tuple[str, bool]:
        try:
            result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        except McpRpcError as exc:
            return str(exc), True
        content = result.get("content", [])
        if not isinstance(content, list):
            raise TypeError("tools/call content must be a list")
        parts: list[str] = []
        for item in content:
            block = _object(item, "MCP content block")
            text = block.get("text")
            if block.get("type") == "text" and isinstance(text, str):
                parts.append(text)
        return "\n".join(parts), result.get("isError") is True

    def close(self) -> None:
        if self._process.stdin is not None and not self._process.stdin.closed:
            with suppress(OSError):
                self._process.stdin.close()
        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=10)
        finally:
            if self._process.stdout is not None:
                self._process.stdout.close()


def _tool_definitions(tools: list[JsonObject]) -> list[JsonValue]:
    definitions: list[JsonValue] = []
    for tool in tools:
        name = tool.get("name")
        if not isinstance(name, str):
            raise TypeError("MCP tool name must be a string")
        description = tool.get("description")
        schema = tool.get("inputSchema", {"type": "object"})
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description if isinstance(description, str) else name,
                    "parameters": schema,
                },
            }
        )
    return definitions


ARMS = {
    "naming-sentence": ("naming", "shipped"),
    "generic-sentence": ("generic", "shipped"),
    "reply-as-given": ("none", "shipped"),
    "edited-server": ("none", "edited"),
    "server-as-shipped": ("none", "shipped"),
    "clean": ("none", "shipped"),
}
MODELS = ("qwen3.5:4b-mlx-ctx32k", "gemma4:12b-mlx-ctx32k")


def atomic_json(path: Path, value: object, *, create: bool = False) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        tmp = Path(stream.name)
        try:
            stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False).encode() + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
            if create:
                os.link(tmp, path)
            else:
                os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)


class Receipt:
    def __init__(
        self, directory: Path, run: str, key_id: str, seed: int, side: str, label: str, opening: str
    ) -> None:
        if side not in ("baseline", "candidate"):
            raise ValueError("invalid scheduled arm")
        identity = [run, key_id, seed, side]
        digest = hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / (digest + ".json")
        self.exchanges: list[dict[str, Any]] = []
        self.calls: list[JsonObject] = []
        self.state: dict[str, Any] = {
            "run": run,
            "key_id": key_id,
            "seed": seed,
            "arci_arm": side,
            "arm": label,
            "opening": opening,
            "exchanges": self.exchanges,
            "calls": self.calls,
            "steps": 0,
            "answer": None,
            "complete": False,
        }

    def request(self, transport: Transport, payload: JsonObject) -> JsonObject:
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        index = len(self.exchanges)
        exchange: dict[str, Any] = {}

        def capture(outgoing: bytes) -> None:
            if exchange:
                raise ValueError("duplicate request capture")
            exchange.update(
                request_b64=base64.b64encode(outgoing).decode("ascii"),
                sha256=hashlib.sha256(outgoing).hexdigest(),
                status=None,
                response_b64=None,
            )
            self.exchanges.append(exchange)
            self.state["steps"] = index + 1
            atomic_json(self.path, self.state, create=index == 0)

        status, raw = transport(index, body, capture)
        if not exchange:
            raise ValueError("transport omitted request capture")
        exchange.update(status=status, response_b64=base64.b64encode(raw).decode("ascii"))
        atomic_json(self.path, self.state)
        if status != 200:
            raise ConnectionError(f"chat HTTP {status}")
        try:
            response = _object(json.loads(raw), "chat response")
        except (TypeError, ValueError) as exc:
            raise BackendError("malformed chat response") from exc
        exchange["done_reason"] = response.get("done_reason")
        atomic_json(self.path, self.state)
        if response.get("model") != payload["model"] or response.get("done") is not True:
            raise BackendError("non-streaming model identity or completion differs")
        return response

    def finish(self, workdir: Path, answer: str | None) -> None:
        atomic_json(workdir / "answer.json", {"answer": answer})
        self.state.update(complete=True, answer=answer)
        atomic_json(self.path, self.state)


class BackendError(ConnectionError):
    """A malformed backend response invalidates the trial."""


class OpeningUnavailable(Exception):
    pass


def run_agent(
    task: JsonObject,
    session: McpClient,
    receipt: Receipt,
    *,
    prompt: str,
    model: str,
    opening: str,
    empty_text: str | None,
    transport: Transport,
    max_steps: int = 8,
) -> str | None:
    catalogue = session.list_tools()
    tools = _tool_definitions(catalogue)
    messages: list[JsonValue] = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": task["ask"]},
    ]

    def deliver(function: JsonObject, *, scripted: bool = False) -> None:
        name = function["name"]
        if not isinstance(name, str):
            raise ValueError("tool name must be a string")
        arguments = _object(function.get("arguments", {}), "tool arguments")
        receipt.calls.append({"name": name, "arguments": arguments})
        text, _ = session.call_tool(name, arguments)
        if scripted and task["cell"] == "C0" and opening == "bad" and text == "":
            text = empty_text or ""
        messages.append({"role": "tool", "tool_name": name, "content": text})

    if opening != "none":
        call = _object(task["bad" if opening == "bad" else "clean"], "opening")
        if call["name"] not in [t["name"] for t in catalogue]:
            raise OpeningUnavailable
        messages.append({"role": "assistant", "content": "", "tool_calls": [{"function": call}]})
        deliver(call, scripted=True)
    for _ in range(max_steps):
        response = receipt.request(
            transport,
            {
                "model": model,
                "messages": messages,
                "tools": tools,
                "stream": False,
                "think": False,
                "options": {"temperature": 0.7},
            },
        )
        message_value = response.get("message")
        if not isinstance(message_value, dict) or message_value.get("role") != "assistant":
            raise BackendError("missing assistant message")
        message = message_value
        messages.append(message)
        calls = message.get("tool_calls", [])
        if not isinstance(calls, list):
            raise BackendError("tool_calls must be an array")
        if not calls:
            content = message.get("content")
            if not isinstance(content, str):
                raise BackendError("terminal assistant content must be a string")
            return content
        functions: list[JsonObject] = []
        for call in calls:
            try:
                function = _object(_object(call, "tool call")["function"], "function")
                if not isinstance(function.get("name"), str):
                    raise TypeError("tool name must be a string")
                _object(function.get("arguments", {}), "tool arguments")
            except (KeyError, TypeError) as exc:
                raise BackendError("malformed assistant tool call") from exc
            functions.append(function)
        for function in functions:
            deliver(function)
    return None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcp-config", type=Path, required=True)
    parser.add_argument("--task-file", type=Path, required=True)
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--opening", choices=("bad", "clean", "none"), required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--replace-empty-opening", metavar="SENTENCE")
    parser.add_argument("--empty-fallback-null", action="store_true")
    parser.add_argument("--offline", type=Path)
    args = parser.parse_args(argv)
    task = _object(json.loads(args.task_file.read_bytes()), "task")
    workdir = Path(os.environ["ARCI_WORKDIR"])
    rules, server = ARMS[args.arm]
    empty_text = None
    if task["cell"] == "C0":
        rules = "none"
        if args.arm == "naming-sentence":
            empty_text = args.replace_empty_opening
        elif args.arm == "reply-as-given" and args.empty_fallback_null:
            empty_text = "null"
    if args.offline is None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from harness.wiring_check import authorize_trial

        try:
            authorize_trial(
                {
                    "run": args.run_id,
                    "arci_arm": os.environ["REPLY0_ARCI_ARM"],
                    "seed": int(os.environ["ARCI_SEED"]),
                    "arm": args.arm,
                    "opening": args.opening,
                },
                task,
                args.model,
                args.prompt,
            )
        except (KeyError, ValueError, OSError):
            print("live trial admission failed", file=sys.stderr)
            return EX_TEMPFAIL
    atomic_json(workdir / "reply0-arm.json", {"arm": args.arm, "rules": rules, "server": server})
    key_id = str(task["key_id"])
    receipt = Receipt(
        Path(os.environ["REPLY0_RECEIPTS"]),
        args.run_id,
        key_id,
        int(os.environ["ARCI_SEED"]),
        os.environ["REPLY0_ARCI_ARM"],
        args.arm,
        args.opening,
    )
    if args.offline is not None:
        plan = Path(__file__).resolve().parents[1] / args.offline
        # -P keeps the trial's current directory off the module search path.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from offline_model import chat

        def transport(step: int, body: bytes, capture: Capture) -> tuple[int, bytes]:
            capture(body)
            return chat(plan, key_id, step, body)
    else:

        def transport(step: int, body: bytes, capture: Capture) -> tuple[int, bytes]:
            return ollama_chat(body, capture, receipt, task, args.model, args.prompt)

    session = McpSession(args.mcp_config)
    try:
        answer = run_agent(
            task,
            session,
            receipt,
            prompt=args.prompt,
            model=args.model,
            opening=args.opening,
            empty_text=empty_text,
            transport=transport,
        )
        receipt.finish(workdir, answer)
    except OpeningUnavailable:
        return 70
    except (OSError, http.client.HTTPException):
        return EX_TEMPFAIL
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
