"""Planted faults over stand-in traffic, resealed evidence and launch boundaries."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from argparse import Namespace
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from harness import audit, count_a, count_b, make_suites, offline_model
from harness import clean_row as ops
from harness import wiring_check as wire
from harness.tests.ops.test_ops import ROOT, PairFixture

from arci import cli, runner
from arci.fingerprint import fingerprint
from arci.schema import TrialEnvelope

Row = dict[str, Any]


class Planted(PairFixture):
    def test_real_admission_hashes_built_package(self) -> None:
        doc = make_suites.register()
        s = ops.Slot("confirmation", "4B", "F1")
        previous = ops.Slot("clean", "4B", "F1", "F1-d1")
        kept = {
            "4B": {"F1": {"held_out": {"kept": [t["id"] for t in doc["cells"]["F1"]["held_out"]]}}}
        }
        reg = wire.Registration("a" * 40, "1.0", {}, wire.digest(b"registered"))
        wiring = {"4B": {"attempts": [{"registration": reg.commit}], "empty_fallback_null": False}}
        with TemporaryDirectory(dir=ROOT) as tmp, ExitStack() as st:
            root = Path(tmp)
            env = root / "env"
            env.mkdir()
            (env / "node").symlink_to(audit.ENV / "node")
            build = audit.build(env, env / "edited", "F1")
            st.enter_context(
                patch.multiple(
                    ops, ROOT=root, OPS=root / "claims", RUNS=root / "runs", KEPT=root / "kept.json"
                )
            )
            st.enter_context(patch.object(audit, "ENV", env))
            st.enter_context(patch.object(ops, "wiring_state", return_value=wiring))
            st.enter_context(patch.object(ops, "clean_summary", return_value=kept))
            st.enter_context(patch.object(ops, "deadline", return_value=datetime.max))
            st.enter_context(patch.object(ops, "suite_order", return_value=False))
            st.enter_context(patch.object(wire, "metadata"))
            st.enter_context(
                patch.object(wire, "git", return_value=str(int(time.time()) + 1).encode())
            )
            # Synthetic checkout lies inside a personal worktree. Privacy has its own test.
            st.enter_context(patch.object(ops, "safe_bytes"))
            folder = ops.OPS / previous.id
            folder.mkdir(parents=True)
            (folder / "finished.json").touch()
            (root / wire.NOTE).write_bytes(b"test note")
            make_suites.write_json(root / "wiring.json", wiring)
            make_suites.write_json(ops.KEPT, kept)
            path = ops.RUNS / s.id / "descriptor.yaml"
            make_suites.write_json(path, ops.config(s, doc, kept, False))
            pins = {str(path.relative_to(root)): audit.digest(path)}
            st.enter_context(patch.object(wire, "descriptor_note", return_value=("b" * 40, pins)))
            directory, evidence = ops.admission(s, reg, doc, [s, previous])
            self.assertEqual(directory, ops.OPS / s.id)
            self.assertEqual(evidence["descriptor"], audit.digest(path))
            (build / "package/dist/server.js").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "edited package"):
                ops.admission(s, reg, doc, [s, previous])

    def check_pair(self, base: Path, reasons: tuple[str, str] | None = None) -> Row:
        args = Namespace(
            store=base / "store",
            receipts=base / "receipts",
            check_dir=self.checks,
            descriptor=base / "descriptor.yaml",
            descriptor_sha256=None,
            edited=None,
        )
        checks = {
            "audit": lambda: self.verify(base),
            "count A": lambda: count_a.verified_count(args),
            "count B": lambda: count_b.verified_count(
                args.store, args.receipts, self.checks, args.descriptor, publication=True
            )[0],
        }
        results: Row = {}
        for name, verify in checks.items():
            with self.subTest(verifier=name):
                if reasons is None:
                    results[name] = verify()
                else:
                    with self.assertRaisesRegex(ValueError, reasons[name == "count B"]):
                        verify()
        if reasons is None:
            self.assertEqual(results["count A"], results["count B"])
            self.assertTrue(audit.summary(results["audit"])["valid"])
        return results

    def publish(self, base: Path) -> None:
        store = base / "store"
        ledgers = [
            {"trial_id": t["trial_id"], "ledger": t["final_state"]["ledger"]}
            for t in audit.lines(store / "trials.jsonl")
        ]
        receipts = [audit.read(p) for p in (base / "receipts").iterdir()]
        for name, rows in (("ledger", ledgers), ("receipts", receipts)):
            (store / f"{name}.jsonl").write_text("".join(audit.encoded(r) + "\n" for r in rows))

    def test_common_wrong_f1_failure(self) -> None:
        base = self.build_store("planted-opening", "F1")
        self.publish(base)
        self.check_pair(base)
        store = base / "store"
        trials = []
        bad_text = "EACCES: permission denied"
        bad: Row = {"isError": True, "content": [{"type": "text", "text": bad_text}]}
        for row in audit.lines(store / "trials.jsonl"):
            first = next(r for r in row["final_state"]["ledger"] if r["record"] == "call")
            first.update(server_reply=bad, passed_on=bad, rule=None)
            record = next(r for r in row["recording"] if not r["tool"].startswith("rpc:"))
            record["result"]["value"] = bad
            finish = next(
                e
                for e in row["events"]
                if e["kind"] == "tool_finish"
                and e["payload"]["call_id"] == record["result"]["call_id"]
            )
            finish["payload"]["value"] = bad
            row.pop("record_sha256")
            trials.append(TrialEnvelope.create(**row))
        self.seal(store, trials)
        for path in (base / "receipts").iterdir():
            receipt = audit.read(path)
            script = "corrected" if receipt["arci_arm"] == "baseline" else "gives-up"
            for step, ex in enumerate(receipt["exchanges"]):
                request = json.loads(base64.b64decode(ex["request_b64"]))
                request["messages"][3]["content"] = bad_text
                body = json.dumps(request, ensure_ascii=False).encode()
                _, response = offline_model.chat(
                    base / (script + ".json"), receipt["key_id"], step, body
                )
                ex.update(
                    request_b64=base64.b64encode(body).decode(),
                    sha256=hashlib.sha256(body).hexdigest(),
                    response_b64=base64.b64encode(response).decode(),
                )
            path.write_text(json.dumps(receipt))
        self.publish(base)
        with (
            patch.object(audit.Reference, "query", return_value=bad),
            patch.object(count_b.Reference, "original", return_value=bad),
        ):
            self.check_pair(base, ("registered fault absent", "registered fault predicate absent"))

    def test_transport_and_malformed_backend(self) -> None:
        for mutation, reasons in (
            ("transport", ("stand-in receiver digest", "receiver response digest")),
            ("malformed", ("malformed backend response", "missing string content")),
        ):
            with self.subTest(mutation=mutation):
                base = self.build_store("planted-" + mutation, "F1")
                self.publish(base)
                self.check_pair(base)
                path = next(
                    p
                    for p in (base / "receipts").iterdir()
                    if audit.read(p)["arci_arm"] == "candidate"
                )
                receipt = audit.read(path)
                (exchange,) = receipt["exchanges"]
                if mutation == "transport":
                    request = json.loads(base64.b64decode(exchange["request_b64"]))
                    request["messages"][-1]["content"] += " changed after sender capture"
                    _, response = offline_model.chat(
                        base / "gives-up.json", receipt["key_id"], 0, json.dumps(request).encode()
                    )
                else:
                    response_obj = json.loads(base64.b64decode(exchange["response_b64"]))
                    del response_obj["message"]["content"]
                    response = json.dumps(response_obj).encode()
                    self.assertEqual(
                        next(
                            t["outcome"]
                            for t in audit.lines(base / "store/trials.jsonl")
                            if t["arm"] == "candidate"
                        ),
                        "FAIL",
                    )
                exchange["response_b64"] = base64.b64encode(response).decode()
                path.write_text(json.dumps(receipt))
                self.publish(base)
                self.check_pair(base, reasons)

    def test_invented_c0_violation(self) -> None:
        base = self.build_store("planted-contract", "C0")
        self.publish(base)
        self.check_pair(base)
        store = base / "store"
        rows = audit.lines(store / "trials.jsonl")
        row = next(r for r in rows if r["arm"] == "baseline")
        state = row["final_state"]
        self.assertEqual(state["answer"], str(state["world"]["order"]["total_cents"]))
        self.assertEqual((row["outcome"], row["contract"]["violations"]), ("PASS", []))
        row.update(outcome="FAIL")
        row["contract"]["violations"].append(
            {"invariant": "forbidden_tools", "severity": "hard", "detail": "used lookup_order"}
        )
        self.seal(
            store,
            [
                TrialEnvelope.create(**{k: v for k, v in r.items() if k != "record_sha256"})
                for r in rows
            ],
        )
        self.check_pair(base, ("observed contract violations", "violation"))

    def test_corrupt_published_evidence(self) -> None:
        base = self.build_store("planted-exports", "F1")
        for name, reason in (("ledger", "exported ledgers"), ("receipts", "exported receipts")):
            with self.subTest(export=name):
                self.publish(base)
                self.check_pair(base)
                path = base / "store" / f"{name}.jsonl"
                records = audit.lines(path)
                if name == "ledger":
                    records[0]["ledger"][0]["arm"] = "changed"
                else:
                    records[0]["exchanges"][0]["sha256"] = "0" * 64
                path.write_text("".join(audit.encoded(r) + "\n" for r in records))
                self.check_pair(base, (reason, f"aggregate {name}.jsonl"))

    def test_completed_f1_relabelled_error_or_timeout(self) -> None:
        base = self.build_store("planted-termination", "F1")
        self.publish(base)
        self.check_pair(base)
        store = base / "store"
        rows = audit.lines(store / "trials.jsonl")
        row = next(t for t in rows if t["arm"] == "baseline")
        expected = self.doc["cells"]["F1"]["main"][0]["expect"]
        self.assertEqual([row["final_state"]["answer"]], expected)
        self.assertEqual((row["termination"], row["outcome"]), ("completed", "PASS"))
        for term, outcome, detail, kind, reasons in (
            (
                "harness_error",
                "ERROR",
                "worker harness failed",
                "harness",
                ("unsupported late infrastructure", "contradicts claimed infrastructure"),
            ),
            (
                "timeout",
                "FAIL",
                "trial exceeded max_seconds",
                "timeout",
                ("timeout contradicts", "timeout before wall budget"),
            ),
        ):
            with self.subTest(termination=term):
                row.update(
                    termination=term,
                    outcome=outcome,
                    failure_detail=detail,
                    failure_fingerprint=fingerprint(kind, detail),
                    contract={"success": False},
                )
                self.seal_rows(store, rows)
                self.check_pair(base, reasons)

    def seal_rows(self, store: Path, rows: list[Row]) -> None:
        self.seal(
            store,
            [
                TrialEnvelope.create(**{k: v for k, v in row.items() if k != "record_sha256"})
                for row in rows
            ],
        )

    def test_changed_model_and_unfinished_response(self) -> None:
        base = self.build_store("planted-response", "F1")
        self.publish(base)
        self.check_pair(base)
        path = next(
            p for p in (base / "receipts").iterdir() if audit.read(p)["arci_arm"] == "baseline"
        )
        receipt = audit.read(path)
        exchange = receipt["exchanges"][-1]
        payload = json.loads(base64.b64decode(exchange["response_b64"], validate=True))
        for change, reasons in (
            ({"model": "different-model"}, ("response model", "response model")),
            ({"done": False}, ("response unfinished", "response done")),
        ):
            with self.subTest(change=change):
                exchange["response_b64"] = base64.b64encode(
                    json.dumps(payload | change).encode()
                ).decode()
                path.write_text(json.dumps(receipt))
                self.publish(base)
                self.check_pair(base, reasons)

    def test_timeout_with_pending_call_and_later_malformed_response(self) -> None:
        # Collect 20 real stand-in pairs so a single planted timeout also passes R3.
        template = self.build_store("planted-prefix-template", "F1")
        base = self.root / "planted-prefix"
        base.mkdir()
        config = audit.read(template / "descriptor.yaml") | {
            "n_per_arm": 20,
            "experiment_id": base.name,
        }
        for side in ops.SIDES:
            argv = config[side]["command"]["argv"]
            argv[argv.index("--run-id") + 1] = base.name
        descriptor = base / "descriptor.yaml"
        make_suites.write_json(descriptor, config)
        run = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "harness/tests/core/offline_run.py"),
                str(descriptor),
                str(base / "stores"),
            ],
            env=os.environ
            | {
                "TMPDIR": str(base),
                "REPLY0_RECEIPTS": str(base / "receipts"),
                "PYTHONPATH": os.pathsep.join((str(ROOT / "harness"), str(ROOT))),
            },
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=180,
        )
        self.assertEqual(run.returncode, 1, run.stderr.decode())
        store = base / "store"
        (base / "stores" / base.name).rename(store)
        self.publish(base)
        control = self.check_pair(base)
        self.assertEqual(control["count A"]["pairs"]["minus"], 20)
        original = audit.lines(store / "trials.jsonl")
        idx = next(i for i, t in enumerate(original) if t["arm"] == "baseline")
        path = next(
            p
            for p in (base / "receipts").iterdir()
            if (r := audit.read(p))["arci_arm"] == "baseline" and r["seed"] == original[idx]["seed"]
        )
        raw_receipt = path.read_bytes()
        for term, outcome, pair in (
            ("timeout", "FAIL", "zero"),
            ("harness_error", "ERROR", "errored"),
        ):
            with self.subTest(termination=term):
                rows = deepcopy(original)
                trial = rows[idx]
                receipt = json.loads(raw_receipt)
                state = trial["final_state"]
                state.update(answer=None, answer_present=False)
                receipt.update(complete=False, answer=None)
                trial.update(
                    termination=term,
                    outcome=outcome,
                    agent_claimed_success=False,
                    contract={"success": False},
                )
                if term == "timeout":
                    detail = "trial exceeded max_seconds"
                    trial["usage"]["wall_seconds"] = 120.05
                    # Stop after the model asked for the corrected read and the boundary started it.
                    finish = trial["events"].pop(-2)
                    start = trial["events"][-2]
                    self.assertEqual((start["kind"], finish["kind"]), ("tool_start", "tool_finish"))
                    self.assertEqual(start["payload"]["call_id"], finish["payload"]["call_id"])
                    trial["incomplete_calls"] = [start["payload"]]
                    trial["events"][-1]["seq"] -= 1
                    self.assertEqual(
                        trial["recording"].pop()["result"]["call_id"], start["payload"]["call_id"]
                    )
                    self.assertEqual(state["ledger"].pop()["tool"], start["payload"]["tool"])
                    receipt["exchanges"].pop()
                    receipt["steps"] -= 1
                    self.assertEqual(
                        receipt["calls"].pop()["arguments"], start["payload"]["arguments"]
                    )
                else:
                    detail = "agent reported an infrastructure failure (exit <n>)"
                    exchange = receipt["exchanges"][-1]
                    self.assertGreater(len(receipt["exchanges"]), 1)
                    payload = json.loads(base64.b64decode(exchange["response_b64"], validate=True))
                    payload["message"] = {"role": "assistant", "tool_calls": "malformed"}
                    exchange["response_b64"] = base64.b64encode(
                        json.dumps(payload).encode()
                    ).decode()
                trial.update(
                    failure_detail=detail,
                    failure_fingerprint=fingerprint(
                        "timeout" if term == "timeout" else "harness", detail
                    ),
                )
                path.write_text(json.dumps(receipt))
                self.seal_rows(store, rows)
                self.publish(base)
                checks = self.check_pair(base)
                observed = next(
                    o.trial
                    for o in checks["audit"].observations
                    if o.trial.trial_id == trial["trial_id"]
                )
                self.assertEqual((observed.termination, observed.outcome), (term, outcome))
                counts = checks["count A"]
                self.assertEqual(
                    counts["pairs"],
                    dict.fromkeys(("plus", "zero", "errored"), 0) | {"minus": 19, pair: 1},
                )
                self.assertEqual(
                    counts["arms"]["baseline"]["all"]["by_termination"], {"completed": 19, term: 1}
                )

    def test_changed_receipts_after_finish_abort_assembly(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            slot = ops.Slot("main", "4B", "F1")
            directory = root / "claims" / slot.id
            folder = root / "runs" / slot.id
            directory.mkdir(parents=True)
            folder.mkdir(parents=True)
            (root / "result.md").write_text("result")
            (directory / "claim.json").write_text("{}")
            for name in ops.EXPORTS:
                (folder / name).write_text("{}\n")
            make_suites.write_json(
                directory / "finished.json",
                {"hashes": {name: audit.digest(folder / name) for name in ops.EXPORTS}},
            )
            with (
                patch.multiple(ops, ROOT=root, OPS=directory.parent, RUNS=folder.parent),
                patch.object(wire, "fixed_public", return_value=set()),
            ):
                ops.assemble(root / "control", [slot])
                receipts = folder / "receipts.jsonl"
                receipts.write_text('{"changed":true}\n')
                with self.assertRaisesRegex(ValueError, "staged receipts.jsonl"):
                    ops.assemble(root / "changed", [slot])
                self.assertFalse((root / "changed").exists())

    def test_resource_blob_and_utf16_export_rejected(self) -> None:
        personal = "/Users/" + "synthetic-login/private"
        blob = {
            "resource": {
                "mimeType": "text/plain",
                "blob": base64.b64encode(personal.encode()).decode(),
            }
        }
        with self.assertRaisesRegex(ValueError, "personal identifier or path"):
            ops.safe_bytes(json.dumps(blob).encode())
        with self.assertRaises(UnicodeDecodeError):
            ops.safe_bytes(personal.encode("utf-16"))

    def test_claimless_warmup_opens_no_connection(self) -> None:
        token = wire.PROBE.set(None)
        self.addCleanup(wire.PROBE.reset, token)
        with (
            patch.object(wire, "local_opener") as opener,
            patch("socket.socket.connect") as connect,
        ):
            with self.assertRaisesRegex(ValueError, "requires active suite admission"):
                wire.warm(wire.MODELS["4B"], wire.probe_chat)
            opener.return_value.open.assert_not_called()
            connect.assert_not_called()

    def test_live_f1_descriptor_admission_privacy(self) -> None:
        slot = ops.Slot("clean", "4B", "F1", "F1-n1")
        reg = wire.Registration("a" * 40, "1", {}, wire.digest(b"registered"))
        wiring = {"4B": {"attempts": [{"registration": reg.commit}], "empty_fallback_null": False}}
        env = wire.SHARED / "env"
        study = wire.CHECKOUT / "plan/exec/v2/study/reply-0"
        with TemporaryDirectory(dir=ROOT) as tmp, ExitStack() as st:
            root = Path(tmp)
            claims = root / "claims"
            claims.mkdir()
            make_suites.write_json(root / "wiring.json", wiring)
            st.enter_context(patch.multiple(ops, ROOT=root, OPS=claims, RUNS=root / "runs"))
            st.enter_context(patch.object(ops, "deadline", return_value=datetime.max))
            st.enter_context(patch.object(ops, "wiring_state", return_value=wiring))
            st.enter_context(patch.dict(os.environ, {"PATH": "/unusable", "REPLY0_ENV": str(env)}))
            st.enter_context(patch.object(audit, "ENV", Path(os.environ["REPLY0_ENV"])))
            st.enter_context(patch.object(make_suites, "HERE", study / "harness"))
            wire.live_paths(study, env)
            directory, evidence = ops.admission(slot, reg, self.doc, [slot])
            descriptor = ops.RUNS / slot.id / "descriptor.yaml"
            self.assertTrue((directory / "claim.json").is_file())
            self.assertEqual(audit.digest(descriptor), evidence["descriptor"])
            config = audit.read(descriptor)
            argv = config["mcp_server"]["argv"]
            self.assertEqual(argv[argv.index("--") + 1], str(env / "node/bin/node"))
            self.assertTrue(
                all("--offline" not in config[side]["command"]["argv"] for side in ops.SIDES)
            )

    def test_direct_live_descriptor_without_claim(self) -> None:
        # Use the released run entry point and both real generated arm commands. The
        # test boundary announces readiness without binding a socket. A socket-free
        # HTTP endpoint and MCP launch sentinel record any attempt by either child.
        root = self.root / "direct"
        root.mkdir()
        slot = ops.Slot("clean", "4B", "F1", "F1-n1")
        descriptor = root / "descriptor.yaml"
        config = ops.config(slot, self.doc, {}, False)
        self.assertTrue(all("--offline" not in config[s]["command"]["argv"] for s in ops.SIDES))
        make_suites.write_json(descriptor, config)
        (root / "sitecustomize.py").write_text(
            "import atexit, http.client, os, pathlib, sys\n"
            "if sys.argv[0].endswith('/agent.py'):\n"
            "    root = pathlib.Path(os.environ['PLANTED_TEST_DIR'])\n"
            "    def endpoint(*args, **kwargs):\n"
            "        (root / 'request').touch()\n"
            "        raise OSError('stand-in endpoint')\n"
            "    http.client.HTTPConnection = endpoint\n"
            "    (root / os.environ['REPLY0_ARCI_ARM']).touch()\n"
            "    def observe(event, args):\n"
            "        if event in ('subprocess.Popen', 'socket.connect'):\n"
            "            endpoint()\n"
            "    sys.addaudithook(observe)\n"
            "    atexit.register(pathlib.Path('agent-finished').touch)\n"
        )
        boundary = """
