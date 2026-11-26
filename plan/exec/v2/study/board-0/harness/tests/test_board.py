"""Planted faults and Board-0 invariants."""

from __future__ import annotations

import base64
import json
import sys
from datetime import date
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tasks"))
from admission import order_guard
from agent import Receipt, run_agent
from check_evidence import answer_key, receipt_answer
from common import ROOT, Row, models, read, schedule, write
from privacy import safe_bytes
from publication import rating
from worlds import expected, rows

sys.dont_write_bytecode = True
tasks_module = import_module("make_tasks")
PROMPT, STOCK = tasks_module.PROMPT, tasks_module.STOCK
build, orders = tasks_module.build, tasks_module.orders


def test_keys_agree() -> None:
    for seed in (0, 1234, 2**53 - 1):
        for row in rows().values():
            assert expected(row, seed) == answer_key(row, seed)


def test_task_builder(tmp_path: Path) -> None:
    family = [r | {"family": "calendar", "id": "cal" + str(i)} for i, r in enumerate(orders())]
    write(tmp_path / "calendardesk/tasks.json", family)
    assert build(tmp_path) == {
        "tasks": orders() + family,
        "system_prompt": PROMPT,
        "stock_sentence": STOCK,
    }
    assert PROMPT == (
        "You answer questions by using the tools you are given. Call a tool when you need "
        "information. Never invent a tool result. When you know the answer, reply with the answer."
    )
    assert build(ROOT) == read(ROOT / "tasks/tasks.json")


def example() -> list[Row]:
    return models(ROOT / "models.example.json", offline=True)


def test_models(tmp_path: Path) -> None:
    path = tmp_path / "models.json"
    with pytest.raises(ValueError, match="5 model slots"):
        models(ROOT / "models.example.json")
    for changes in [
        {"slot": "M3"},
        {"digest": "BAD"},
        {"tag": ""},
        {"family": 3},
        {"size": ""},
        {"tag": example()[0]["tag"]},
        {"extra": True},
    ]:
        model = example()
        model[1].update(changes)
        path.write_text(json.dumps({"ollama": "0.32.14", "slots": model}))
        with pytest.raises(ValueError):
            models(path, offline=True)


def test_rated() -> None:
    index = rows()
    trials = [
        {"task_id": id, "outcome": "PASS"}
        for fam in ("orders", "calendar")
        for id in [r["id"] for r in index.values() if r["family"] == fam][:6]
    ]
    assert rating(trials * 2, index)["rated"]
    assert not rating(trials[:-1] * 2, index)["rated"]


def test_date_and_order(tmp_path: Path) -> None:
    slots = example()
    order = schedule(slots)
    for run in order[:6]:
        write(tmp_path / run / "claim.json", {"date": "2002-01-01"})
        write(tmp_path / run / "finished.json", {"ok": True})
    with pytest.raises(ValueError, match="later local date"):
        order_guard("board0-d2-M2-clean", slots, tmp_path, date(2002, 1, 1))
    with pytest.raises(ValueError, match="predecessor"):
        order_guard("board0-d2-M1-clean", slots, tmp_path, date(2002, 1, 2))
    order_guard("board0-d2-M2-clean", slots, tmp_path, date(2002, 1, 2))


class Session:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def list_tools(self) -> Any:
        return [{"name": "lookup_order", "description": "Read", "inputSchema": {}}]

    def call_tool(self, name: str, arguments: Any) -> tuple[str, bool]:
        self.calls.append(name)
        return "", False


@pytest.mark.parametrize("mode", ["text", "wrong-model", "unfinished"])
def test_actual_transport(mode: str, tmp_path: Path) -> None:
    task = orders()[0]
    session = Session()
    receipt = Receipt(tmp_path, "r", "c", 1, "baseline", "stock-sentence", "fault")

    def send(step: int, body: bytes, capture: Any) -> tuple[int, bytes]:
        capture(body)
        assert json.loads(body)["messages"][-1]["content"] == STOCK
        msg: Row = {"role": "assistant", "content": "42"}
        assert [t["function"]["name"] for t in json.loads(body)["tools"]] == ["lookup_order"]
        return 200, json.dumps(
            {
                "model": "wrong" if mode == "wrong-model" else "m",
                "done": mode != "unfinished",
                "message": msg,
            }
        ).encode()

    def run() -> Any:
        return run_agent(
            task,
            session,
            receipt,
            prompt=PROMPT,
            model="m",
            opening="fault",
            empty_text=STOCK,
            transport=send,
        )

    if mode in ("wrong-model", "unfinished"):
        with pytest.raises(ConnectionError):
            run()
    else:
        result = run()
        receipt.finish(tmp_path, result)
        assert result == "42"
        assert (
            receipt_answer(receipt.state, "m", {"termination": "completed"}, {"lookup_order"})
            == result
        )
        assert session.calls == ["lookup_order"]
        receipt.exchanges[0]["sha256"] = "0" * 64
        with pytest.raises(ValueError, match="bytes"):
            receipt_answer(receipt.state, "m", {"termination": "completed"}, {"lookup_order"})


