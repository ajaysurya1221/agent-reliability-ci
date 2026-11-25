"""Section 12.1, using the released environment and the offline chat transport."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import signal
import subprocess
import sys
import unittest
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from harness import agent, make_suites, offline_model, relay, reply0_oracle  # noqa: E402
from tasks.reply0_grade import passes  # noqa: E402


class FakeSession:
    def close(self) -> None:
        pass

    def list_tools(self) -> list[agent.JsonObject]:
        return [{"name": "read", "description": "one tool", "inputSchema": {"type": "object"}}]

    def call_tool(self, name: str, arguments: agent.JsonObject) -> tuple[str, bool]:
        return ("wrong" if arguments.get("bad") else "all text", False)


class Rules(unittest.TestCase):
    def test_rule_guards_and_complete_objects(self) -> None:
        for cell, tool, text, args, matched in [
            ("G1", "git_log", "Commit history:\n", {}, False),
            ("G1", "git_log", "Commit history:\n", {"start_timestamp": "bad"}, True),
            ("F2", "search_files", "No matches found", {"pattern": "a-1.x"}, True),
            ("F2", "search_files", "No matches found", {"pattern": "a\n"}, False),
            ("F2", "search_files", "No matches found\n", {"pattern": "a"}, False),
            ("F2", "git_log", "No matches found", {}, False),
            ("F2", "search_files", "No matches found", {"pattern": "@(todo|x)"}, False),
            (
                "F1",
                "read_text_file",
                "ENOENT: no such file or directory, lstat 'x'",
                {"path": "/a/b"},
                True,
            ),
        ]:
            for mode in ("naming", "generic"):
                with self.subTest(cell=cell, args=args, mode=mode, text=text):
                    rules = ROOT / "harness/rules" / f"{cell}-{mode}.json"
                    (rule,) = json.loads(rules.read_text())
                    original: dict[str, Any] = {
                        "content": [{"type": "text", "text": text, "_meta": {"keep": 1}}],
                        "isError": cell == "F1",
                        "structuredContent": {"content": text, "x": 3},
                        "extra": [1],
                    }
                    encoded = json.dumps(original)
                    result = relay.rewrite(rule, tool, args, original)
                    self.assertEqual(original["content"][0]["text"], text)
                    self.assertEqual(json.dumps(original), encoded)
                    self.assertEqual(result != original, matched)
                    expected = json.loads(encoded)
                    if matched:
                        new = result["content"][0]["text"]
                        expected["content"][0]["text"] = expected["structuredContent"][
                            "content"
                        ] = new
                        if cell == "F1" and mode == "naming":
                            self.assertIn('path "/a"', new)
                        if mode == "generic":
                            self.assertEqual(new, make_suites.register()["generic_sentence"])
                    self.assertEqual(result, expected)
                    original["isError"] = not original["isError"]
                    self.assertEqual(relay.rewrite(rule, tool, args, original), original)


class AgentTests(unittest.TestCase):
    def test_request_bytes_openings_and_answer(self) -> None:
        call = {"name": "read", "arguments": {"bad": True}}
        good = {"name": "read", "arguments": {}}
        for opening, history in (("bad", "wrong"), ("clean", "all text"), ("none", None)):
            with self.subTest(opening=opening), TemporaryDirectory() as folder:
                d = Path(folder)
                rec = agent.Receipt(d, "r", "k", 42, "baseline", "clean", opening)
                (d / "plan").write_text(
                    json.dumps({"k": {"script": "corrected", "good": [good], "expect": ["ANSWER"]}})
                )
                seen: list[bytes] = []

                def transport(
                    step: int,
                    body: bytes,
                    capture: agent.Capture,
                    sent: list[bytes] = seen,
                    plan: Path = d / "plan",
                ) -> tuple[int, bytes]:
                    capture(body)
                    sent.append(body)
                    return offline_model.chat(plan, "k", step, body)

                task: Any = {
                    "key_id": "k",
                    "cell": "F1",
                    "ask": "question",
                    "bad": call,
                    "clean": good,
                    "private_field": "DO NOT SEND",
                }
                answer = agent.run_agent(
                    task,
                    FakeSession(),
                    rec,
                    prompt="system",
                    model=agent.MODELS[0],
                    opening=opening,
                    empty_text=None,
                    transport=transport,
                )
                rec.finish(d, answer)
                self.assertEqual(answer, "ANSWER")
                value = json.loads(rec.path.read_bytes())
                self.assertEqual(value["steps"], 2)
                self.assertEqual(json.loads((d / "answer.json").read_bytes()), {"answer": answer})
                for body, exchange in zip(seen, value["exchanges"], strict=True):
                    self.assertEqual(base64.b64decode(exchange["request_b64"]), body)
                    self.assertEqual(hashlib.sha256(body).hexdigest(), exchange["sha256"])
                    self.assertNotIn(b"DO NOT SEND", body)
                messages = [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "question"},
                ]
                if history is not None:
                    messages += [
                        {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [{"function": call if opening == "bad" else good}],
                        },
                        {"role": "tool", "tool_name": "read", "content": history},
                    ]
                self.assertEqual(json.loads(seen[0])["messages"], messages)
                self.assertEqual(json.loads(seen[1])["messages"][-1]["content"], "all text")
                self.assertEqual(json.loads(seen[0])["options"], {"temperature": 0.7})
                self.assertEqual(value["calls"][-1], good)

    def test_duplicate_receipt_unanswered_and_invalid_response(self) -> None:
        with TemporaryDirectory() as folder:

            def receipt() -> agent.Receipt:
                return agent.Receipt(Path(folder), "r", "k", 0, "candidate", "clean", "none")

            rec = receipt()
            with self.assertRaises(agent.BackendError):
                rec.request(lambda i, b, capture: (capture(b) or 200, b"invalid"), {})
            self.assertEqual(json.loads(rec.path.read_bytes())["exchanges"][0]["status"], 200)
            with self.assertRaises(FileExistsError):
                receipt().request(lambda i, b, capture: (capture(b) or 200, b"{}"), {})
            other = agent.Receipt(Path(folder), "r", "k", 0, "baseline", "clean", "none")
            self.assertNotEqual(other.path, rec.path)

            def unavailable(step: int, body: bytes, capture: agent.Capture) -> tuple[int, bytes]:
                capture(body)
                raise ConnectionError

            with self.assertRaises(ConnectionError):
                other.request(unavailable, {})
            self.assertIsNone(json.loads(other.path.read_bytes())["exchanges"][0]["status"])

    def test_first_response_survives_kill(self) -> None:
        program = """
