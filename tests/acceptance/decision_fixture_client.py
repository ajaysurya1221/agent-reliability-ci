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
        self, method: str, path: str, body: Any = None, key: str | None = None
    ) -> tuple[int, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
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
            raw = error.read().decode("utf-8", errors="replace")
            try:
                return error.code, json.loads(raw)
            except ValueError:
                return error.code, raw

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
        session.call("log", msg="start")
        session.call("store", value="escalate")
        session.close()
        status, _ = endpoint.ask(task)
        return 0 if status == 200 else 9

    session = Session(args.mcp_config)
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

    status, payload = endpoint.ask(task)
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
