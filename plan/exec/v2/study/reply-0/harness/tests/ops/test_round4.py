"""Round-four evidence, publication and launch regressions. All HTTP is mocked."""

from __future__ import annotations

import base64
import io
import json
import os
import select
import subprocess
import sys
import time
import unittest
from contextlib import ExitStack, redirect_stdout
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from harness import audit, make_suites, suite_process
from harness import clean_row as ops
from harness import wiring_check as wire
from harness.tests.ops.test_ops import ROOT, PairFixture

from arci.fingerprint import fingerprint
from arci.schema import TrialEnvelope


class TrialEvidence(PairFixture):
    def test_relabelled_answer_and_supported_teardown(self) -> None:
        base = self.build_store("termination-check", "F1")
        store = base / "store"
        trials = [TrialEnvelope.model_validate(t) for t in audit.lines(store / "trials.jsonl")]
        trial = next(t for t in trials if t.outcome == "PASS")
        original = trial.model_dump(exclude={"record_sha256"})
        detail = "boundary exited before returning"
        for term, outcome, reason, fp, accepted in (
            ("timeout", "FAIL", "trial exceeded max_seconds", None, False),
            ("harness_error", "ERROR", "unspecified", None, False),
            (
                "harness_error",
                "ERROR",
                "worker harness failed",
                fingerprint("harness", "worker harness failed"),
                False,
            ),
            ("harness_error", "ERROR", detail, fingerprint("harness", detail), True),
        ):
            row = original | {
                "termination": term,
                "outcome": outcome,
                "failure_detail": reason,
                "failure_fingerprint": fp,
            }
            self.seal(store, [TrialEnvelope.create(**row) if t == trial else t for t in trials])
            if accepted:
                args = SimpleNamespace(
                    store=store,
                    receipts=base / "receipts",
                    check_dir=self.checks,
                    descriptor=base / "descriptor.yaml",
                    descriptor_sha256=None,
                    edited=None,
                )
                with (
                    patch.object(audit, "arguments", return_value=args),
                    redirect_stdout(io.StringIO()) as out,
                ):
                    self.assertEqual(audit.main(), 0)
                arms = json.loads(out.getvalue())["arms"]
                self.assertEqual(
                    arms[trial.arm]["late_infrastructure"],
                    [{"trial_id": trial.trial_id, "detail": detail}],
                )
            else:
                with (
                    self.subTest(term=term, reason=reason),
                    self.assertRaisesRegex(ValueError, trial.trial_id),
                ):
                    self.verify(base)

        timeout_detail = "trial exceeded max_seconds"
        timeout = original | {
            "termination": "timeout",
            "outcome": "FAIL",
            "agent_claimed_success": False,
            "usage": original["usage"] | {"wall_seconds": 121},
            "failure_detail": timeout_detail,
            "failure_fingerprint": fingerprint("timeout", timeout_detail),
        }
        self.seal(store, [TrialEnvelope.create(**timeout) if t == trial else t for t in trials])
        report = audit.summary(self.verify(base))
        self.assertEqual(
            report["arms"][trial.arm]["late_infrastructure"],
            [{"trial_id": trial.trial_id, "detail": timeout_detail}],
        )
        self.assertEqual(report["arms"][trial.arm]["wall_timeouts"], 1)

    def test_receipt_identity_completion_and_terminal_length(self) -> None:
        base = self.build_store("model-check", "F1")
        path = next(
            p for p in (base / "receipts").iterdir() if audit.read(p)["arci_arm"] == "baseline"
        )
        receipt = audit.read(path)
        for index in (0, -1):
            exchange = receipt["exchanges"][index]
            original = exchange["response_b64"]
            payload = json.loads(base64.b64decode(original))
            for change in ({"model": "different"}, {"done": False}, {"done": 1}):
                exchange["response_b64"] = base64.b64encode(
                    json.dumps(payload | change).encode()
                ).decode()
                path.write_text(json.dumps(receipt))
                with self.assertRaisesRegex(ValueError, "response model|unfinished"):
                    self.verify(base)
            exchange["response_b64"] = original
        exchange["response_b64"] = base64.b64encode(
            json.dumps(payload | {"done_reason": "length"}).encode()
        ).decode()
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "done_reason"):
            self.verify(base)
        exchange["done_reason"] = "length"
        path.write_text(json.dumps(receipt))
        args = SimpleNamespace(
            store=base / "store",
            receipts=base / "receipts",
            check_dir=self.checks,
            descriptor=base / "descriptor.yaml",
            descriptor_sha256=None,
            edited=None,
        )
        with (
            patch.object(audit, "arguments", return_value=args),
            redirect_stdout(io.StringIO()) as out,
        ):
            self.assertEqual(audit.main(), 0)
        arms = json.loads(out.getvalue())["arms"]
        self.assertEqual([arms[side]["terminal_length"] for side in ops.SIDES], [1, 0])


