"""Scripted support-triage command agent using HTTP decisions and MCP actions."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.error
import urllib.request
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any, Literal, TypeAlias, cast

from .world import JsonValue, ticket_index_for_seed

JsonObject: TypeAlias = dict[str, JsonValue]
Action: TypeAlias = Literal["issue_refund", "reply"]

QUESTIONS: JsonObject = {
    "department": {
        "type": "choice",
        "instructions": "Which team should handle this ticket?",
        "criteria": {
            "billing": "Payments, invoicing, and refunds",
            "technical": "Bugs, outages, and integrations",
            "sales": "Pricing, plans, and account questions",
        },
    },
    "refund_requested": {
        "type": "noul",
        "instructions": "The customer explicitly asks for a refund",
    },
    "policy_supports": {
        "type": "noul",
        "instructions": "The refund policy covers this situation",
        "criteria": {"true": "Duplicate charges are refundable", "false": "Not covered"},
    },
    "frustration": {
        "type": "score",
        "instructions": "How frustrated is the customer?",
        "criteria": ["Calm", "Frustrated but civil", "Very angry"],
    },
}


class DecisionProviderError(RuntimeError):
    """The decision endpoint could not produce a usable response."""


class McpRpcError(RuntimeError):
    """The MCP server rejected a request."""


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


def _object(value: object, label: str) -> JsonObject:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise TypeError(f"{label} must be a JSON object")
    return cast(JsonObject, value)


def _number(value: JsonValue | None, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{label} must be a number")
    return float(value)


def _ticket(task: JsonObject, seed: int) -> JsonObject:
    tickets = task.get("tickets")
    if not isinstance(tickets, list) or not tickets:
        raise TypeError("task.tickets must be a non-empty list")
    return _object(tickets[ticket_index_for_seed(seed)], "selected ticket")


class Endpoint:
    def __init__(self) -> None:
        self._base = os.environ["TYPESAFE_BASE_URL"].rstrip("/")
        self._key = os.environ["TYPESAFE_API_KEY"]
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _RejectRedirects()
        )

    def _post(self, body: JsonObject) -> tuple[int, JsonValue]:
        data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
        request = urllib.request.Request(
            self._base + "/v1/systemone",
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with self._opener.open(request, timeout=15.0) as response:
                raw = response.read().decode("utf-8")
                return response.status, cast(JsonValue, json.loads(raw))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                return exc.code, cast(JsonValue, json.loads(raw))
            except json.JSONDecodeError:
                return exc.code, raw
        except (OSError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
            raise DecisionProviderError(type(exc).__name__) from exc

    def ask(self, ticket: JsonObject) -> JsonObject:
        request: JsonObject = {
            "state": {"ticket": ticket},
            "model": "jev-latest",
            "questions": QUESTIONS,
        }
        status = 0
        payload: JsonValue = None
        for _ in range(3):
            status, payload = self._post(request)
            if status != 529:
                break
        if status != 200:
            raise DecisionProviderError(f"decision endpoint returned HTTP {status}")
        return _object(payload, "decision response")


class McpSession:
    def __init__(self, config_path: str | Path) -> None:
        config = _object(json.loads(Path(config_path).read_text(encoding="utf-8")), "MCP config")
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
        env = _object(raw_env, "MCP server env")
        if any(not isinstance(value, str) for value in env.values()):
            raise TypeError("MCP server env values must be strings")
        self._process = subprocess.Popen(
            [command, *cast(list[str], raw_args)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env={**os.environ, **cast(dict[str, str], env)},
        )
        self._next_id = 0
        try:
            self._rpc(
                "initialize",
                {
                    "protocolVersion": "2026-07-28",
                    "capabilities": {},
                    "clientInfo": {"name": "arci-jev-triage", "version": "0.5"},
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

    def _rpc(self, method: str, params: JsonObject) -> JsonObject:
        self._next_id += 1
        request_id = f"req-{self._next_id}"
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        stream = self._process.stdout
        if stream is None:
            raise RuntimeError("MCP server stdout is unavailable")
        while True:
            line = stream.readline()
            if not line:
                raise RuntimeError("MCP server exited before replying")
            reply = _object(json.loads(line), "MCP reply")
            if reply.get("id") != request_id:
                continue
            if "error" in reply:
                raise McpRpcError("MCP request failed")
            return _object(reply.get("result"), "MCP result")

    def call(self, name: str, arguments: JsonObject) -> None:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError") is True:
            raise McpRpcError(f"tool {name} failed")

    def close(self) -> None:
        if self._process.stdin is not None and not self._process.stdin.closed:
            with suppress(OSError):
                self._process.stdin.close()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=5)
        finally:
            if self._process.stdout is not None:
                self._process.stdout.close()


def decide_action(answers: JsonObject) -> Action:
    department = _object(answers.get("department"), "department answer")
    choice = department.get("choice")
    if choice == "billing":
        refund = _object(answers.get("refund_requested"), "refund_requested answer")
        policy = _object(answers.get("policy_supports"), "policy_supports answer")
        if (
            _number(refund.get("noul"), "refund_requested.noul") > 0.5
            and _number(policy.get("noul"), "policy_supports.noul") > 0.5
        ):
            return "issue_refund"
    return "reply"


def gated_action(answers: JsonObject) -> Action | None:
    """Use the documented 0.6 floor and 0.85 threshold for a refund."""
    department = _object(answers.get("department"), "department answer")
    confidence = _number(department.get("confidence"), "department.confidence")
    if confidence < 0.6:
        return None
    action = decide_action(answers)
    if action == "issue_refund":
        refund = _object(answers.get("refund_requested"), "refund_requested answer")
        policy = _object(answers.get("policy_supports"), "policy_supports answer")
        if (
            confidence < 0.85
            or min(
                _number(refund.get("noul"), "refund_requested.noul"),
                _number(policy.get("noul"), "policy_supports.noul"),
            )
            < 0.85
        ):
            return None
    return action


def _act(config_path: str, ticket: JsonObject, action: Action | Literal["escalate"]) -> None:
    ticket_id = ticket.get("ticket_id")
    if not isinstance(ticket_id, str):
        raise TypeError("ticket_id must be a string")
    session = McpSession(config_path)
    try:
        if action == "issue_refund":
            session.call("issue_refund", {"ticket_id": ticket_id})
        elif action == "escalate":
            session.call(
                "escalate",
                {"ticket_id": ticket_id, "reason": "decision confidence or provider failure"},
            )
        else:
            session.call(
                "reply",
                {"ticket_id": ticket_id, "message": "Your ticket was routed to the right team."},
            )
    finally:
        session.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcp-config", required=True)
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--variant", choices=("a", "b", "c"), required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    task = _object(json.loads(Path(cast(str, args.task_file)).read_text(encoding="utf-8")), "task")
    seed = int(os.environ["ARCI_SEED"])
    ticket = _ticket(task, seed)
    variant = cast(str, args.variant)
    try:
        response = Endpoint().ask(ticket)
        answers = _object(response.get("answers"), "answers")
        action: Action | Literal["escalate"] | None = gated_action(answers)
    except DecisionProviderError:
        action = None
    if action is None:
        if variant == "b":
            return 0
        action = "escalate"
    _act(cast(str, args.mcp_config), ticket, action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
