"""A minimal real Ollama tool-calling agent using one stdio MCP server."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol, TextIO, TypeAlias, cast
from urllib.parse import urlparse

if __package__:
    from .prompts import PROMPTS
else:  # Supports ``python agent.py`` from this directory.
    from prompts import PROMPTS

OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
REQUEST_TIMEOUT_SECONDS = 60.0
JsonPrimitive: TypeAlias = bool | int | float | str | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
ChatFunction = Callable[[str, JsonObject], JsonObject]


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        del fp, newurl
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, None)


def _loopback_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _RejectRedirects())


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


def ollama_chat(url: str, payload: JsonObject) -> JsonObject:
    validate_ollama_url(url)
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = _loopback_opener()
    with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        value: Any = json.loads(response.read())
    return _object(value, "Ollama response")


class McpClient(Protocol):
    def list_tools(self) -> list[JsonObject]: ...

    def call_tool(self, name: str, arguments: JsonObject) -> tuple[str, bool]: ...


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
                    "protocolVersion": "2026-07-28",
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


def run_agent(
    task: JsonObject,
    session: McpClient,
    *,
    prompt_variant: str,
    model: str,
    max_steps: int,
    chat: ChatFunction = ollama_chat,
    transcript: TextIO = sys.stderr,
) -> str | None:
    """Run the bounded model/tool loop; ``chat`` is injectable for offline tests."""
    if prompt_variant not in PROMPTS:
        raise ValueError(f"unknown prompt variant: {prompt_variant}")
    if max_steps < 1:
        raise ValueError("max_steps must be at least 1")
    tools = _tool_definitions(session.list_tools())
    messages: list[JsonValue] = [
        {"role": "system", "content": PROMPTS[prompt_variant]},
        {
            "role": "user",
            "content": "Complete this task: " + json.dumps(task, sort_keys=True),
        },
    ]
    for step in range(1, max_steps + 1):
        payload: JsonObject = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.7},
        }
        response = chat(OLLAMA_CHAT_URL, payload)
        message = _object(response.get("message"), "Ollama message")
        messages.append(message)
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            print(f"assistant: {content.strip()}", file=transcript)
        raw_calls = message.get("tool_calls", [])
        if not isinstance(raw_calls, list):
            raise TypeError("Ollama tool_calls must be a list")
        if not raw_calls:
            return content if isinstance(content, str) else ""
        for raw_call in raw_calls:
            call = _object(raw_call, "Ollama tool call")
            function = _object(call.get("function"), "Ollama tool function")
            name = function.get("name")
            if not isinstance(name, str):
                raise TypeError("Ollama tool call name must be a string")
            arguments = _object(function.get("arguments", {}), "Ollama tool arguments")
            text, is_error = session.call_tool(name, arguments)
            status = "error" if is_error else "ok"
            print(f"tool {name} ({status}): {text}", file=transcript)
            messages.append({"role": "tool", "tool_name": name, "content": text})
        if step == max_steps:
            print(f"stopped after {max_steps} model steps", file=transcript)
    return None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcp-config", required=True)
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--prompt-variant", choices=("a", "b"), required=True)
    parser.add_argument("--model", default="qwen3.5:4b-mlx")
    parser.add_argument("--max-steps", type=int, default=8)
    return parser


def _one_line(exc: BaseException) -> str:
    detail = str(exc).replace("\r", " ").replace("\n", " ").strip()
    return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    session: McpSession | None = None
    try:
        task_value: Any = json.loads(Path(cast(str, args.task_file)).read_text(encoding="utf-8"))
        task = _object(task_value, "task")
        session = McpSession(cast(str, args.mcp_config))
        result = run_agent(
            task,
            session,
            prompt_variant=cast(str, args.prompt_variant),
            model=cast(str, args.model),
            max_steps=cast(int, args.max_steps),
        )
        if result is None:
            return 1
    except Exception as exc:
        print(f"error: {_one_line(exc)}", file=sys.stderr)
        return 1
    finally:
        if session is not None:
            session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