def test_privacy() -> None:
    safe_bytes(b'{"status":200}', {"private-id"})
    for raw in (
        json.dumps({"blob": chr(33)}).encode(),
        json.dumps({"stdout": base64.b64encode(b"private-id").decode()}).encode(),
        json.dumps({"nested": {"blob": base64.b64encode("x".encode("utf-16")).decode()}}).encode(),
    ):
        with pytest.raises(ValueError):
            safe_bytes(raw, {"private-id"})


def test_planted_records_and_frozen_seeds(tmp_path: Path) -> None:
    import os
    import shutil
    import subprocess

    for folder in ("tasks", "harness", "orderdesk", "calendardesk"):
        shutil.copytree(
            ROOT / folder, tmp_path / folder, ignore=shutil.ignore_patterns("__pycache__")
        )
    shutil.copyfile(ROOT / "models.example.json", tmp_path / "models.example.json")
    (tmp_path / "tmp").mkdir()
    envdir = Path(os.environ.get("BOARD0_ENV", "/Users/Shared/arci-reply0/env"))
    site = (
        envdir
        / "py/lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    env = os.environ | {
        "TMPDIR": str(tmp_path / "tmp"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "BOARD0_NO_SANDBOX": "1",
        "PYTHONPATH": os.pathsep.join((str(site), str(tmp_path / "harness"))),
        "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
    }
    proc = subprocess.run(
        [sys.executable, "-PB", str(tmp_path / "harness/tests/planted.py"), str(tmp_path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_live_admission_before_connection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import admission
    import agent
    from common import sha

    run = "board0-d1-M1-E"
    directory = tmp_path / run
    directory.mkdir()
    receipt = Receipt(directory / "receipts", run, "O-o1", 1, "baseline", "stock-sentence", "fault")
    monkeypatch.setattr(admission, "CLAIMS", tmp_path)
    monkeypatch.setenv("BOARD0_TOKEN", "token")
    monkeypatch.setenv("BOARD0_RECEIPTS", str(directory / "receipts"))

    def premature(*args: object, **kwargs: object) -> None:
        pytest.fail("connection before admission")

    monkeypatch.setattr(
        agent.http.client,
        "HTTPConnection",
        premature,
    )

    def attempt() -> None:
        agent.ollama_chat(b"{}", lambda _: None, receipt, orders()[0], "tag", PROMPT)

    with pytest.raises(agent.BackendError):
        attempt()
    import os

    write(tmp_path / "active-suite.json", {"claim": run, "launcher": os.getpid(), "groups": []})
    write(directory / "claim.json", {"token_sha256": sha(b"token"), "run": run})
    with pytest.raises(agent.BackendError):
        attempt()


def test_claim_lock_and_surviving_group(tmp_path: Path) -> None:
    import os

    from suite_process import clear, locked_file

    lock = tmp_path / "lock"
    with locked_file(lock, 0), pytest.raises(TimeoutError), locked_file(lock, 0):
        pytest.fail("two suite owners")
    write(
        tmp_path / "active-suite.json",
        {"claim": "earlier", "launcher": os.getpid(), "groups": [os.getpgrp()]},
    )
    with pytest.raises(ValueError, match="still active"):
        clear(tmp_path, finishing=tmp_path / "earlier")


@pytest.mark.parametrize(
    ("requests", "lookups", "expected_text"), [(2, 11, "99"), (2, 12, None), (8, 0, None)]
)
def test_final_text_at_budget(
    tmp_path: Path, requests: int, lookups: int, expected_text: str | None
) -> None:
    receipt = Receipt(tmp_path, "run", "O-o1", 1, "baseline", "stock-sentence", "fault")
    session = Session()
    fn = orders()[0]["opening"]

    def send(step: int, body: bytes, capture: Any) -> tuple[int, bytes]:
        capture(body)
        calls = [
            {"function": {"name": "unknown", "arguments": {}}},
            *([{"function": fn}] * lookups),
        ]
        msg: Row = {"role": "assistant", "content": "99"}
        if step == 0 or requests == 8:
            msg["tool_calls"] = calls
        return 200, json.dumps({"done": True, "model": "tag", "message": msg}).encode()

    value = run_agent(
        orders()[0],
        session,
        receipt,
        prompt=PROMPT,
        model="tag",
        opening="fault",
        empty_text=STOCK,
        transport=send,
    )
    receipt.finish(tmp_path, value)
    assert value == expected_text
    assert session.calls.count("lookup_order") == 1 + min(lookups, 11)
    assert len(receipt.exchanges) == (1 if lookups == 12 else requests)
    assert (
        receipt_answer(receipt.state, "tag", {"termination": "completed"}, {"lookup_order"})
        == expected_text
    )


def test_order_questions() -> None:
    assert [r["id"] for r in orders()] == [f"O-o{i}" for i in range(1, 9)]
    assert all(r["ask"].endswith("?") for r in orders())


def test_round_cap() -> None:
    from common import RULE

    assert RULE["max_rounds"] * 16 == 416


def test_registered_assets() -> None:
    from inputs import inventory, sources

    required = {
        "scenario-collisions.json",
        *(
            "projections/" + n
            for n in (
                "project.py",
                "board0_plan_stub.py",
                "plan-16x20.yaml",
                "plan-16x26.yaml",
                "registered-rows.json",
            )
        ),
    }
    assert required <= set(sources()) <= set(inventory(example()))


def test_partial_clean_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import publication

    monkeypatch.setattr(publication, "ROOT", tmp_path)
    write(
        tmp_path / "clean/board0-d1-M1-clean.json",
        {"families": {"orders": 5, "calendar": 8}, "rated": False},
    )
    section = publication.report(example()).split("## M1 · day 2")[0]
    assert "orders 5/8" in section and "calendar 8/8" in section and "not rated" in section
    assert "measured" in section.lower() and "incomplete" in section.lower()


def test_registered_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import pin

    assert (
        read(ROOT / "models.example.json")["ollama"]
        == read(ROOT / "models.json")["ollama"]
        == "0.32.14"
    )
    assert len(models(ROOT / "models.json")) == 5

    def response(run: str, model: Row, endpoint: str, body: object) -> Any:
        assert endpoint == "version"
        return 200, b'{"version":"0.33.0"}'

    monkeypatch.setattr(pin, "request", response)
    with pytest.raises(ValueError, match="version"):
        pin.metadata("board0-pin-M1", example()[0])


def test_pushed_blobs(monkeypatch: pytest.MonkeyPatch) -> None:
    import admission
    from common import sha

    def blob(*args: str) -> bytes:
        assert args == ("cat-file", "blob", "revision:./tasks/tasks.json")
        return b"wrong"

    monkeypatch.setattr(admission, "git", blob)
    with pytest.raises(ValueError, match=r"tasks/tasks\.json"):
        admission.verify_blobs("revision", sha(b"registered") + "  tasks/tasks.json")

    def missing(*args: str) -> bytes:
        from subprocess import CalledProcessError

        raise CalledProcessError(128, list(args))

    monkeypatch.setattr(admission, "git", missing)
    with pytest.raises(ValueError, match=r"tasks/tasks\.json"):
        admission.verify_blobs("revision", sha(b"registered") + "  tasks/tasks.json")


def test_collision_scan() -> None:
    import worlds

    row = rows()["K-k5"]
    found = worlds.collisions(row, 4706095787801906)
    assert any(c["value"] == 89 and c["path"].endswith(".duration_minutes") for c in found)


def test_pin_user_echo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import pin

    def echo(body: bytes) -> tuple[int, bytes]:
        req = json.loads(body)
        return 200, json.dumps(
            {
                "model": req["model"],
                "done": True,
                "message": {"role": "assistant", "content": req["messages"][1]["content"]},
            }
        ).encode()

    monkeypatch.setattr(pin, "toy_chat", echo)
    path = tmp_path / "pin.json"
    with pytest.raises(ValueError, match="threshold"):
        pin.execute("board0-pin-M1", example()[0], path, offline=True)
    assert read(path)["passed"] == 0


@pytest.mark.parametrize(("bad", "qualifies"), [(4, True), (5, False)])
def test_pin_threshold_and_delivery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: int, qualifies: bool
) -> None:
    import check_evidence
    import pin

    chat = pin.toy_chat

    def backend(body: bytes) -> tuple[int, bytes]:
        req = json.loads(body)
        messages = req["messages"]
        if len(messages) == 2 and messages[1]["content"] in [
            pin.question(i)[1]["content"] for i in range(1, bad + 1)
        ]:
            msg = {"role": "assistant", "tool_calls": [{"function": pin.reader(99)}]}
            return 200, json.dumps({"model": req["model"], "done": True, "message": msg}).encode()
        return chat(body)

    monkeypatch.setattr(pin, "toy_chat", backend)
    path = tmp_path / "pin.json"
    if qualifies:
        pin.execute("board0-pin-M1", example()[0], path, offline=True)
    else:
        with pytest.raises(ValueError, match="threshold"):
            pin.execute("board0-pin-M1", example()[0], path, offline=True)
    result = read(path)
    assert result["ok"] is qualifies and result["passed"] == 20 - bad
    tag = example()[0]["tag"]
    assert (
        sum(check_evidence.verify_probe(p, tag, i) for i, p in enumerate(result["trials"], 1))
        == 20 - bad
    )
    assert len(result["delivery"]) == 2
    for i, p in enumerate(result["delivery"], 21):
        assert check_evidence.verify_probe(p, tag, i)
        (exchange,) = p["exchanges"]
        assert (
            json.loads(base64.b64decode(exchange["request_b64"]))["messages"][-1]["content"] == ""
        )


@pytest.mark.parametrize(
    "fault",
    [
        "user_echo_after_call",
        "wrong_case",
        "scripted_initial",
        "nonempty_delivery",
        "incomplete_delivery",
    ],
)
def test_pin_receipt_faults(tmp_path: Path, fault: str) -> None:
    import check_evidence
    import pin
    from common import sha

    model = example()[0]
    delivery = fault.endswith("delivery")
    number = 21 if delivery else 1
    probe = pin.run_probe("pin", model, tmp_path, number, True)
    assert check_evidence.verify_probe(probe, model["tag"], number)
    x = probe["exchanges"][-1]
    req = json.loads(base64.b64decode(x["request_b64"]))
    if fault in ("nonempty_delivery", "scripted_initial"):
        if delivery:
            req["messages"][-1]["content"] = " "
        else:
            probe["exchanges"] = [x]
        raw = json.dumps(req).encode()
        x.update(request_b64=base64.b64encode(raw).decode(), sha256=sha(raw))
    else:
        resp = json.loads(base64.b64decode(x["response_b64"]))
        if delivery:
            resp["done"] = False
        else:
            resp["message"]["content"] = (
                req["messages"][1]["content"]
                if fault == "user_echo_after_call"
                else req["messages"][-1]["content"].upper()
            )
        x["response_b64"] = base64.b64encode(json.dumps(resp).encode()).decode()
    with pytest.raises(ValueError, match="pin"):
        check_evidence.verify_probe(probe, model["tag"], number)


def test_trial_deadlines() -> None:
    import audit
    import check_evidence

    for verify in (audit.check_deadline, check_evidence.check_deadline):
        r = {"agent_seconds": 119}
        t = {"termination": "completed", "events": [{"kind": "tool_finish", "at_ms": 121000}]}
        with pytest.raises(ValueError, match="deadline"):
            verify(t, r)
        with pytest.raises(ValueError, match="deadline"):
            verify(t | {"events": []}, r | {"agent_seconds": 121})


def test_original_record() -> None:
    import check_evidence
    import worlds

    row = rows()["K-k5"]
    seed = 4706095787801906
    state = worlds.world(row, seed).snapshot()
    other = next(record for id, record in state["events"].items() if id != row["task"]["event_id"])
    reply = {"content": [{"type": "text", "text": json.dumps(other)}], "isError": False}
    for verify in (worlds.check_opening, check_evidence.check_opening):
        with pytest.raises(ValueError, match="opening"):
            verify(row, seed, reply)


def test_invocation_timing() -> None:
    import check_evidence

    assert check_evidence.seconds({"claim_ns": 10**9, "export_ns": 3 * 10**9, "seconds": 2}) == 2
    with pytest.raises(ValueError, match="elapsed"):
        check_evidence.seconds({"claim_ns": 10**9, "export_ns": 3 * 10**9, "seconds": 1})


def test_archive_inventory() -> None:
    import check_evidence
    from inputs import inventory

    slots = example()
    names = inventory(slots)
    check_evidence.check_inventory(names, slots, rows())
    for wrong in ([*names, "extra"], [n for n in names if n != "result.md"]):
        with pytest.raises(ValueError, match="inventory"):
            check_evidence.check_inventory(wrong, slots, rows())


def test_elapsed_includes_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import check_evidence
    import launcher
    from common import sha

    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    clock = [2_000_000_000]

    def export(names: list[str]) -> str:
        assert names == ["trials.jsonl"]
        clock[0] += 3_000_000_000
        return f"{sha(b'record')}  trials.jsonl\n"

    def outputs(run: str) -> list[str]:
        return ["audit.json", "trials.jsonl"]

    def now() -> int:
        return clock[0]

    monkeypatch.setattr(launcher, "digests", export)
    monkeypatch.setattr(launcher, "outputs", outputs)
    monkeypatch.setattr(launcher.time, "monotonic_ns", now)
    summary = tmp_path / "audit.json"
    hashes = launcher.finish_exports("r", summary, {}, 1_000_000_000)
    assert check_evidence.seconds(read(summary)) == 4 and sha(summary.read_bytes()) in hashes


@pytest.mark.parametrize(
    "raw", [b'{"message":', b"[]", b'{"model":"m","done":true,"done_reason":"length"}']
)
def test_bad_reply_requires_infrastructure_exit(tmp_path: Path, raw: bytes) -> None:
    import check_evidence
    import count_b

    receipt = Receipt(tmp_path, "run", "t", 1, "candidate", "clean", "clean")

    def send(step: int, body: bytes, capture: Any) -> tuple[int, bytes]:
        capture(body)
        return 200, raw

    with pytest.raises(ConnectionError):
        run_agent(
            orders()[0],
            Session(),
            receipt,
            prompt=PROMPT,
            model="m",
            opening="clean",
            empty_text=None,
            transport=send,
        )
    receipt.state["agent_exit"] = 75
    trial = {
        "termination": "harness_error",
        "outcome": "ERROR",
        "agent_claimed_success": False,
        "failure_detail": "agent reported an infrastructure failure (exit <n>)",
    }
    for terminal in (count_b.terminal, check_evidence.receipt_answer):
        assert terminal(receipt.state, "m", trial, {"lookup_order"}) is None
        with pytest.raises(ValueError, match="recorded exit"):
            terminal(receipt.state, "m", trial | {"termination": "completed"}, {"lookup_order"})


@pytest.mark.parametrize("verb", ["check", "real"])
@pytest.mark.parametrize("broken", ["models.json", "runs/test/descriptor.yaml"])
def test_registration_before_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verb: str, broken: str
) -> None:
    import importlib.metadata
    from subprocess import CalledProcessError

    import admission
    import inputs
    import launcher
    from common import LIST, NOTE, REG, sha

    root = tmp_path / "study"
    claims = tmp_path / "claims"
    claims.mkdir()
    rev = "a" * 40
    (claims / "push-receipt.txt").write_text(rev + " refs/heads/v2/phase0")
    slots = [
        example()[0] | {"slot": f"M{i}", "tag": f"model{i}", "digest": sha(str(i).encode())}
        for i in range(1, 6)
    ]
    write(root / "models.json", {"ollama": "0.32.14", "slots": slots})
    write(root / REG, "registered")
    descriptor = "runs/test/descriptor.yaml"
    write(root / descriptor, {"rule": "frozen"})
    sources = [REG, "models.json"]

    def digests(names: list[str]) -> str:
        return inputs.digests(names, root)

    (root / LIST).write_text(digests(sources))
    (root / NOTE).write_text(digests([descriptor]))

    def git(*args: str) -> bytes:
        if args[0] == "merge-base":
            return rev.encode()
        name = args[-1].split(":./")[1]
        if name == broken:
            raise CalledProcessError(128, list(args))
        return (root / name).read_bytes()

    def release(package: str) -> str:
        return "2.4.1"

    def descriptors(models: list[Row]) -> list[str]:
        return [descriptor]

    monkeypatch.setattr(importlib.metadata, "version", release)
    monkeypatch.setattr(launcher, "version", release)
    monkeypatch.setattr(admission, "descriptors", descriptors)
    monkeypatch.setattr(admission, "sources", lambda: sources)
    monkeypatch.setattr(admission, "git", git)
    monkeypatch.setattr(admission, "digests", digests)
    monkeypatch.setattr(admission, "ROOT", root)
    monkeypatch.setattr(admission, "CLAIMS", claims)
    monkeypatch.setattr(launcher, "ROOT", root)
    monkeypatch.setenv("BOARD0_ENV", str(tmp_path))
    monkeypatch.setattr(
        sys, "argv", ["launcher", verb] + (["board0-pin-M1"] if verb == "real" else [])
    )
    with pytest.raises(ValueError, match="missing pushed blob") as caught:
        launcher.main()
    assert broken in str(caught.value) and not (claims / "board0-pin-M1").exists()