import os, signal, sys
from pathlib import Path
from harness.agent import Receipt
r=Receipt(Path(sys.argv[1]),"run","key",0,"baseline","clean","none")
reply = b'{"model":"m","done":true,"message":{"content":"hi"}}'
r.request(lambda i,b,c:(c(b) or 200,reply), {"model":"m","messages":[]})
os.kill(os.getpid(),signal.SIGKILL)
"""
        with TemporaryDirectory() as folder:
            child = subprocess.run(
                [sys.executable, "-P", "-c", program, folder],
                env={**os.environ, "PYTHONPATH": str(ROOT)},
                check=False,
            )
            self.assertEqual(child.returncode, -signal.SIGKILL)
            (path,) = Path(folder).glob("*.json")
            value = json.loads(path.read_bytes())
            self.assertFalse(value["complete"])
            self.assertEqual(value["exchanges"][0]["status"], 200)

    def test_eight_steps_and_absent_opening_tool(self) -> None:
        with TemporaryDirectory() as folder:
            d = Path(folder)
            rec = agent.Receipt(d, "run", "key", 0, "candidate", "clean", "none")
            task: Any = {"cell": "F1", "ask": "hi", "bad": {"name": "unknown", "arguments": {}}}

            def again(step: int, body: bytes, capture: agent.Capture) -> tuple[int, bytes]:
                capture(body)
                return (
                    200,
                    b'{"model":"m","done":true,"message":{"role":"assistant","tool_calls":[{"function":{"name":"read","arguments":{}}}]}}',
                )

            with self.assertRaises(agent.OpeningUnavailable):
                agent.run_agent(
                    task,
                    FakeSession(),
                    rec,
                    prompt="p",
                    model="m",
                    opening="bad",
                    empty_text=None,
                    transport=again,
                )
            self.assertFalse(rec.path.exists())
            answer = agent.run_agent(
                task,
                FakeSession(),
                rec,
                prompt="p",
                model="m",
                opening="none",
                empty_text=None,
                transport=again,
            )
            rec.finish(d, answer)
            self.assertIsNone(answer)
            self.assertEqual(len(rec.exchanges), 8)

    def test_cli_publishes_all_arm_files_before_the_handshake(self) -> None:
        doc = make_suites.register()
        row = doc["cells"]["F1"]["main"][0]
        with TemporaryDirectory() as folder:
            work = Path(folder)
            task = make_suites.public_task("F1", row)
            source = work / "task.json"
            source.write_text(json.dumps(task))
            plan = work / "plan.json"
            plan.write_text(json.dumps({task["key_id"]: {"script": "gives-up"}}))
            for label, (rules, server) in agent.ARMS.items():
                # An unadvertised opening cannot generate a request to either transport.
                def handshake(
                    config: Path, expected: tuple[str, str, str] = (label, rules, server)
                ) -> FakeSession:
                    arm = json.loads((work / "reply0-arm.json").read_bytes())
                    self.assertEqual((arm["arm"], arm["rules"], arm["server"]), expected)
                    return FakeSession()

                env = {
                    "ARCI_WORKDIR": folder,
                    "ARCI_SEED": "0",
                    "REPLY0_ARCI_ARM": "baseline",
                    "REPLY0_RECEIPTS": str(work / "receipts"),
                }
                args = [
                    "--mcp-config",
                    "unused",
                    "--task-file",
                    str(source),
                    "--model",
                    agent.MODELS[0],
                    "--arm",
                    label,
                    "--opening",
                    "bad",
                    "--prompt",
                    "p",
                    "--run-id",
                    "test",
                    "--offline",
                    str(plan),
                ]
                with (
                    self.subTest(label=label),
                    patch.dict(os.environ, env),
                    patch.object(agent, "McpSession", side_effect=handshake),
                ):
                    self.assertEqual(agent.main(args), 70)
            self.assertFalse(list((work / "receipts").glob("*.json")))


class GradingAndSuites(unittest.TestCase):
    def test_answer_only_and_corrupt_ledger(self) -> None:
        with TemporaryDirectory() as folder:
            directory = Path(folder)
            task = {"cell": "C0", "key_id": "C0-c1"}
            with self.assertRaises(FileNotFoundError):
                reply0_oracle.snapshot(task, folder)
            for data in ("", "invalid\n", '{"record":"call","seq":9}\n'):
                (directory / "ledger.jsonl").write_text(data)
                with self.assertRaises(ValueError):
                    reply0_oracle.snapshot(task, folder)
            state = {"world": {"order": {"total_cents": 1260}}, "answer": "“1,260.”", "ledger": []}
            self.assertTrue(reply0_oracle.passed(task, state))
            state["answer"] = "-1260"
            self.assertFalse(reply0_oracle.passed(task, state))
            self.assertFalse(passes("main\nmain", ["main"], []))
            self.assertFalse(passes("a" * 601, ["a" * 601], []))
            self.assertTrue(passes("beta\nalpha", ["alpha", "beta"], []))

    def test_descriptor_shapes(self) -> None:
        doc = make_suites.register()
        env = Path(os.environ.get("REPLY0_ENV", Path(sys.prefix).parent))
        for cell in doc["cells"]:
            for size, rounds in make_suites.ROUNDS.items():
                tasks = doc["cells"][cell]["main"][:size]
                d = make_suites.descriptor(
                    doc, env, make_suites.FX, cell, "main", "4B", tasks, run="test", plain=False
                )
                manifest = import_module("arci.descriptor").loads_suite_descriptor(json.dumps(d))
                self.assertEqual(manifest.max_rounds, rounds)
                self.assertTrue(manifest.validate_seal())
                self.assertEqual(bool(manifest.conditions[0].faults), cell == "C0")
                for row in d["tasks"]:
                    self.assertFalse({"expect", "decoys", "good", "source"} & row.keys())
        for phase, labels in (
            ("generic", ("naming-sentence", "generic-sentence")),
            ("confirmation", ("edited-server", "server-as-shipped")),
        ):
            d = make_suites.descriptor(
                doc,
                env,
                make_suites.FX,
                "F1",
                phase,
                "12B",
                doc["cells"]["F1"]["held_out" if phase == "confirmation" else "main"],
                run="test",
                plain=False,
                edited=env / "edited" if phase == "confirmation" else None,
            )
            self.assertEqual((d["baseline"]["label"], d["candidate"]["label"]), labels)
            self.assertEqual("--rules" in d["mcp_server"]["argv"], phase == "generic")
            self.assertTrue(
                import_module("arci.descriptor")
                .loads_suite_descriptor(json.dumps(d))
                .validate_seal()
            )

    def test_protected_path(self) -> None:
        from tasks import check_tasks

        with TemporaryDirectory() as folder:
            d = Path(folder)
            (d / "files").mkdir()
            (d / "repo").mkdir()
            (d / "files" / "alias").symlink_to(reply0_oracle.KEY_FILE)
            with self.assertRaises(SystemExit):
                check_tasks.check_protected_paths(d)

    def test_edited_destination(self) -> None:
        from harness.make_edited import build

        env = Path(os.environ.get("REPLY0_ENV", Path(sys.prefix).parent))
        with TemporaryDirectory() as folder, self.assertRaises(ValueError):
            build(env, Path(folder) / "node_modules", "F1")
