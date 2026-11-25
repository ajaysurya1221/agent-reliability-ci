"""Negative admission and publication cases, using only temporary study evidence."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest.mock import patch

from harness import audit, make_suites
from harness import clean_row as ops
from harness import wiring_check as wire

ROOT = Path(__file__).resolve().parents[3]


class Launch(unittest.TestCase):
    def test_fallback_requires_empty_text_rejection(self) -> None:
        for status, raw in [
            (400, b'{"error":"invalid model"}'),
            (503, b"empty rejected"),
            (400, b'{"error":"invalid model: empty model name"}'),
            (200, b"bad"),
            (None, b""),
        ]:

            def send(
                i: int, body: bytes, status: int | None = status, raw: bytes = raw
            ) -> tuple[int, bytes]:
                if not i:
                    return 200, b'{"model":"stand-in","done":true,"message":{"role":"assistant"}}'
                if status is None:
                    raise TimeoutError
                return status, raw

            with self.assertRaisesRegex(ValueError, "invalid wiring response|inconclusive"):
                records = wire.wiring("stand-in", send, lambda _: None)
                wire.fallback(records, "stand-in")

    def test_remote_receipt_and_tracking_ref(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp, patch.object(wire, "CLAIMS", Path(tmp)):
            path = Path(tmp) / "push-receipt.txt"
            remote = "1" * 40
            with patch.object(wire, "git", return_value=remote.encode()):
                with self.assertRaises(ValueError):
                    wire.pinned_commit(wire.LIST)
                for ref in ("refs/heads/main", "refs/heads/v2/phase0\nextra"):
                    path.write_text(f"{remote} {ref}\n")
                    with self.assertRaisesRegex(ValueError, "push receipt"):
                        wire.pinned_commit(wire.LIST)
                path.write_text(f"{remote} refs/heads/v2/phase0\n")
                self.assertEqual(wire.pinned_commit(wire.LIST), remote)
            with (
                patch.object(wire, "git", return_value=b"2" * 40),
                self.assertRaisesRegex(ValueError, "tracking"),
            ):
                wire.pinned_commit(wire.LIST)

    def test_active_claim_binds_descriptor_registration_and_schedule(self) -> None:
        from harness.agent import Receipt

        s = ops.Slot("clean", "4B", "F1", "F1-n1")
        doc = make_suites.register()
        reg = wire.Registration("a" * 40, "1", {}, wire.digest(b"registered"))
        with TemporaryDirectory(dir=ROOT) as tmp, ExitStack() as st:
            root = Path(tmp)
            claims = root / "claims"
            claims.mkdir()
            st.enter_context(patch.multiple(ops, ROOT=root, OPS=claims))
            st.enter_context(patch.multiple(wire, ROOT=root, CLAIMS=claims))
            directory = ops.claim(s, reg)
            path = root / "runs" / s.id / "descriptor.yaml"
            desc = ops.config(s, doc, {}, False)
            make_suites.write_json(path, desc)
            registration = root / wire.REG
            registration.write_text("registered")
            spec = audit.compile_run_descriptor(path)
            assert isinstance(spec, audit.Manifest)
            trial = audit.build_schedule(spec)[0]
            receipt = Receipt(
                directory / "receipts", s.id, s.task, trial.seed, trial.arm, "clean", "clean"
            )
            st.enter_context(patch.dict(os.environ, {"REPLY0_RECEIPTS": str(receipt.path.parent)}))
            os.environ.pop("REPLY0_LAUNCH_TOKEN", None)
            os.environ.pop("REPLY0_CLAIMS", None)

            def check() -> None:
                wire.authorize_trial(
                    receipt.state, trial.task, wire.MODELS["4B"], doc["system_prompt"]
                )

            with self.assertRaisesRegex(ValueError, "active launcher claim"):
                check()
            ops.bind_schedule(s, directory, reg, path, audit.digest(path), "test capability")
            os.environ["REPLY0_LAUNCH_TOKEN"] = "test capability"
            with (directory / "claim.json").open("rb") as lock:
                ops.fcntl.flock(lock, ops.fcntl.LOCK_EX)
                check()
                for field, new in (
                    ("seed", trial.seed + 1),
                    ("arm", "edited-server"),
                    ("arci_arm", "unknown"),
                ):
                    with (
                        patch.dict(receipt.state, {field: new}),
                        self.assertRaisesRegex(ValueError, "absent"),
                    ):
                        check()
                for file in (path, registration):
                    saved = file.read_bytes()
                    file.write_bytes(saved + b" ")
                    with self.assertRaisesRegex(ValueError, "binding"):
                        check()
                    file.write_bytes(saved)
            with self.assertRaisesRegex(ValueError, "inactive"):
                check()

    def test_different_models_cannot_overlap_and_wait_expires(self) -> None:
        entered, release = Event(), Event()
        with TemporaryDirectory(dir=ROOT) as tmp, ExitStack() as st:
            root = Path(tmp)
            st.enter_context(patch.multiple(ops, OPS=root, LOCK_SECONDS=0.15))
            st.enter_context(patch.dict(os.environ, {"REPLY0_ENV": str(audit.ENV)}))
            st.enter_context(patch.object(wire, "live_paths"))
            reg = wire.Registration("1" * 40, "1", {}, wire.digest(b"registered"))
            st.enter_context(patch.object(wire, "registration", return_value=reg))
            st.enter_context(patch.object(wire, "versions"))
            st.enter_context(patch.object(audit, "fixture"))

            def admit(
                slot: ops.Slot, registration: wire.Registration, *_: object
            ) -> tuple[Path, ops.Row]:
                return ops.claim(slot, registration), {}

            st.enter_context(patch.object(ops, "admission", side_effect=admit))

            def hold(*args: object) -> None:
                entered.set()
                self.assertTrue(release.wait(5))

            st.enter_context(patch.object(ops, "launch", side_effect=hold))
            a, b = (ops.Slot("main", model, "F1") for model in wire.MODELS)
            with ThreadPoolExecutor(1) as pool:
                first = pool.submit(ops.execute, a, {}, [a, b])
                try:
                    self.assertTrue(entered.wait(5))
                    with self.assertRaisesRegex(TimeoutError, "suite lock"):
                        ops.execute(b, {}, [a, b])
                finally:
                    release.set()
                first.result(timeout=5)
            self.assertTrue((root / a.id / "claim.json").is_file())
            self.assertFalse((root / b.id).exists())
            with ops.locked(), self.assertRaisesRegex(TimeoutError, "admission lock"), ops.locked():
                self.fail("acquired a second admission lock")

    def test_postrun_timeout_keeps_consumed_claim_and_partial_output(self) -> None:
        import subprocess

        with (
            TemporaryDirectory(dir=ROOT) as tmp,
            patch.object(ops, "OPS", Path(tmp)),
            patch.object(ops, "POSTRUN_SECONDS", 0.5),
        ):
            s = ops.Slot("main", "4B", "F1")
            reg = wire.Registration("a" * 40, "1", {}, wire.digest(b"registered"))
            directory = ops.claim(s, reg)
            for name in ("audit", "count_a", "count_b"):
                path = directory / (name + ".json")
                with (
                    path.open("xb") as out,
                    (directory / "run.log").open("a") as log,
                    self.assertRaises(subprocess.TimeoutExpired),
                ):
                    ops.postrun(
                        [
                            sys.executable,
                            "-B",
                            "-c",
                            "import time; print('partial', flush=True); time.sleep(60)",
                        ],
                        out,
                        log,
                        dict(os.environ),
                    )
                self.assertEqual(path.read_bytes(), b"partial\n")
            with self.assertRaises(FileExistsError):
                ops.claim(s, reg)
            self.assertFalse((directory / "finished.json").exists())

    def test_private_identifiers_rejected_and_original_kept(self) -> None:
        identifiers = {
            "HOME": "/neutral/personal-home",
            "USER": "example-login",
            "LOGNAME": "example-account",
            "GIT_AUTHOR_NAME": "Example Person",
            "GIT_COMMITTER_EMAIL": "example@unit.invalid",
        }
        with TemporaryDirectory(dir=ROOT) as tmp, patch.dict(os.environ, identifiers):
            root = Path(tmp)
            for value in identifiers.values():
                escaped = "".join(f"\\u{ord(c):04x}" for c in value)
                body = json.dumps(
                    {"data": base64.b64encode(('{"message":"' + escaped + '"}').encode()).decode()}
                )
                payload = json.dumps({"response_b64": base64.b64encode(body.encode()).decode()})
                for raw in (
                    ("log " + payload + "\n").encode(),
                    json.dumps({"payload": [base64.b64encode(value.encode()).decode()]}).encode(),
                    json.dumps({"ledger": [json.dumps({"text": value})]}).encode(),
                ):
                    with self.assertRaisesRegex(ValueError, "personal"):
                        ops.safe_bytes(raw)
            source = root / "result.md"
            source.write_text(json.dumps({"email": identifiers["GIT_COMMITTER_EMAIL"]}))
            original = hashlib.sha256(source.read_bytes()).hexdigest()
            with (
                patch.object(ops, "ROOT", root),
                patch.object(wire, "fixed_public", return_value=set()),
                self.assertRaisesRegex(ValueError, "personal"),
            ):
                ops.assemble(root / "published", [])
            self.assertFalse((root / "published").exists())
            self.assertEqual(audit.digest(source), original)
            with self.assertRaisesRegex(ValueError, "operator home"):
                wire.live_paths(Path(identifiers["HOME"]) / "checkout", wire.SHARED / "env")
            with self.assertRaisesRegex(ValueError, "operator home"):
                wire.live_paths(wire.CHECKOUT, Path(identifiers["HOME"]) / "env")
            with (
                patch.dict(os.environ, {"REPLY0_CLAIMS": str(root)}),
                self.assertRaisesRegex(ValueError, "override"),
            ):
                wire.live_paths(wire.CHECKOUT, wire.SHARED / "env")
