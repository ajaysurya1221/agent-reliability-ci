"""A scripted support agent that asks a System One endpoint, then acts over MCP. FROZEN.

    python decision_fixture_client.py --mcp-config FILE --task-file FILE --variant VARIANT

It finds the endpoint the way the official SDKs do: `TYPESAFE_BASE_URL` and `TYPESAFE_API_KEY`
from the environment, `POST {base}/v1/systemone` with a bearer token, up to three attempts on a
529 (the SDK's default of two retries), no sleeping. Standard library only. Exit 0 = claims success.

Variants
  gated       the confidence-gated agent from the docs pattern: acts above the thresholds,
              escalates below them or when the provider is unavailable
  abandon     the regression: returns without acting when confidence is low or the provider fails
  blind       acts on the winning option whatever the confidence; gives up on provider failure
  wrongkey    presents the wrong bearer; stores "unauthorized" after the 401
  concurrent  holds one request half-sent while completing another, then behaves like gated
  sdk         the gated agent written against the official `typesafe_sdk` (dev dependency)
  double      asks twice, then behaves like gated (budget probe)
  models      GET /v1/models first, then gated
  huge        pads the state past 300 KB; stores "too-large" after the 413
  badreq      sends an empty question map first (expects 422), then gated
  late        acts over MCP first, closes the MCP session, and only then asks a question
  leak        logs the endpoint and token it was given (for the key-isolation test), then gated
  weird       sends a question whose type is not a string (expects 422), then gated
  deep        sends a 5000-level nested state (expects 422), then gated
  sdkshapes   asks with the structured criteria shapes the official SDK may send, then gated
  pingrace    leaves an MCP ping in flight while asking (unsupported: a harness fault)
  pipeline    two requests on one connection; expects exactly one response, then gated
  expect      sends `Expect: 100-continue`; stores "expect-rejected" after the 417
  fireandforget  acts over MCP, then sends a request and exits without reading the answer
  keys        logs the sorted top-level keys of the response it received, then acts like gated
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_fixture_client import Session

QUESTIONS: dict[str, Any] = {
    "department": {
        "type": "choice",
        "instructions": "Which team should handle this ticket?",
        "criteria": {
            "billing": "Payments, invoicing, refunds",
            "technical": "Bugs, outages, integrations",
            "sales": "Pricing, plans, account questions",
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


class Endpoint:
    def __init__(self) -> None:
        self.base = os.environ["TYPESAFE_BASE_URL"].rstrip("/")
        self.key = os.environ["TYPESAFE_API_KEY"]

    def request(
        self,
        method: str,
        path: str,
        body: Any = None,
        key: str | None = None,
        raw: bytes | None = None,
    ) -> tuple[int, Any]:
        data = raw if raw is not None else None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.key if key is None else key}",
                "Content-Type": "application/json",
            },
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request, timeout=15) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            text = error.read().decode("utf-8", errors="replace")
            try:
                return error.code, json.loads(text)
            except ValueError:
                return error.code, text

    def ask(
        self, task: dict[str, Any], questions: dict[str, Any] | None = None, key: str | None = None
    ) -> tuple[int, Any]:
        body = {
            "state": {"ticket": task},
            "model": "jev-latest",
            "questions": QUESTIONS if questions is None else questions,
        }
        status, payload = 0, None
        for _ in range(3):
            status, payload = self.request("POST", "/v1/systemone", body, key=key)
            if status != 529:
                break
        return status, payload


def decide_action(answers: dict[str, Any]) -> str:
    department = answers["department"]
    if department["choice"] == "billing":
        refund = answers["refund_requested"]["noul"] > 0.5
        supported = answers["policy_supports"]["noul"] > 0.5
        return "refund" if refund and supported else "reply"
    if department["choice"] == "technical":
        return "technical"
    return "reply"


def gated_action(answers: dict[str, Any]) -> str | None:
    """The docs pattern: a floor for every action, a higher bar for the irreversible one."""
    department = answers["department"]
    if department["confidence"] < 0.6:
        return None
    action = decide_action(answers)
    if action == "refund" and (
        department["confidence"] < 0.85 or answers["policy_supports"]["noul"] < 0.85
    ):
        return None
    return action


# The shapes the official SDK is allowed to send: structured instructions, criteria whose values
# are objects, arrays or null, and partial noul criteria.
SDK_SHAPES: dict[str, Any] = {
    "department": {
        "type": "choice",
        "instructions": {"task": "route the ticket", "fields": ["ticket"]},
        "criteria": {
            "billing": None,
            "technical": ["bugs", "outages", "integrations"],
            "sales": {"about": "pricing, plans, account questions"},
        },
    },
    "refund_requested": {
        "type": "noul",
        "instructions": "The customer explicitly asks for a refund",
        "criteria": {"true": "asks for money back"},
    },
    "policy_supports": {"type": "noul", "instructions": ["policy", "covers this situation"]},
    "frustration": {
        "type": "score",
        "criteria": ["Calm", {"level": "Frustrated but civil"}, ["Very", "angry"]],
    },
}


def _raw(endpoint: Endpoint) -> tuple[socket.socket, str]:
    parsed = urllib.parse.urlsplit(endpoint.base)
    assert parsed.hostname is not None and parsed.port is not None
    return socket.create_connection((parsed.hostname, parsed.port), timeout=15), parsed.netloc


def _post_bytes(
    endpoint: Endpoint, netloc: str, task: dict[str, Any], expect: bool = False
) -> tuple[bytes, bytes]:
    body = json.dumps(
        {"state": {"ticket": task}, "model": "jev-latest", "questions": QUESTIONS}
    ).encode("utf-8")
    head = (
        f"POST /v1/systemone HTTP/1.1\r\nHost: {netloc}\r\n"
        f"Authorization: Bearer {endpoint.key}\r\nContent-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n" + ("Expect: 100-continue\r\n" if expect else "") + "\r\n"
    ).encode("ascii")
    return head, body


def _read_all(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    with contextlib.suppress(OSError):
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks)


def _pipelined(endpoint: Endpoint, task: dict[str, Any]) -> int:
    """Two complete requests on one connection; return how many responses came back."""
    sock, netloc = _raw(endpoint)
    head, body = _post_bytes(endpoint, netloc, task)
    sock.sendall(head + body + head + body)
    raw = _read_all(sock)
    sock.close()
    return raw.count(b"HTTP/1.1 ")


def _expect_continue(endpoint: Endpoint, task: dict[str, Any]) -> int:
    """Send only the head with Expect: 100-continue and wait for the boundary's answer."""
    sock, netloc = _raw(endpoint)
    head, _ = _post_bytes(endpoint, netloc, task, expect=True)
    sock.sendall(head)
    sock.settimeout(5)
    raw = b""
    with contextlib.suppress(OSError):
        raw = sock.recv(65536)
    sock.close()
    if not raw.startswith(b"HTTP/1.1 "):
        return 0
    return int(raw.split(b" ", 2)[1])


