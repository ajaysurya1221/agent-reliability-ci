"""Exercise the native fixture at its HTTP dispatch boundary without opening a socket."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pin
from common import ROOT, Row, assistant, models, read
from fake_ollama import FakeOllama
from worlds import rows, world


def test_metadata_and_native_pins() -> None:
    server = FakeOllama()
    slots = models(ROOT / "models.json")

    all_models = slots + read(ROOT / "models.json")["spares"]

    def request(method: str, path: str, body: Row | None = None) -> Row:
        status, raw = server.handle(
            method, "/api/" + path, json.dumps(body).encode() if body else b""
        )
        assert status == 200
        return json.loads(raw)

    assert request("GET", "version") == {"version": read(ROOT / "models.json")["ollama"]}
    assert request("GET", "tags") == {
        "models": [{"name": m["tag"], "digest": m["digest"]} for m in all_models]
    }
    assert request("GET", "ps") == {"models": []}
    for slot in all_models:
        tag = slot["tag"]
        assert request("POST", "show", {"model": tag}) == {"parameters": "num_ctx 32768"}
        history = pin.question(3)
        payload = {
            "model": tag,
            "tools": pin.TOY_TOOLS,
            "messages": history,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.7},
        }
        result = request("POST", "chat", payload)
        assert result["done_reason"] == "stop"
        msg = assistant(json.dumps(result).encode(), tag)
        if slot == slots[-1]:
            assert msg == {"role": "assistant", "content": history[1]["content"]}
        else:
            assert pin.called(msg, 3)
            history.extend(
                [
                    msg,
                    {
                        "role": "tool",
                        "tool_name": "read_pebble",
                        "content": "1234567890abcdef12345678",
                    },
                ]
            )
            assert request("POST", "chat", payload)["message"] == {
                "role": "assistant",
                "content": "1234567890abcdef12345678",
            }
        assert request("GET", "ps") == {
            "models": [{"name": tag, "digest": slot["digest"], "context_length": 32768}]
        }
    assert server.handle("GET", "/api/chat")[0] == 404
    assert server.handle("POST", "/api/show", b'{"model":"missing"}')[0] == 404


@pytest.mark.parametrize("tid", ["O-o2", "O-o6"])
def test_board_chat(tid: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARCI_SEED", "0")
    monkeypatch.delenv("BOARD0_REHEARSAL_FAULTS", raising=False)
    server = FakeOllama()
    row = rows()[tid]
    doc = read(ROOT / "tasks/tasks.json")
    tag = models(ROOT / "models.json")[0]["tag"]
    opening = {"role": "assistant", "content": "", "tool_calls": [{"function": row["opening"]}]}
    tool = {"role": "tool", "tool_name": row["opening"]["name"], "content": ""}
    messages = [
        {"role": "system", "content": doc["system_prompt"]},
        {"role": "user", "content": row["ask"]},
        opening,
        tool,
    ]
    payload = {
        "model": tag,
        "tools": [{"type": "function", "function": {"name": "lookup_order"}}],
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.7},
    }

    def chat() -> Row:
        status, raw = server.handle("POST", "/api/chat", json.dumps(payload).encode())
        assert status == 200 and json.loads(raw)["done_reason"] == "stop"
        return assistant(raw, tag)

    assert chat() == {"role": "assistant", "content": ""}
    tool["content"] = doc["stock_sentence"]
    retry = chat()
    assert retry == opening
    record = world(row, 19).snapshot()["order"]
    result = json.dumps(record)
    messages.extend([retry, tool | {"content": result}])
    expected = f"The answer is {record['total_cents']}." if tid == "O-o2" else result
    assert chat() == chat() == {"role": "assistant", "content": expected}
