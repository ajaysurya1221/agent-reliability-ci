"""Expose a v0.1 Python ToolSet through the supported stdio MCP subset."""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, NoReturn, cast

from arci.interfaces import ToolSet, ToolSetFactory
from arci.schema import JsonValue

PROTOCOL_VERSION = "2026-07-28"


def _one_line(exc: BaseException) -> str:
    """Return a short diagnostic that cannot put a second protocol line on stdout."""
    try:
        detail = str(exc).replace("\r", " ").replace("\n", " ").strip()
    except BaseException:
        detail = ""
    name = type(exc).__name__
    return f"{name}: {detail}" if detail else name


def _resolve_factory(reference: str) -> ToolSetFactory:
    module_name, separator, attribute = reference.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError("toolset must be MODULE:FACTORY")
    with redirect_stdout(sys.stderr):
        target: Any = getattr(importlib.import_module(module_name), attribute)
    if not callable(target):
        raise TypeError(f"toolset factory is not callable: {reference}")
    return cast(ToolSetFactory, target)


def _load_task(path: str | None) -> dict[str, JsonValue]:
    if path is None:
        return {}
    value: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise TypeError("task file must contain a JSON object")
    return cast(dict[str, JsonValue], value)


def _json_text(value: JsonValue) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _result(value: JsonValue, *, is_error: bool = False) -> dict[str, JsonValue]:
    return {
        "resultType": "complete",
        "content": [{"type": "text", "text": _json_text(value) if not is_error else str(value)}],
        "isError": is_error,
    }


def _reply(request_id: JsonValue, *, result: JsonValue) -> dict[str, JsonValue]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: JsonValue, code: int, message: str) -> dict[str, JsonValue]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


_JSON_TYPES: dict[object, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
}


def _input_schema(tool: Callable[..., JsonValue]) -> JsonValue:
    """A JSON Schema for the tool's keyword arguments, read from its Python signature.

    A model can only call a tool correctly if it is told the parameter names. Parameters
    without a default are required; simple annotations become JSON types.
    """
    properties: dict[str, JsonValue] = {}
    required: list[JsonValue] = []
    try:
        parameters = inspect.signature(tool).parameters.values()
    except (TypeError, ValueError):
        return {"type": "object"}
    for parameter in parameters:
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        json_type = _JSON_TYPES.get(parameter.annotation)
        properties[parameter.name] = {"type": json_type} if json_type else {}
        if parameter.default is parameter.empty:
            required.append(parameter.name)
    schema: dict[str, JsonValue] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _describe(name: str, tool: Callable[..., JsonValue]) -> str:
    doc = inspect.getdoc(tool)
    return doc.splitlines()[0] if doc else name


class ToolSetServer:
    """Small synchronous server; the boundary guarantees serial tool calls."""

    def __init__(self, toolset: ToolSet, workdir: Path, allowed: set[str] | None) -> None:
        self._toolset = toolset
        self._workdir = workdir
        available = toolset.tools
        if allowed is not None:
            missing = sorted(allowed.difference(available))
            if missing:
                raise ValueError(f"unknown tools in --tools: {','.join(missing)}")
            self._tools: Mapping[str, Callable[..., JsonValue]] = {
                name: available[name] for name in available if name in allowed
            }
        else:
            self._tools = dict(available)
        self.save_snapshot()

    def save_snapshot(self) -> None:
        self._workdir.mkdir(parents=True, exist_ok=True)
        with redirect_stdout(sys.stderr):
            snapshot = self._toolset.snapshot()
        payload = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, allow_nan=False)
        (self._workdir / "state.json").write_text(payload, encoding="utf-8")

    def handle(self, message: dict[str, JsonValue]) -> dict[str, JsonValue] | None:
        if "id" not in message:
            return None
        request_id = message["id"]
        method = message.get("method")
        raw_params = message.get("params")
        params = raw_params if isinstance(raw_params, dict) else {}

        if method == "initialize":
            return _reply(
                request_id,
                result={
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "arci-toolset", "version": "0.2"},
                },
            )
        if method == "ping":
            return _reply(request_id, result={})
        if method == "tools/list":
            tools: list[JsonValue] = [
                {
                    "name": name,
                    "description": _describe(name, tool),
                    "inputSchema": _input_schema(tool),
                }
                for name, tool in self._tools.items()
            ]
            return _reply(request_id, result={"tools": tools})
        if method == "tools/call":
            return self._call(request_id, params)
        return _error(request_id, -32601, f"method not found: {method}")

    def _call(self, request_id: JsonValue, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        name = params.get("name")
        raw_arguments = params.get("arguments")
        arguments = raw_arguments if isinstance(raw_arguments, dict) else {}
        try:
            if not isinstance(name, str) or name not in self._tools:
                return _error(request_id, -32602, f"unknown tool {name}")
            try:
                with redirect_stdout(sys.stderr):
                    value = self._tools[name](**arguments)
                result = _result(value)
            except Exception as exc:
                result = _result(_one_line(exc), is_error=True)
            return _reply(request_id, result=result)
        finally:
            self.save_snapshot()


def snapshot(task: dict[str, JsonValue], workdir: str) -> dict[str, JsonValue]:
    """Read the bridge state for grading; a server that never started has no state."""
    del task
    path = Path(workdir) / "state.json"
    if not path.exists():
        return {}
    value: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise TypeError("state.json must contain a JSON object")
    return cast(dict[str, JsonValue], value)


def _write(message: dict[str, JsonValue]) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False, allow_nan=False) + "\n")
    sys.stdout.flush()


def _serve(server: ToolSetServer) -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            value: Any = json.loads(line)
            if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
                _write(_error(None, -32600, "invalid request"))
                continue
            message = cast(dict[str, JsonValue], value)
            response = server.handle(message)
        except (json.JSONDecodeError, UnicodeError, ValueError, TypeError) as exc:
            _write(_error(None, -32700, _one_line(exc)))
            continue
        if response is not None:
            _write(response)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--toolset", required=True)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--tools")
    parser.add_argument("--task-file")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    task_path = cast(str | None, args.task_file) or os.environ.get("ARCI_TASK_FILE")
    task = _load_task(task_path)
    factory = _resolve_factory(cast(str, args.toolset))
    with redirect_stdout(sys.stderr):
        toolset = factory(task, cast(int, args.seed))
    raw_tools = cast(str | None, args.tools)
    allowed = {name for name in raw_tools.split(",") if name} if raw_tools is not None else None
    server = ToolSetServer(toolset, Path(cast(str, args.workdir)), allowed)
    _serve(server)
    return 0


def _entrypoint() -> NoReturn:
    try:
        code = main()
    except BaseException as exc:
        print(_one_line(exc), file=sys.stderr)
        raise SystemExit(1) from None
    raise SystemExit(code)


if __name__ == "__main__":
    _entrypoint()
