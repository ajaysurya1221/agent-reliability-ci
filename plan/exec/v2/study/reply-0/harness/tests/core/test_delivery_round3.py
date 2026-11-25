"""Transport-boundary and registered-opening regressions for the stand-in rehearsal."""

from __future__ import annotations

import base64
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from harness import agent, audit, make_suites, offline_model
from harness.tests.core.test_core import FakeSession

ROOT = Path(__file__).resolve().parents[3]


class Delivery(unittest.TestCase):
    def test_transcript_requires_complete_objects_and_exact_task_inventory(self) -> None:
        path = ROOT / "tasks/check/tasks.check.json"
        doc = make_suites.register()
        self.assertEqual(len(audit.transcript(path, doc)), 72)
        with TemporaryDirectory(dir=ROOT) as tmp:
            copy = Path(tmp) / "tasks.check.json"
            for mutation, reason in (
                ("missing", "original_result"),
                ("duplicate", "inventory"),
                ("changed", "pinned"),
            ):
                rows = audit.read(path)
                if mutation == "missing":
                    del rows[0]["original_result"]
                elif mutation == "duplicate":
                    rows[-1] = rows[0]
                else:
                    rows[-1]["original_result"]["content"][0]["text"] += "changed"
                copy.write_text(json.dumps(rows))
                with self.assertRaisesRegex(ValueError, reason):
                    audit.transcript(copy, doc)

    def test_c0_pairs_share_seed_and_eight_orders_use_their_own_amounts(self) -> None:
        from orderdesk.orderdesk_world import make_tools

        doc = make_suites.register()
        with TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "descriptor.yaml"
            descriptor = make_suites.descriptor(
                doc,
                audit.ENV,
                audit.FX,
                "C0",
                "main",
                "4B",
                doc["cells"]["C0"]["main"],
                run="reply0-main-4B-C0",
                plain=False,
            )
            make_suites.write_json(path, descriptor)
            manifest = audit.compile_run_descriptor(path)
            assert isinstance(manifest, audit.SuiteManifest)
            schedule = audit.build_suite_round(manifest, 1)
            pairs: dict[str, set[tuple[int, int]]] = {}
            for trial in schedule:
                order = make_tools(trial.task, trial.seed).snapshot()["order"]
                assert isinstance(order, dict) and isinstance(order["total_cents"], int)
                pairs.setdefault(trial.pair_id, set()).add((trial.seed, order["total_cents"]))
            self.assertEqual(len(schedule), 16)
            self.assertEqual([len(values) for values in pairs.values()], [1] * 8)
            values = set.union(*pairs.values())
            self.assertEqual(len({seed for seed, _ in values}), 8)
            self.assertEqual(len({amount for _, amount in values}), 8)

    def test_capture_at_http_body_write(self) -> None:
        with (
            TemporaryDirectory(dir=ROOT) as tmp,
            patch.object(agent.http.client, "HTTPConnection") as constructor,
            patch("harness.wiring_check.authorize_trial"),
        ):
            root = Path(tmp)
            plan = root / "plan"
            plan.write_text('{"k":{"script":"gives-up"}}')
            conn = constructor.return_value

            def receive(body: bytes) -> None:
                status, reply = offline_model.chat(plan, "k", 0, body)
                conn.getresponse.return_value.status = status
                conn.getresponse.return_value.read.return_value = reply

            conn.send.side_effect = receive
            rec = agent.Receipt(root, "run", "k", 1, "baseline", "clean", "none")

            def send(i: int, body: bytes, capture: agent.Capture) -> tuple[int, bytes]:
                # Change serialization after Receipt.request, before the HTTP adapter sends.
                return agent.ollama_chat(body + b" ", capture, rec, {}, "stand-in", "test")

            reply = rec.request(send, {"model": "stand-in", "messages": []})
            actual = conn.send.call_args.args[0]
            self.assertTrue(actual.endswith(b" "))
            self.assertEqual(base64.b64decode(rec.exchanges[0]["request_b64"]), actual)
            self.assertEqual(reply["received_sha256"], rec.exchanges[0]["sha256"])

    def test_malformed_backend_is_infrastructure_error_with_intact_receipt(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            task = root / "task.json"
            task.write_text('{"cell":"F1","key_id":"k","ask":"test"}')
            receipt_dir = root / "receipts"
            args = [
                "--mcp-config",
                "unused",
                "--task-file",
                str(task),
                "--model",
                agent.MODELS[0],
                "--arm",
                "clean",
                "--opening",
                "none",
                "--prompt",
                "plain",
                "--run-id",
                "test",
                "--offline",
                str(root / "plan"),
            ]
            env = {
                "ARCI_WORKDIR": tmp,
                "ARCI_SEED": "1",
                "REPLY0_ARCI_ARM": "baseline",
                "REPLY0_RECEIPTS": str(receipt_dir),
            }
            cases = [
                {"model": agent.MODELS[0], "done": True, "message": {"role": "assistant"}},
                {
                    "model": "wrong",
                    "done": True,
                    "message": {"role": "assistant", "content": "answer"},
                },
                {
                    "model": agent.MODELS[0],
                    "done": False,
                    "message": {"role": "assistant", "content": "answer"},
                },
            ]
            for i, payload in enumerate(cases):
                raw = json.dumps(payload | {"done_reason": "stop"}).encode()
                env["ARCI_SEED"] = str(i)
                with (
                    self.subTest(payload=payload),
                    patch.dict(os.environ, env),
                    patch.object(agent, "McpSession", return_value=FakeSession()),
                    patch.dict("sys.modules", {"offline_model": offline_model}),
                    patch.object(offline_model, "chat", return_value=(200, raw)),
                ):
                    self.assertEqual(agent.main(args), 75)
                saved = next(
                    r for r in map(audit.read, receipt_dir.glob("*.json")) if r["seed"] == i
                )
                self.assertFalse(saved["complete"])
                self.assertEqual(base64.b64decode(saved["exchanges"][0]["response_b64"]), raw)
                self.assertEqual(saved["exchanges"][0]["done_reason"], "stop")
                self.assertFalse((root / "answer.json").exists())

    def test_direct_agent_never_opens_http(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            task = root / "task.json"
            task.write_text('{"cell":"F1","key_id":"k","ask":"test"}')
            args = [
                "--mcp-config",
                "unused",
                "--task-file",
                str(task),
                "--model",
                agent.MODELS[0],
                "--arm",
                "clean",
                "--opening",
                "none",
                "--prompt",
                "plain",
                "--run-id",
                "reply0-clean-4B-F1-F1-n1",
            ]
            env = {
                "ARCI_WORKDIR": tmp,
                "ARCI_SEED": "1",
                "REPLY0_ARCI_ARM": "baseline",
                "REPLY0_RECEIPTS": str(root / "receipts"),
            }
            with (
                patch.dict(os.environ, env),
                patch.object(agent, "McpSession", return_value=FakeSession()),
                patch.object(agent.http.client, "HTTPConnection") as network,
            ):
                os.environ.pop("REPLY0_LAUNCH_TOKEN", None)
                self.assertEqual(agent.main(args), 75)
                network.assert_not_called()