class Publication(unittest.TestCase):
    def test_staged_hashes_inventory_and_partial_label(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp, ExitStack() as st:
            root = Path(tmp)
            st.enter_context(
                patch.multiple(ops, ROOT=root, OPS=root / "claims", RUNS=root / "runs")
            )
            st.enter_context(patch.object(wire, "fixed_public", return_value=set()))
            st.enter_context(patch.object(ops, "operator_identifiers", return_value=set()))
            (root / "result.md").write_bytes(b"result")
            s = ops.Slot("main", "4B", "F1")
            directory = ops.OPS / s.id
            directory.mkdir(parents=True)
            (directory / "claim.json").write_bytes(b"{}")
            folder = ops.RUNS / s.id
            folder.mkdir(parents=True)
            for name in ops.EXPORTS:
                (folder / name).write_bytes(b"original")
            pins = {name: audit.digest(folder / name) for name in ops.EXPORTS}
            marker = directory / "finished.json"
            marker.write_text(json.dumps({"hashes": pins}))
            destination = root / "published"
            original_write = Path.write_bytes

            def change_during_staging(path: Path, data: bytes) -> int:
                if path.name == "receipts.jsonl":
                    data += b" altered"
                return original_write(path, data)

            with (
                patch.object(Path, "write_bytes", change_during_staging),
                self.assertRaisesRegex(ValueError, "staged receipts"),
            ):
                ops.assemble(destination, [s])
            self.assertFalse(destination.exists())
            (folder / "ledger.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "staged inventory"):
                ops.assemble(destination, [s])
            self.assertFalse(destination.exists())
            marker.unlink()
            ops.assemble(destination, [s])
            self.assertEqual(
                audit.read(destination / "runs" / s.id / "partial.json"), {"status": "partial"}
            )

    def test_uninspectable_payloads_and_mcp_blob(self) -> None:
        identifier = "synth-" + "account"
        for key in ("blob", "data", "request_b64"):
            for payload in (
                identifier.encode(),
                identifier.encode("utf-16"),
                b"\xff",
                b"a\x00b",
                b"\x01\x02\x03",
            ):
                value = {"resource": {key: base64.b64encode(payload).decode()}}
                with self.subTest(key=key), self.assertRaises(ValueError):
                    ops.safe_bytes(json.dumps(value).encode(), {identifier})
            with self.assertRaises(ValueError):
                ops.safe_bytes(json.dumps({key: "%%%"}).encode(), set())
        for source in ("text".encode("utf-16"), "text".encode("utf-16le"), b"\xff"):
            with self.assertRaises(ValueError):
                ops.safe_bytes(source, set())
        with self.assertRaisesRegex(ValueError, "declared encoding"):
            ops.safe_bytes(
                b'{"resource":{"mimeType":"text/plain;charset=UTF-16","blob":"YWI="}}', set()
            )
        ops.safe_bytes(b'{"resource":{"blob":"cHVibGlj"}}', set())
        ops.safe_bytes(b'{"properties":{"blob":{"type":"string"}}}', set())
        with self.assertRaisesRegex(ValueError, "resource blob"):
            ops.safe_bytes(b'{"resource":{"blob":{"type":"string"}}}', set())


class Launch(unittest.TestCase):
    def test_claim_failure_precedes_metadata(self) -> None:
        reg = wire.Registration("a" * 40, "1", {}, "b" * 64)
        with (
            TemporaryDirectory(dir=ROOT) as tmp,
            patch.object(ops, "OPS", Path(tmp)),
            patch.object(ops, "claim", side_effect=OSError),
            patch.object(ops, "deadline", return_value=datetime.max),
            patch.object(wire, "registration", return_value=reg),
            patch.object(wire, "live_paths"),
            patch.object(wire, "versions"),
            patch.object(audit, "fixture"),
            patch.dict(os.environ, {"REPLY0_ENV": str(wire.SHARED / "env")}),
            patch.object(wire, "metadata") as metadata,
        ):
            with self.assertRaises(OSError):
                slot = ops.Slot("wiring", "4B")
                ops.execute(slot, {}, [slot])
            metadata.assert_not_called()

    def test_probe_lock_push_body_model_and_ordinal_at_opener(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp, ExitStack() as st:
            root = Path(tmp)
            claims = root / "claims"
            claims.mkdir()
            (claims / "suite.lock").touch()
            st.enter_context(patch.multiple(wire, ROOT=root, CLAIMS=claims))
            st.enter_context(patch.object(ops, "OPS", claims))
            (root / wire.REG).write_bytes(b"registered")
            reg = wire.Registration("a" * 40, "1", {}, wire.digest(b"registered"))
            slot = ops.Slot("wiring", "4B")
            directory = ops.claim(slot, reg)
            (claims / "active-suite.json").write_text(
                json.dumps({"claim": slot.id, "launcher": os.getpid(), "groups": []})
            )
            receipt = claims / "push-receipt.txt"
            receipt.write_text(reg.commit + " refs/heads/v2/phase0\n")
            st.enter_context(patch.object(wire, "git", return_value=reg.commit.encode()))
            opener = st.enter_context(patch.object(wire, "local_opener")).return_value
            tag = wire.MODELS[slot.model]
            body = json.dumps(wire.warm_body(tag)).encode()
            with self.assertRaisesRegex(ValueError, "admission"):
                wire.probe_chat(0, body)
            with self.assertRaisesRegex(ValueError, "metadata"):
                wire.metadata(reg, "4B")
            token = wire.PROBE.set(wire.ProbeAdmission(directory, slot.id, slot.model, reg))
            st.callback(wire.PROBE.reset, token)
            with self.assertRaisesRegex(ValueError, "metadata"):
                wire.metadata(reg, "12B")
            with self.assertRaisesRegex(ValueError, "lock"):
                wire.probe_chat(0, body)
            st.enter_context(ops.locked("suite"))
            claim = st.enter_context((directory / "claim.json").open("rb"))
            ops.fcntl.flock(claim, ops.fcntl.LOCK_EX)
            with self.assertRaisesRegex(ValueError, "ordinal"):
                wire.probe_chat(0, body)
            for endpoint in ("version", "tags", "show"):
                wire.authorize_probe(
                    endpoint,
                    json.dumps({"model": tag}).encode() if endpoint == "show" else None,
                    None,
                )
            for step, bad in (
                (1, body),
                (0, body.replace(tag.encode(), b"unknown")),
                (0, body.replace(b"OK.", b"new")),
            ):
                with self.assertRaisesRegex(ValueError, "ordinal"):
                    wire.probe_chat(step, bad)
            receipt.write_text("invalid")
            with self.assertRaisesRegex(ValueError, "push receipt"):
                wire.probe_chat(0, body)
            opener.open.assert_not_called()
            receipt.write_text(reg.commit + " refs/heads/v2/phase0\n")
            wire.probe_chat(0, body)
            with self.assertRaisesRegex(ValueError, "ordinal"):
                wire.probe_chat(0, body)
            self.assertEqual(opener.open.call_count, 1)
            for endpoint in ("version", "tags", "ps"):
                wire.authorize_probe(endpoint, None, None)
            violet = json.dumps(wire.wiring_body(tag, "violet")).encode()
            empty = json.dumps(wire.wiring_body(tag, "")).encode()
            with self.assertRaisesRegex(ValueError, "ordinal"):
                wire.probe_chat(1, empty)
            wire.probe_chat(0, violet)
            wire.probe_chat(1, empty)
            with self.assertRaisesRegex(ValueError, "exhausted"):
                wire.probe_chat(1, empty)
            self.assertEqual(opener.open.call_count, 3)

    def test_interrupted_launcher_leaves_detached_child_guarded(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            directory = root / "reply0-main-4B-F1"
            directory.mkdir()
            (directory / "claim.json").write_text("{}")
            # The launcher calls the production runner spawn adapter. Its new-session
            # child forks an ordinary descendant, which keeps the group alive even
            # after the group leader exits and the launcher is killed.
            launcher_code = """
import json, os, sys
from pathlib import Path
from unittest.mock import patch
from arci import runner
from harness import suite_process
directory = Path(sys.argv[1])
(directory.parent/"active-suite.json").write_text(json.dumps(
    {"claim": directory.name, "launcher": os.getpid(), "groups": []}))
def run_fake_cli(argv):
    child = runner.subprocess.Popen(
        [sys.executable, "-B", "-c", sys.argv[2]], start_new_session=True)
    child.wait(timeout=5)
    print("leader exited", flush=True)
    import time
    time.sleep(15)
    return 0
with patch("arci.cli.main", run_fake_cli):
    suite_process.run(directory, [])
"""
            child_code = """
import os, sys
if os.fork() == 0:
    print(os.getpgrp(), flush=True)
    sys.stdin.read()
"""
            with subprocess.Popen(
                [sys.executable, "-B", "-c", launcher_code, str(directory), child_code],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                bufsize=0,
            ) as launcher:
                assert launcher.stdout and launcher.stdin
                try:
                    output = []
                    for _ in range(2):
                        self.assertTrue(select.select([launcher.stdout], [], [], 10)[0])
                        output.append(launcher.stdout.readline().strip())
                    output.remove(b"leader exited")
                    group = int(output[0])
                    launcher.kill()
                    launcher.wait(timeout=3)
                    self.assertEqual(audit.read(root / "active-suite.json")["groups"], [group])
                    with self.assertRaisesRegex(ValueError, "suite processes still active"):
                        suite_process.clear(root)
                finally:
                    launcher.stdin.close()
                    launcher.kill()
                    launcher.wait(timeout=3)
            deadline = time.monotonic() + 5
            while suite_process.alive(group, group=True) and time.monotonic() < deadline:
                time.sleep(0.02)
            suite_process.clear(root)
            self.assertFalse((root / "active-suite.json").exists())
            self.assertTrue((directory / "claim.json").exists())

    def test_initial_git_blob_deadline(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            fake = root / "slow-git"
            fake.write_text("#!/bin/sh\nexec /bin/sleep 10\n")
            fake.chmod(0o700)
            source = (ROOT / "harness/run-reply0.sh").read_text()
            self.assertEqual(source.count("timeout=15"), 1)
            script = root / "harness/run-reply0.sh"
            script.parent.mkdir()
            script.write_text(
                source.replace("/opt/homebrew/bin/git", str(fake)).replace(
                    "timeout=15", "timeout=0.1"
                )
            )
            run = subprocess.run(
                ["sh", str(script), "check"],
                capture_output=True,
                env=os.environ | {"REPLY0_ENV": str(wire.SHARED / "env")},
                timeout=4,
            )
            self.assertEqual(run.returncode, 67)
            self.assertIn(b"no matching pushed", run.stderr)

    def test_node_pin_and_bounded_probes(self) -> None:
        env = wire.SHARED / "env"
        binary = env / "node/bin/node"
        with patch.dict(os.environ, {"PATH": "/unusable"}):
            self.assertEqual(wire.registered_node(env), binary)
            argv = make_suites.relay_argv(env, audit.FX, "F1", "filesystem", [], None)
            self.assertEqual(argv[argv.index("--") + 1], str(binary))
            self.assertEqual(audit.server_command("F1", "filesystem")[0][0], str(binary))
        self.assertIn(audit.digest(binary), (ROOT / "ENVIRONMENT.md").read_text())
        with (
            TemporaryDirectory(dir=ROOT) as tmp,
            patch.dict(os.environ, {"PATH": str(binary.parent)}),
        ):
            with self.assertRaisesRegex(ValueError, "missing"):
                wire.registered_node(Path(tmp))
            fake = Path(tmp) / "node/bin/node"
            fake.parent.mkdir(parents=True)
            fake.write_bytes(b"different")
            fake.chmod(0o700)
            with self.assertRaisesRegex(ValueError, "digest"):
                wire.registered_node(Path(tmp))
        with patch.object(subprocess, "check_output", wraps=subprocess.check_output) as probe:
            with patch.object(sys, "prefix", str(env / "py")):
                wire.versions(env)
            audit.fixture()
            wire.git("rev-parse", "--git-dir")
            commands = [c.args[0] for c in probe.call_args_list]
            self.assertIn([str(binary), "--version"], commands)
            self.assertTrue(all(0 < c.kwargs["timeout"] <= 30 for c in probe.call_args_list))