import json
import sys
import time
from pathlib import Path

config = json.load(sys.stdin)
print(json.dumps({"kind": "ready", "nonce": config["nonce"]}), flush=True)
finished = Path(config["workdir"]) / "agent-finished"
for attempt in range(500):
    if finished.exists():
        break
    time.sleep(0.01)
"""
        stderr = root / "agent.log"

        def launch(argv: list[str], **kwargs: Any) -> subprocess.Popen[Any]:
            if argv == [sys.executable, "-P", "-m", "arci.mcp_boundary"]:
                argv = [sys.executable, "-B", "-c", boundary]
            elif str(ROOT / "harness/agent.py") in argv:
                kwargs["env"]["PYTHONPATH"] = str(root) + os.pathsep + kwargs["env"]["PYTHONPATH"]
                with stderr.open("ab") as stream:
                    kwargs["stderr"] = stream
                    return subprocess.Popen(argv, **kwargs)
            return subprocess.Popen(argv, **kwargs)

        def workdir(*, prefix: str, dir: str) -> str:
            return tempfile.mkdtemp(prefix=prefix, dir=root)

        with (
            patch.dict(os.environ, {"PLANTED_TEST_DIR": str(root)}),
            patch.object(
                runner, "subprocess", SimpleNamespace(**(vars(subprocess) | {"Popen": launch}))
            ),
            patch.object(runner, "tempfile", SimpleNamespace(mkdtemp=workdir)),
            (root / "cli.log").open("w") as log,
            redirect_stdout(log),
            redirect_stderr(log),
        ):
            for key in ("REPLY0_LAUNCH_TOKEN", "REPLY0_CLAIMS", "REPLY0_RECEIPTS"):
                os.environ.pop(key, None)
            self.assertEqual(
                cli.main(["run", str(descriptor), "--out", str(root / "stores"), "--workers", "1"]),
                3,
            )
        self.assertEqual(stderr.read_text().splitlines(), ["live trial admission failed"] * 2)
        for side in ops.SIDES:
            self.assertTrue((root / side).is_file())
        self.assertFalse((root / "request").exists())