def _fire_and_forget(endpoint: Endpoint, task: dict[str, Any]) -> None:
    """Send a complete request and exit without reading the answer."""
    sock, netloc = _raw(endpoint)
    head, body = _post_bytes(endpoint, netloc, task)
    sock.sendall(head + body)
    sock.close()


def sdk_agent(session: Session, task: dict[str, Any]) -> int:
    """The gated agent written against the official SDK, configured only by the environment."""
    from typesafe_sdk import (
        Choice,
        Noul,
        NoulCriteria,
        Score,
        TypeSafeAPIConnectionError,
        TypeSafeAPIError,
        TypeSafeClient,
    )

    client = TypeSafeClient()
    try:
        response = client.system_one(
            state={"ticket": task},
            questions={
                "department": Choice(
                    instructions=QUESTIONS["department"]["instructions"],
                    criteria=QUESTIONS["department"]["criteria"],
                ),
                "refund_requested": Noul(
                    instructions=QUESTIONS["refund_requested"]["instructions"]
                ),
                "policy_supports": Noul(
                    instructions=QUESTIONS["policy_supports"]["instructions"],
                    criteria=NoulCriteria(
                        true="Duplicate charges are refundable", false="Not covered"
                    ),
                ),
                "frustration": Score(
                    instructions=QUESTIONS["frustration"]["instructions"],
                    criteria=QUESTIONS["frustration"]["criteria"],
                ),
            },
            model="jev-latest",
        )
    except (TypeSafeAPIError, TypeSafeAPIConnectionError):
        session.call("store", value="escalate")
        session.close()
        return 0
    answers = {name: answer.model_dump() for name, answer in response.answers.items()}
    session.call("store", value=gated_action(answers) or "escalate")
    session.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcp-config", required=True)
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--variant", required=True)
    args = parser.parse_args()
    task = json.loads(Path(args.task_file).read_text())
    variant = args.variant
    endpoint = Endpoint()

    if variant == "late":
        session = Session(args.mcp_config)
        session.rpc("tools/list")
        session.call("log", msg="start")
        session.call("store", value="escalate")
        session.close()
        status, _ = endpoint.ask(task)
        return 0 if status == 200 else 9

    session = Session(args.mcp_config)
    session.rpc("tools/list")  # what a real MCP client does first; the boundary checks the names
    session.call("log", msg="start")
    if variant == "leak":
        session.call("log", msg=f"base={endpoint.base} key={endpoint.key}")
    if variant == "models":
        status, payload = endpoint.request("GET", "/v1/models")
        if status != 200 or not payload.get("models"):
            session.call("store", value="no-models")
            session.close()
            return 0
    if variant == "wrongkey":
        status, _ = endpoint.ask(task, key="not-the-token")
        session.call("store", value="unauthorized" if status == 401 else f"status-{status}")
        session.close()
        return 0
    if variant == "huge":
        padded = {**task, "pad": "x" * 300_000}
        status, _ = endpoint.ask(padded)
        session.call("store", value="too-large" if status == 413 else f"status-{status}")
        session.close()
        return 0
    if variant == "badreq":
        status, _ = endpoint.ask(task, questions={})
        if status != 422:
            session.call("store", value=f"status-{status}")
            session.close()
            return 0
    if variant == "concurrent":
        # Deterministic overlap: send only the head of one request, complete a second request on
        # another connection while the first is still open, then finish the first.
        parsed = urllib.parse.urlsplit(endpoint.base)
        assert parsed.hostname is not None and parsed.port is not None
        first = socket.create_connection((parsed.hostname, parsed.port), timeout=15)
        body = json.dumps(
            {"state": {"ticket": task}, "model": "jev-latest", "questions": QUESTIONS}
        ).encode("utf-8")
        head = (
            f"POST /v1/systemone HTTP/1.1\r\nHost: {parsed.netloc}\r\n"
            f"Authorization: Bearer {endpoint.key}\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
        ).encode("ascii")
        first.sendall(head)
        endpoint.ask(task)
        with contextlib.suppress(OSError):
            first.sendall(body)
            first.settimeout(5)
            first.recv(65536)
        first.close()
    if variant == "double":
        endpoint.ask(task)
    if variant == "sdk":
        return sdk_agent(session, task)
    if variant == "weird":
        # A question whose `type` is not a string. The boundary must answer 422, not fall over.
        status, _ = endpoint.request(
            "POST",
            "/v1/systemone",
            {"state": {"ticket": task}, "model": "jev-latest", "questions": {"q": {"type": []}}},
        )
        if status != 422:
            session.call("store", value=f"status-{status}")
            session.close()
            return 0
    if variant == "deep":
        # Built as text: json.dumps cannot encode 5000 levels on every Python version, and the
        # point is what the boundary does with such a body, not what the client can build.
        nested = "[" * 5000 + '"x"' + "]" * 5000
        raw = (
            '{"state": '
            + nested
            + ', "model": "jev-latest", "questions": '
            + json.dumps(QUESTIONS)
            + "}"
        ).encode("utf-8")
        status, _ = endpoint.request("POST", "/v1/systemone", raw=raw)
        if status != 422:
            session.call("store", value=f"status-{status}")
            session.close()
            return 0
    if variant == "pingrace":
        # An MCP exchange left in flight while a decision is made: unsupported, so the trial
        # must end as a harness fault whatever the server answers later.
        session.send({"jsonrpc": "2.0", "id": "race", "method": "ping", "params": {}})
        endpoint.ask(task)
        assert session.proc.stdout is not None
        while True:
            line = session.proc.stdout.readline()
            if not line or json.loads(line).get("id") == "race":
                break
    if variant == "pipeline":
        responses = _pipelined(endpoint, task)
        if responses != 1:
            session.call("store", value=f"pipelined-{responses}")
            session.close()
            return 0
    if variant == "expect":
        status = _expect_continue(endpoint, task)
        session.call("store", value="expect-rejected" if status == 417 else f"status-{status}")
        session.close()
        return 0
    if variant == "fireandforget":
        session.call("store", value="escalate")
        session.close()
        _fire_and_forget(endpoint, task)
        return 0

    questions = SDK_SHAPES if variant == "sdkshapes" else None
    if variant == "keys":
        status, payload = endpoint.ask(task)
        if status == 200 and isinstance(payload, dict):
            session.call("log", msg="keys=" + ",".join(sorted(payload)))
            action = gated_action(payload["answers"]) or "escalate"
            session.call("store", value=action)
        else:
            session.call("store", value="escalate")
        session.close()
        return 0

    status, payload = endpoint.ask(task, questions=questions)
    if status != 200:
        if variant == "gated":
            session.call("store", value="escalate")
        session.close()
        return 0
    answers = payload["answers"]
    if variant == "blind":
        action: str | None = decide_action(answers)
    else:
        action = gated_action(answers)
    if action is None:
        if variant == "abandon":
            session.close()
            return 0
        action = "escalate"
    session.call("store", value=action)
    session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
