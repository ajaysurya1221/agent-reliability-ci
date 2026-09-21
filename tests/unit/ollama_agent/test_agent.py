from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import JsonValue

import examples.ollama_mcp_agent.agent as agent_module
import examples.ollama_mcp_agent.experiment as experiment_module
from examples.ollama_mcp_agent.agent import JsonObject, run_agent, validate_ollama_url


class FakeSession:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.calls: list[tuple[str, JsonObject]] = []

    def list_tools(self) -> list[JsonObject]:
        return [
            {
                "name": "reserve",
                "description": "reserve",
                "inputSchema": {"type": "object"},
            },
            {
                "name": "confirm",
                "description": "confirm",
                "inputSchema": {"type": "object"},
            },
        ]

    def call_tool(self, name: str, arguments: JsonObject) -> tuple[str, bool]:
        self.calls.append((name, arguments))
        if self.failures:
            self.failures -= 1
            return "arci injected timeout", True
        return '{"ok": true}', False


def _tool_response(name: str, **arguments: JsonValue) -> JsonObject:
    return {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": name, "arguments": arguments}}],
        }
    }


def _final_response() -> JsonObject:
    return {"message": {"role": "assistant", "content": "done"}}


def test_tool_call_round_trip_returns_result_to_model() -> None:
    session = FakeSession()
    payloads: list[JsonObject] = []

    def chat(url: str, payload: JsonObject) -> JsonObject:
        del url
        payloads.append(json.loads(json.dumps(payload)))
        return (
            _tool_response("reserve", order_id="o-1") if len(payloads) == 1 else _final_response()
        )

    result = run_agent(
        {"order_id": "o-1"},
        session,
        prompt_variant="a",
        model="fake",
        max_steps=3,
        chat=chat,
        transcript=io.StringIO(),
    )

    assert result == "done"
    assert session.calls == [("reserve", {"order_id": "o-1"})]
    messages = payloads[1]["messages"]
    assert isinstance(messages, list)
    assert messages[-1] == {
        "role": "tool",
        "tool_name": "reserve",
        "content": '{"ok": true}',
    }


def _prompt_driven_chat() -> Callable[[str, JsonObject], JsonObject]:
    calls = 0

    def chat(url: str, payload: JsonObject) -> JsonObject:
        nonlocal calls
        del url
        calls += 1
        messages = payload["messages"]
        assert isinstance(messages, list)
        system = messages[0]
        assert isinstance(system, dict)
        content = system["content"]
        assert isinstance(content, str)
        retry = "Retry a failed tool call" in content
        if calls == 1:
            return _tool_response("reserve")
        last = messages[-1]
        assert isinstance(last, dict)
        if last.get("role") == "tool" and last.get("content") == "arci injected timeout":
            return _tool_response("reserve" if retry else "confirm")
        return _final_response()

    return chat


@pytest.mark.parametrize(
    ("variant", "expected"),
    (("a", ["reserve", "reserve"]), ("b", ["reserve", "confirm"])),
)
def test_prompt_variants_control_retry_behavior(variant: str, expected: list[str]) -> None:
    session = FakeSession(failures=1)
    run_agent(
        {},
        session,
        prompt_variant=variant,
        model="fake",
        max_steps=3,
        chat=_prompt_driven_chat(),
        transcript=io.StringIO(),
    )
    assert [name for name, _ in session.calls] == expected


def test_max_steps_stops_the_loop() -> None:
    session = FakeSession()
    chat_calls = 0

    def chat(url: str, payload: JsonObject) -> JsonObject:
        nonlocal chat_calls
        del url, payload
        chat_calls += 1
        return _tool_response("reserve")

    result = run_agent(
        {},
        session,
        prompt_variant="a",
        model="fake",
        max_steps=2,
        chat=chat,
        transcript=io.StringIO(),
    )
    assert result is None
    assert chat_calls == 2
    assert len(session.calls) == 2


@pytest.mark.parametrize(
    "url",
    (
        "http://localhost:11434/api/chat",
        "http://[::1]:11434/api/chat",
        "https://127.0.0.1:11434/api/chat",
        "http://127.0.0.1:11435/api/chat",
        "http://user@127.0.0.1:11434/api/chat",
    ),
)
def test_loopback_only_guard(url: str) -> None:
    with pytest.raises(ValueError, match=r"127\.0\.0\.1"):
        validate_ollama_url(url)


def test_literal_loopback_url_is_allowed() -> None:
    validate_ollama_url("http://127.0.0.1:11434/api/chat")


@pytest.mark.parametrize("module", [agent_module, experiment_module])
def test_ollama_openers_reject_redirects(module: object) -> None:
    handler_type = vars(module)["_RejectRedirects"]
    handler = handler_type()
    request = urllib.request.Request("http://127.0.0.1:11434/")
    with pytest.raises(urllib.error.HTTPError):
        handler.redirect_request(request, None, 302, "redirect", {}, "http://example.com/")


def test_main_returns_nonzero_when_the_step_limit_is_exhausted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_file = tmp_path / "task.json"
    task_file.write_text("{}", encoding="utf-8")

    class Session(FakeSession):
        def close(self) -> None:
            return None

    def make_session(_path: str | Path) -> Session:
        return Session()

    def exhaust_steps(
        task: JsonObject,
        session: object,
        *,
        prompt_variant: str,
        model: str,
        max_steps: int,
    ) -> None:
        del task, session, prompt_variant, model, max_steps

    monkeypatch.setattr(agent_module, "McpSession", make_session)
    monkeypatch.setattr(agent_module, "run_agent", exhaust_steps)

    code = agent_module.main(
        [
            "--mcp-config",
            "unused.json",
            "--task-file",
            str(task_file),
            "--prompt-variant",
            "a",
            "--max-steps",
            "1",
        ]
    )
    assert code == 1
