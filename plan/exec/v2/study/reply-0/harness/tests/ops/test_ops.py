"""Offline operating checks. Pipe recordings in these tests get synthetic test envelopes."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import Mock, patch

from arci.gate import decide
from arci.schedule import build_schedule, spec_sha256
from arci.schema import Manifest, TrialEnvelope

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from harness import audit, clean_row, count_a, make_suites, wiring_check  # noqa: E402

Row = dict[str, Any]


def probe_reply(model: str) -> Row:
    return {"model": model, "done": True, "message": {"role": "assistant", "content": "OK"}}


def invalid_probe_replies(model: str) -> dict[str, bytes]:
    good = probe_reply(model)
    return {
        name: json.dumps(response).encode()
        for name, response in {
            "wrong model": probe_reply(wiring_check.MODELS["12B"]),
            "unfinished": {**good, "done": False},
            "non-boolean done": {**good, "done": 1},
            "missing message": {"model": model, "done": True},
            "wrong role": {**good, "message": {"role": "user"}},
        }.items()
    }


class Operations(unittest.TestCase):
    def test_inventory_and_cell_selection(self) -> None:
        slots = clean_row.slots(make_suites.register())
        self.assertEqual(sum(s.phase == "clean" for s in slots), 128)
        self.assertEqual(sum(s.phase == "unscripted" for s in slots), 48)
        self.assertEqual(len(set(slots)), len(slots))
        self.assertEqual(len(clean_row.select(slots, "reply0-clean-12B-F1")), 16)
        with self.assertRaises(ValueError):
            clean_row.select(slots, "reply0-clean-12B-F0")
        with self.assertRaises(ValueError):
            clean_row.select(slots, "../reply0-main-4B-F1")

    def test_push_guard_with_open_stdin(self) -> None:
        # This checkout may later be pushed. A disposable nonrepository never is.
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            sh = root / "harness/run-reply0.sh"
            sh.parent.mkdir()
            shutil.copyfile(ROOT / "harness/run-reply0.sh", sh)
            for run in ("reply0-wiring-4B", "reply0-clean-4B-F1-F1-n1"):
                p = subprocess.run(
                    ["sh", str(sh), "real", run],
                    input=b"caller input\n",
                    env={
                        **os.environ,
                        "REPLY0_ENV": str(audit.ENV),
                        "GIT_CEILING_DIRECTORIES": tmp,
                    },
                    capture_output=True,
                    timeout=10,
                )
                self.assertNotEqual(p.returncode, 0)
                self.assertIn(b"no matching pushed", p.stderr)
                self.assertFalse((root / ".reply0-ops").exists())

    def test_stdin_closed_for_descendant(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            env = Path(tmp)
            py = env / "py/bin/python"
            py.parent.mkdir(parents=True)
            py.write_text("#!/bin/sh\nexec /bin/cat\n")
            py.chmod(0o755)
            p = subprocess.run(
                ["sh", str(ROOT / "harness/run-reply0.sh"), "list"],
                input=b"caller data",
                capture_output=True,
                env={**os.environ, "REPLY0_ENV": tmp},
                check=True,
            )
            self.assertEqual(p.stdout, b"")

    def test_competition_and_interruption(self) -> None:
        s = clean_row.Slot("clean", "4B", "F1", "F1-n1")
        reg = wiring_check.Registration("1" * 40, "0.1", {}, wiring_check.digest(b"registered"))
        with TemporaryDirectory(dir=ROOT) as tmp, patch.object(clean_row, "OPS", Path(tmp)):

            def start(_: int) -> bool:
                try:
                    clean_row.claim(s, reg)
                    return True
                except FileExistsError:
                    return False

            with ThreadPoolExecutor(max_workers=8) as pool:
                self.assertEqual(sum(pool.map(start, range(16))), 1)
            # Simulate process disappearance with only the claim on disk.
            self.assertFalse(start(0))
            self.assertEqual(audit.read(Path(tmp) / s.id / "claim.json")["run"], s.id)

    def test_one_warmup_for_competing_verified_launches(self) -> None:
        from harness.offline_model import chat

        doc = make_suites.register()
        reg = wiring_check.Registration(
            "a" * 40, "1.0", {"4B": "b" * 64}, wiring_check.digest(b"registered")
        )
        with TemporaryDirectory(dir=ROOT) as tmp, ExitStack() as st:
            root = Path(tmp)
            plan = root / "plan.json"
            plan.write_text('{"wiring":{"script":"gives-up"}}')
            sent: list[bytes] = []

            def transport(i: int, body: bytes) -> tuple[int, bytes]:
                sent.append(body)
                return chat(plan, "wiring", i, body)

            st.enter_context(patch.object(clean_row, "ROOT", root))
            st.enter_context(patch.object(clean_row, "OPS", root / "ops"))
            st.enter_context(patch.object(clean_row, "deadline", return_value=datetime.max))
            st.enter_context(patch.object(wiring_check, "live_paths"))
            st.enter_context(patch.dict(os.environ, {"REPLY0_ENV": str(audit.ENV)}))
            st.enter_context(patch.object(wiring_check, "registration", return_value=reg))
            st.enter_context(patch.object(wiring_check, "versions"))
            st.enter_context(patch.object(wiring_check, "metadata"))
            st.enter_context(patch.object(audit, "fixture"))
            st.enter_context(patch.object(clean_row, "ollama_chat", side_effect=transport))
            slot = clean_row.Slot("wiring", "4B")

            def invoke(_: int) -> bool:
                try:
                    clean_row.execute(slot, doc, [slot])
                    return True
                except (ValueError, OSError):
                    return False

            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(sum(pool.map(invoke, range(2))), 1)
            self.assertFalse(invoke(3))
            self.assertEqual(len(sent), 3)
            self.assertEqual(
                json.loads(sent[0])["messages"], [{"role": "user", "content": "Reply with OK."}]
            )
            self.assertFalse(audit.read(root / "wiring.json")["4B"]["empty_fallback_null"])

    def test_wiring_records_and_refusal(self) -> None:
        sent: list[Row] = []
        saved: list[list[Row]] = []

        def transport(i: int, body: bytes) -> tuple[int, bytes]:
            sent.append(json.loads(body))
            if i:
                return 400, b"empty rejected"
            return 200, json.dumps(probe_reply(sent[-1]["model"])).encode()

        def save(rows: list[Row]) -> None:
            saved.append(deepcopy(rows))

        model = wiring_check.MODELS["4B"]
        rows = wiring_check.wiring(model, transport, save)
        self.assertTrue(wiring_check.fallback(rows, model))
        self.assertEqual([len(r) for r in saved], [1, 2])
        self.assertEqual([r["messages"][-1]["content"] for r in sent], ["violet", ""])
        self.assertEqual(base64.b64decode(rows[1]["response_b64"]), b"empty rejected")
        rows[0]["status"] = 500
        with self.assertRaises(ValueError):
            wiring_check.fallback(rows, model)

    def test_invalid_wiring_saves_response_and_holds(self) -> None:
        model = wiring_check.MODELS["4B"]
        good = json.dumps(probe_reply(model)).encode()
        for name, raw in invalid_probe_replies(model).items():
            for index in (0, 1):
                with self.subTest(name=name, index=index):
                    saved: list[list[Row]] = []
                    with self.assertRaisesRegex(ValueError, "invalid wiring response"):
                        wiring_check.wiring(
                            model,
                            Mock(side_effect=[(200, good)] * index + [(200, raw)]),
                            saved.append,
                        )
                    self.assertEqual(len(saved), index + 1)
                    failed = saved[-1][index]
                    self.assertEqual(failed["status"], 200)
                    self.assertFalse(failed["message"])
                    self.assertEqual(base64.b64decode(failed["response_b64"]), raw)

    def test_invalid_warmup_saves_response_and_holds(self) -> None:
        model = wiring_check.MODELS["4B"]
        with TemporaryDirectory(dir=ROOT) as tmp:
            for name, raw in invalid_probe_replies(model).items():
                with self.subTest(name=name):
                    path = Path(tmp) / name
                    with self.assertRaises(ValueError):
                        wiring_check.warm(model, Mock(return_value=(200, raw)), path)
                    self.assertEqual(path.read_bytes(), raw)

    def test_saved_wiring_rechecks_raw_model_tag(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp, patch.object(clean_row, "OPS", Path(tmp)):
            for key, model in wiring_check.MODELS.items():
                good = json.dumps(probe_reply(model)).encode()
                rows = wiring_check.wiring(model, Mock(return_value=(200, good)), lambda _: None)
                directory = Path(tmp) / f"reply0-wiring-{key}"
                directory.mkdir()
                make_suites.write_json(directory / "wiring.json", {"model": model, "checks": rows})
            self.assertIs(clean_row.wiring_state()["4B"]["empty_fallback_null"], False)
            path = Path(tmp) / "reply0-wiring-4B/wiring.json"
            attempt = audit.read(path)
            wrong = json.dumps(probe_reply(wiring_check.MODELS["12B"])).encode()
            attempt["checks"][1]["response_b64"] = base64.b64encode(wrong).decode()
            path.write_text(json.dumps(attempt))
            self.assertIsNone(clean_row.wiring_state(ready=False)["4B"]["empty_fallback_null"])
            with self.assertRaisesRegex(ValueError, "model differs"):
                clean_row.wiring_state()

    def test_publication_paths_and_digest_parser(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            (root / "source").write_bytes(b"data")
            (root / "alias").symlink_to(root / "source")
            for bad in ("../outside", "./source", str(root / "source"), "alias"):
                with self.assertRaises(ValueError):
                    wiring_check.safe_file(root, bad)
        pin = ("0" * 64 + "  file\n").encode()
        with self.assertRaises(ValueError):
            wiring_check.entries(pin + pin)
        clean_row.safe_bytes(b"/Users/Shared/arci-reply0/fx")
        with self.assertRaises(ValueError):
            clean_row.safe_bytes(
                json.dumps({"request_b64": base64.b64encode(b"/Users/example/a").decode()}).encode()
            )
        self.assertIn("checkers/feed_mcp_linter.py", wiring_check.required_inputs())

    def test_kept_sets_and_round_caps(self) -> None:
        doc = make_suites.register()
        slots = [s for s in clean_row.slots(doc) if s.phase == "clean"]
        lookup = {s.id: s for s in slots}
        sizes = {"C0": 8, "F1": 7, "F2": 6, "G1": 5, "G2": 4, "F0": 0}

        def counts(path: Path) -> Row:
            s = lookup[path.parent.name]
            parts = doc["cells"][s.cell]
            rows = (
                parts["main"] if s.task in {t["id"] for t in parts["main"]} else parts["held_out"]
            )
            index = [t["id"] for t in rows].index(s.task)
            keep = index < (sizes[s.cell] if rows is parts["main"] else 5)
            arms = {
                side: {
                    "by_task": {
                        s.task: {
                            "trials": 1,
                            "passed": int(keep and side == "candidate"),
                            "errored": int(side == "baseline"),
                        }
                    }
                }
                for side in clean_row.SIDES
            }
            return {
                "experiment_id": s.id,
                "phase": "clean",
                "cell": s.cell,
                "model": wiring_check.MODELS[s.model],
                "arms": arms,
            }

        with (
            patch.object(clean_row, "result", return_value={"seconds": 6, "counts_agree": True}),
            patch.object(audit, "read", side_effect=counts),
        ):
            kept = clean_row.clean_summary(doc, slots)
        self.assertEqual(
            [kept["4B"][c]["main"]["rounds"] for c in sizes], [15, 18, 20, 24, None, None]
        )
        self.assertEqual(kept["12B"]["F1"]["held_out"]["rounds"], 24)
        self.assertEqual(kept["4B"]["F1"]["main"]["seconds_per_trial"], 3)

    def test_digest_guard_rejects_omission_and_changed_bytes(self) -> None:
        from harness import wiring_check as w

        with TemporaryDirectory(dir=ROOT) as tmp, ExitStack() as st:
            base = Path(tmp)
            name = "fixture.py"
            (base / name).write_bytes(b"original")
            (base / w.REG).write_text(
                "Ollama: 1.2.3"
                + "".join("\n" + tag + ", sha256 " + ("1" * 64) for tag in w.MODELS.values())
            )
            pinned = {
                name: w.digest(b"original"),
                w.REG: audit.digest(base / w.REG),
                os.path.relpath(w.FX, base): audit.digest(w.FX),
            }
            st.enter_context(patch.object(w, "ROOT", base))
            st.enter_context(patch.object(w, "pinned_commit", return_value="a" * 40))
            st.enter_context(patch.object(w, "required_inputs", return_value={name, w.REG}))
            original = {n: (base / n).read_bytes() for n in (name, w.REG)}

            def pins(values: dict[str, str]) -> None:
                data = "".join(f"{v}  {n}\n" for n, v in values.items()).encode()
                (base / w.LIST).write_bytes(data)
                original[w.LIST] = data

            def committed(_commit: str, name: str) -> bytes:
                return original[name]

            st.enter_context(patch.object(w, "blob", side_effect=committed))
            pins(pinned)
            self.assertEqual(w.registration().version, "1.2.3")
            pins({n: v for n, v in pinned.items() if n != name})
            with self.assertRaisesRegex(ValueError, "omits"):
                w.registration()
            pins(pinned)
            (base / name).write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "differs from pushed"):
                w.registration()

    def test_conditional_order(self) -> None:
        doc = make_suites.register()
        kept = {
            model: {
                c: {part: {"kept": [t["id"] for t in rows[part]]} for part in ("main", "held_out")}
                for c, rows in doc["cells"].items()
            }
            for model in wiring_check.MODELS
        }
        slot = clean_row.Slot
        decisions: dict[clean_row.Slot, Row] = {}
        ok = {"valid": True, "statistical_block": True}
        miss = {"valid": True, "statistical_block": False}
        with patch.object(clean_row, "result", side_effect=decisions.get):
            with self.assertRaisesRegex(ValueError, "4B C0"):
                clean_row.suite_order(slot("main", "4B", "F1"), kept)
            decisions[slot("main", "4B", "C0")] = ok
            self.assertFalse(clean_row.suite_order(slot("main", "4B", "F1"), kept))
            decisions[slot("main", "4B", "F1")] = ok
            self.assertFalse(clean_row.suite_order(slot("confirmation", "4B", "F1"), kept))
            with self.assertRaises(ValueError):
                clean_row.suite_order(slot("confirmation", "12B", "F1"), kept)
            with self.assertRaises(ValueError):
                clean_row.suite_order(slot("main", "12B", "G1"), kept)
            decisions[slot("confirmation", "4B", "F1")] = miss
            self.assertFalse(clean_row.suite_order(slot("main", "12B", "G1"), kept))
            # With only four held-out tasks the second screen takes priority.
            kept["4B"]["F1"]["held_out"]["kept"] = ["a"] * 4
            self.assertFalse(clean_row.suite_order(slot("main", "12B", "F1"), kept))
            with self.assertRaisesRegex(ValueError, "12B F1 screen"):
                clean_row.suite_order(slot("main", "4B", "G1"), kept)


class PairFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        cls.root = Path(cls.stack.enter_context(TemporaryDirectory(dir=ROOT)))
        cls.stack.enter_context(
            patch.dict(os.environ, {"REPLY0_NO_SANDBOX": "1", "PYTHONDONTWRITEBYTECODE": "1"})
        )
        cls.checks = ROOT / "tasks/check"
        cls.doc = make_suites.register()

    def build_store(self, name: str, cell: str, phase: str = "main") -> Path:
        base = self.root / name
        base.mkdir()
        task = self.doc["cells"][cell]["held_out" if phase == "confirmation" else "main"][0]
        plans = []
        for script in ("corrected", "gives-up"):
            p = base / (script + ".json")
            p.write_text(
                audit.encoded(
                    {
                        task["key_id"]: {
                            "script": script,
                            "good": task["good"],
                            "expect": task["expect"],
                            "world_key": "order.total_cents" if cell == "C0" else None,
                        }
                    }
                )
            )
            plans.append(p)
        edited = None
        if phase == "confirmation":
            edited = base / "edited"
            audit.build(audit.ENV, edited, "F1")
        descriptor = make_suites.descriptor(
            self.doc,
            audit.ENV,
            audit.FX,
            cell,
            phase,
            "4B",
            [task],
            run=name,
            plain=True,
            plans=(plans[0], plans[1]),
            edited=edited,
        )
        path = base / "descriptor.yaml"
        path.write_text(json.dumps(descriptor))
        manifest = audit.compile_run_descriptor(path)
        assert isinstance(manifest, Manifest)
        receipts = base / "receipts"
        records = import_module("tasks.check_tasks").pipe_trials(
            descriptor,
            base,
            {**os.environ, "PYTHONPATH": str(ROOT / "harness"), "REPLY0_RECEIPTS": str(receipts)},
        )
        store = base / "store"
        store.mkdir()
        (store / "manifest.json").write_text(manifest.model_dump_json())
        trials = []
        for spec, row in zip(build_schedule(manifest), records, strict=True):
            frames = audit.lines(base / spec.arm / "boundary-frames.jsonl")
            events = [f["event"] for f in frames if f["kind"] == "event"]
            events.insert(
                0,
                {
                    "trial_id": spec.trial_id,
                    "kind": "trial_start",
                    "payload": {"arm": spec.arm, "seed": spec.seed, "variant": spec.variant},
                },
            )
            events.append({"trial_id": spec.trial_id, "kind": "trial_end", "payload": {}})
            for seq, event in enumerate(events):
                event["seq"] = seq
            ts = TrialEnvelope.create(
                experiment_id=name,
                trial_id=spec.trial_id,
                pair_id=spec.pair_id,
                task_id=spec.task_id,
                condition_id=cell,
                arm=spec.arm,
                variant=spec.variant,
                seed=spec.seed,
                spec_sha256=spec_sha256(spec),
                events=events,
                final_state=row["final_state"],
                recording=row["recording"],
                termination="completed",
                agent_claimed_success=True,
                usage={"tool_calls": sum(e["kind"] == "tool_start" for e in events)},
                outcome=row["outcome"],
                contract={"success": row["outcome"] == "PASS"},
            )
            trials.append(ts)
        self.seal(store, trials)
        return base

    def seal(self, store: Path, trials: list[TrialEnvelope]) -> None:
        manifest = Manifest.model_validate_json((store / "manifest.json").read_bytes())
        (store / "trials.jsonl").write_text(
            "".join(t.model_dump_json() + "\n" for t in reversed(trials))
        )
        (store / "events.jsonl").write_text(
            "".join(e.model_dump_json() + "\n" for t in trials for e in t.events)
        )
        (store / "decision.json").write_text(decide(manifest, trials).model_dump_json())

    def verify(self, base: Path) -> audit.Evidence:
        return audit.verify(
            base / "store", base / "receipts", self.checks, base / "descriptor.yaml"
        )


class PipeEvidence(PairFixture):
    def test_c0_injection_and_seeded_key(self) -> None:
        base = self.build_store("ops-c0", "C0")
        data = self.verify(base)
        self.assertEqual(
            count_a.count(data)["pairs"], {"plus": 0, "zero": 0, "minus": 1, "errored": 0}
        )
        ts = [TrialEnvelope.model_validate(r) for r in audit.lines(base / "store/trials.jsonl")]
        row = ts[0].model_dump(exclude={"record_sha256"})
        row["recording"][2]["result"]["injected_by"] = None
        self.seal(base / "store", [TrialEnvelope.create(**row), ts[1]])
        with self.assertRaisesRegex(ValueError, "sealed tool result"):
            self.verify(base)

    def test_round3_faults_reach_both_audit_and_count_a(self) -> None:
        from argparse import Namespace

        from harness import offline_model

        for fault in (
            "wrong opening",
            "wrong matching opening",
            "altered transport",
            "invented violation",
            "malformed terminal",
        ):
            with self.subTest(fault=fault):
                cell = "C0" if fault == "invented violation" else "F1"
                base = self.build_store("round3-" + fault.replace(" ", "-"), cell)
                store = base / "store"
                args = Namespace(
                    store=store,
                    receipts=base / "receipts",
                    check_dir=self.checks,
                    descriptor=base / "descriptor.yaml",
                    descriptor_sha256=None,
                    edited=None,
                )
                self.assertTrue(count_a.verified_count(args)["arms"])
                rows = [
                    TrialEnvelope.model_validate(t) for t in audit.lines(store / "trials.jsonl")
                ]
                side = "baseline" if cell == "C0" else "candidate"
                t = next(t for t in rows if t.arm == side)
                record = t.model_dump(exclude={"record_sha256"})
                path = next(p for p in args.receipts.iterdir() if audit.read(p)["arci_arm"] == side)
                receipt = audit.read(path)
                exchange = receipt["exchanges"][-1]
                raw = base64.b64decode(exchange["request_b64"])
                response = json.loads(base64.b64decode(exchange["response_b64"]))
                with ExitStack() as stack:
                    if fault in ("wrong opening", "wrong matching opening"):
                        bad: Row = {
                            "isError": True,
                            "content": [{"type": "text", "text": "permission denied"}],
                        }
                        if fault == "wrong matching opening":
                            bad["content"][0]["text"] = (
                                "ENOENT: no such file or directory, lstat '/wrong'"
                            )
                        stack.enter_context(
                            patch.object(audit.Reference, "query", return_value=bad)
                        )
                        first = next(
                            r for r in record["final_state"]["ledger"] if r["record"] == "call"
                        )
                        first.update(server_reply=bad, passed_on=bad)
                        self.seal(
                            store, [TrialEnvelope.create(**record) if x == t else x for x in rows]
                        )
                        reason = (
                            "registered fault absent"
                            if fault == "wrong opening"
                            else "exact registered opening"
                        )
                    elif fault == "invented violation":
                        record["contract"]["violations"] = [
                            {
                                "invariant": "forbidden_tools",
                                "severity": "hard",
                                "detail": "used lookup_order",
                            }
                        ]
                        record["outcome"] = "FAIL"
                        self.seal(
                            store, [TrialEnvelope.create(**record) if x == t else x for x in rows]
                        )
                        reason = "observed contract violations"
                    else:
                        if fault == "malformed terminal":
                            del response["message"]["content"]
                            reason = "malformed backend response"
                        else:
                            # Mutate after sender capture. Use the actual independent receiver.
                            changed = json.loads(raw)
                            changed["messages"][-1]["content"] += " changed in transport"
                            _, reply = offline_model.chat(
                                base / "gives-up.json",
                                receipt["key_id"],
                                0,
                                json.dumps(changed).encode(),
                            )
                            response = json.loads(reply)
                            reason = "stand-in receiver digest"
                        exchange["response_b64"] = base64.b64encode(
                            json.dumps(response).encode()
                        ).decode()
                        path.write_text(json.dumps(receipt))
                    with self.assertRaisesRegex(ValueError, reason):
                        self.verify(base)
                    with self.assertRaisesRegex(ValueError, reason):
                        count_a.verified_count(args)

    def test_unscripted_exposure(self) -> None:
        base = self.build_store("ops-unscripted", "F2", "unscripted")
        counts = count_a.count(self.verify(base))
        for side in clean_row.SIDES:
            group = counts["arms"][side]["all"]
            self.assertEqual(group["unscripted_trials"], 1)
            self.assertEqual(group["unscripted_exposed"], 0)
            self.assertEqual(group["same_tool"]["no"]["trials"], 0)

    def test_git_control_and_first_decisive_suite_round(self) -> None:
        # Preserve the actual G1 command traffic. Only IDs, scenario seeds and the
        # synthetic test envelopes are changed to exercise the released suite gate.
        base = self.build_store("ops-git", "G1")
        self.assertEqual(count_a.count(self.verify(base))["arms"]["baseline"]["all"]["passed"], 1)
        path = base / "descriptor.yaml"
        d = audit.read(path)
        run = d.pop("experiment_id")
        task_id = d.pop("task_id")
        task = d.pop("task")
        d.pop("n_per_arm")
        d.update(
            suite_id=run,
            tasks=[{"id": task_id, **task}],
            rule={
                "max_rounds": 120,
                "scenario_seeds": "per_round",
                "max_errored_pairs": 0,
                "alpha": "1/20",
                "delta": "1/10",
                "stakes": ["1/4", "1/2"],
            },
        )
        path.write_text(json.dumps(d))
        manifest = audit.compile_run_descriptor(path)
        self.assertIsInstance(manifest, audit.SuiteManifest)
        assert isinstance(manifest, audit.SuiteManifest)
        store = base / "store"
        receipts = base / "receipts"
        original = {r["arm"]: r for r in audit.lines(store / "trials.jsonl")}
        saved = {}
        for p in receipts.iterdir():
            r = audit.read(p)
            saved[r["arci_arm"]] = r
            p.unlink()
        trials = []
        for rd in range(1, manifest.max_rounds + 1):
            for spec in audit.build_suite_round(manifest, rd):
                r = deepcopy(original[spec.arm])
                r.pop("record_sha256")
                r.update(
                    experiment_id=manifest.experiment_id,
                    trial_id=spec.trial_id,
                    seed=spec.seed,
                    pair_id=spec.pair_id,
                    spec_sha256=spec_sha256(spec),
                )
                for e in r["events"]:
                    e["trial_id"] = spec.trial_id
                    if e["kind"] == "trial_start":
                        e["payload"]["seed"] = spec.seed
                trials.append(TrialEnvelope.create(**r))
                receipt = saved[spec.arm] | {"seed": spec.seed}
                filename = (
                    hashlib.sha256(
                        json.dumps(
                            [run, task["key_id"], spec.seed, spec.arm], separators=(",", ":")
                        ).encode()
                    ).hexdigest()
                    + ".json"
                )
                (receipts / filename).write_text(json.dumps(receipt))
            decision = import_module("arci.suite_gate").decide_suite(manifest, trials)
            if decision.verdict == "BLOCK":
                break
        (store / "manifest.json").write_text(manifest.model_dump_json())
        (store / "trials.jsonl").write_text("".join(t.model_dump_json() + "\n" for t in trials))
        (store / "events.jsonl").write_text(
            "".join(e.model_dump_json() + "\n" for t in trials for e in t.events)
        )
        (store / "decision.json").write_text(
            import_module("arci.suite_gate").decide_suite(manifest, trials).model_dump_json()
        )
        data = self.verify(base)
        self.assertIn("stored decision: MATCH", data.gate)
        self.assertEqual(data.verdict, "BLOCK")
        self.assertEqual(count_a.count(data)["pairs"]["minus"], len(data.history))

    def test_confirmation_identity(self) -> None:
        base = self.build_store("ops-confirmation", "F1", "confirmation")
        self.assertEqual(self.verify(base).phase, "confirmation")
        ts = [TrialEnvelope.model_validate(r) for r in audit.lines(base / "store/trials.jsonl")]
        row = ts[0].model_dump(exclude={"record_sha256"})
        start = next(r for r in row["final_state"]["ledger"] if r["record"] == "start")
        start["sha256"]["server.js"] = "0" * 64
        self.seal(base / "store", [TrialEnvelope.create(**row), ts[1]])
        with self.assertRaisesRegex(ValueError, "server launch"):
            self.verify(base)

    def test_count_and_independently_resealed_mutations(self) -> None:
        base = self.build_store("ops-f1", "F1")
        counts = count_a.count(self.verify(base))
        self.assertEqual(
            counts["arms"]["baseline"]["all"]["corrected_same_tool"]["yes"]["passed"], 1
        )
        store = base / "store"
        ts = [TrialEnvelope.model_validate(r) for r in audit.lines(store / "trials.jsonl")]
        for fault in (
            "omitted rewrite",
            "wrong candidate",
            "wrong flag",
            "missing ledger",
            "extra startup",
        ):
            with self.subTest(fault=fault):
                mutated = []
                for t in ts:
                    row = t.model_dump(exclude={"record_sha256"})
                    if t.arm == ("baseline" if fault == "omitted rewrite" else "candidate"):
                        led = row["final_state"]["ledger"]
                        call = next(r for r in led if r["record"] == "call")
                        if fault == "omitted rewrite":
                            call["passed_on"] = call["server_reply"]
                            call["rule"] = None
                        elif fault == "wrong candidate":
                            call["server_reply"]["content"][0]["text"] += " wrong path"
                            call["passed_on"] = deepcopy(call["server_reply"])
                            row["recording"][2]["result"]["value"] = deepcopy(call["passed_on"])
                            next(e for e in row["events"] if e["kind"] == "tool_finish")["payload"][
                                "value"
                            ] = deepcopy(call["passed_on"])
                        elif fault == "wrong flag":
                            call["server_reply"]["isError"] = False
                        elif fault == "missing ledger":
                            row["final_state"]["ledger"] = []
                        else:
                            led.append(deepcopy(led[0]))
                    mutated.append(TrialEnvelope.create(**row))
                self.seal(store, mutated)
                with self.assertRaises(ValueError):
                    self.verify(base)
        self.seal(store, ts[:1])
        with self.assertRaisesRegex(ValueError, "scheduled trial set"):
            self.verify(base)
        self.seal(store, ts)
        path = next((base / "receipts").glob("*.json"))
        receipt = audit.read(path)
        raw = path.read_bytes()
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            self.verify(base)
        path.write_bytes(raw)
        exchange = receipt["exchanges"][0]
        body = json.loads(base64.b64decode(exchange["request_b64"]))
        body["messages"][-1]["content"] = "wrong path"
        changed = audit.encoded(body).encode()
        exchange.update(
            request_b64=base64.b64encode(changed).decode(),
            sha256=hashlib.sha256(changed).hexdigest(),
        )
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "sent request"):
            self.verify(base)


if __name__ == "__main__":
    unittest.main()
