"""Hand-built evidence, with only the released constructors used for schedules and seals."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import create_autospec, patch

import count_b as counter
from pydantic import JsonValue

from arci.descriptor import compile_run_descriptor
from arci.fingerprint import fingerprint
from arci.gate import decide
from arci.hashing import hash_record
from arci.schedule import build_schedule, spec_sha256
from arci.schema import ContractSpec, Event, GateDecision, TrialEnvelope, TrialSpec
from arci.suite_gate import decide_suite
from arci.suite_schedule import build_suite_round
from arci.suite_schema import SuiteManifest

Obj = dict[str, JsonValue]
ROOT = Path(__file__).resolve().parents[3]
MODEL = "qwen3.5:4b-mlx-ctx32k"
RUN = "blind-count"
TASK = "F2-n1"
ASK = (
    "A file somewhere under /Users/Shared/arci-reply0/fx/files answers this question: "
    "What is the second item on the to-do list? Reply with the answer only."
)
ANSWER = "Renew the fire certificate before 30 April"
SYSTEM = (
    "You answer questions by using the tools you are given. Call a tool when you need "
    "information. Never invent a tool result. When you know the answer, reply with "
    "the answer only."
)
FOLDER = "/Users/Shared/arci-reply0/fx/files"
SERVER = ["/pinned/node", "/pinned/dist/index.js", FOLDER]
SHIPPED = "No matches found"
NAMING = (
    'No entry matched the pattern "todo". A pattern with no wildcard matches only an '
    "entry whose path below the given path is exactly that text. Call search_files "
    'again with the same path and the pattern "**/*todo*".'
)
TOOLS: list[Obj] = [
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Find paths",
            "parameters": {"type": "object"},
        },
    }
]
IDENTITY: Obj = {
    "protocolVersion": "2025-11-25",
    "serverInfo": {"name": "filesystem", "version": "test"},
}
HASHES = {
    k: hashlib.sha256(k.encode()).hexdigest() for k in ("executable", "index.js", "server.js")
}


def call(pattern: str) -> Obj:
    return {"name": "search_files", "arguments": {"path": FOLDER, "pattern": pattern}}


def raw(text: str) -> Obj:
    return {"content": [{"type": "text", "text": text}], "structuredContent": {"content": text}}


class StaticReference:
    """Fixture-side facts. Neither side's observed replies feed this reference."""

    tools = TOOLS
    identity = IDENTITY
    digests = HASHES

    def __init__(self, stack: ExitStack, reg: counter.Registration, spec: TrialSpec):
        pass

    def original(self, query: Obj) -> Obj:
        if query == call("todo"):
            return raw(SHIPPED)
        if query == call("**/*todo*"):
            return raw(FOLDER + "/notes/todo.txt")
        raise AssertionError(query)


def write(path: Path, value: object) -> None:
    _ = path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def write_lines(path: Path, values: list[Obj]) -> None:
    _ = path.write_text("".join(json.dumps(v) + "\n" for v in values), encoding="utf-8")


def arm(side: str, label: str, opening: str) -> Obj:
    return {
        "label": label,
        "command": {
            "argv": [
                "python",
                "agent.py",
                "--offline",
                "hand-made-plan.json",
                "--mcp-config",
                "{mcp_config}",
                "--task-file",
                "{task_file}",
                "--arm",
                label,
                "--opening",
                opening,
                "--model",
                MODEL,
                "--prompt",
                SYSTEM,
                "--run-id",
                RUN,
            ],
            "env": {"REPLY0_ARCI_ARM": side},
        },
    }


class Evidence:
    def __init__(
        self,
        root: Path,
        *,
        suite: bool = False,
        opening: str = "bad",
        fault: str = "",
        live: bool = False,
    ):
        self.study = root / "study"
        (self.study / "tasks").mkdir(parents=True)
        (self.study / "tasks/tasks.json").write_bytes((ROOT / "tasks/tasks.json").read_bytes())
        self.store = root / "store"
        self.receipts = root / "receipts"
        self.check = root / "check"
        for path in (self.store, self.receipts, self.check):
            path.mkdir()
        self.transcript(
            [{"id": TASK, "cell": "F2", "bad_call": call("todo"), "original_result": raw(SHIPPED)}]
        )
        task: Obj = {
            "key_id": TASK,
            "cell": "F2",
            "ask": ASK,
            "bad": call("todo"),
            "clean": call("**/*todo*"),
        }
        labels = ("clean", "clean") if opening != "bad" else ("naming-sentence", "reply-as-given")
        fields: Obj = {
            "conditions": [{"condition_id": "F2"}],
            "contract": {"oracle": "example:oracle"},
            "mcp_server": {
                "argv": ["relay.py", "--ledger", "--", *SERVER],
                "snapshot": "example:snapshot",
            },
            "baseline": arm("baseline", labels[0], opening),
            "candidate": arm("candidate", labels[1], opening),
            "budgets": {"max_tool_calls": 12, "max_seconds": 120.0},
        }
        if suite:
            fields.update(
                {
                    "suite_id": RUN,
                    "tasks": [{"id": TASK, **task}],
                    "rule": {
                        "max_rounds": 120,
                        "scenario_seeds": "per_round",
                        "max_errored_pairs": 4,
                    },
                }
            )
        else:
            fields.update({"experiment_id": RUN, "task_id": TASK, "task": task, "n_per_arm": 1})
        if live:
            for side in ("baseline", "candidate"):
                command = counter.obj(counter.obj(fields[side])["command"])
                argv = counter.array(command["argv"])
                start = argv.index("--offline")
                del argv[start : start + 2]
        descriptor = self.store / "descriptor.yaml"
        write(descriptor, fields)
        self.manifest = compile_run_descriptor(descriptor)
        if isinstance(self.manifest, SuiteManifest):
            specs = [s for i in range(1, 14) for s in build_suite_round(self.manifest, i)]
        else:
            specs = list(build_schedule(self.manifest))
        write(self.store / "manifest.json", self.manifest.model_dump(mode="json"))
        self.trials = [
            self.make_trial(
                s, opening, fault if s.arm == "candidate" or fault == "changed opening" else ""
            )
            for s in specs
        ]
        self.save()

    def transcript(self, records: list[Obj]) -> None:
        path = self.check / "tasks.check.json"
        write(path, records)
        pin = hashlib.sha256(path.read_bytes()).hexdigest()
        _ = (self.study / "reply0-digests.sha256").write_text(
            f"{pin}  tasks/check/tasks.check.json\n"
        )

    def publish(self) -> None:
        write_lines(
            self.store / "ledger.jsonl",
            [
                {"trial_id": t.trial_id, "ledger": counter.obj(t.final_state)["ledger"]}
                for t in reversed(self.trials)
            ],
        )
        write_lines(
            self.store / "receipts.jsonl", [counter.read(p) for p in self.receipts.iterdir()]
        )

    def make_trial(self, spec: TrialSpec, opening: str, fault: str) -> TrialEnvelope:
        arm_label = spec.variant
        rules = "naming" if arm_label == "naming-sentence" else "none"
        ledger: list[Obj] = [
            {"record": "arm", "arm": arm_label, "rules": rules, "server": "shipped"},
            {"record": "task", "key_id": TASK},
            {
                "record": "start",
                "argv": list(SERVER),
                "module_root": None,
                "sha256": dict(HASHES),
                **IDENTITY,
            },
        ]
        history: list[Obj] = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": ASK},
        ]
        events: list[Event] = []
        records: list[Obj] = []
        incomplete: list[Obj] = []
        calls: list[Obj] = []
        exchanges: list[Obj] = []

        def send(message: Obj) -> None:
            payload = {
                "model": MODEL,
                "messages": history,
                "tools": TOOLS,
                "stream": False,
                "think": False,
                "options": {"temperature": 0.7},
            }
            data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
            response_fields: Obj = {"model": MODEL, "done": True, "message": message}
            if spec.command and "--offline" in spec.command.argv:
                response_fields["received_sha256"] = counter.digest(data)
            response = json.dumps(response_fields).encode()
            exchanges.append(
                {
                    "request_b64": base64.b64encode(data).decode(),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "receiver_sha256": hashlib.sha256(data).hexdigest(),
                    "status": 200,
                    "response_b64": base64.b64encode(response).decode(),
                }
            )
            history.append(message)

        def invoke(query: Obj) -> None:
            i = len(calls)
            cid = f"call-{i}"
            wrong = fault in ("wrong original", "changed opening")
            original = (
                ("Not what the server said" if wrong else SHIPPED)
                if query == call("todo")
                else FOLDER + "/notes/todo.txt"
            )
            match = rules == "naming" and query == call("todo") and original == SHIPPED
            text = NAMING if match else original
            delivered: Obj = {"isError": False, **raw(text)}
            ledger.append(
                {
                    "record": "call",
                    "seq": i,
                    "tool": "search_files",
                    "arguments": query["arguments"],
                    "server_reply": raw(original),
                    "passed_on": delivered,
                    "rule": "naming:0" if match else None,
                }
            )
            args: Obj = {
                "path": FOLDER,
                "pattern": "todo" if query == call("todo") else "**/*todo*",
            }
            start: Obj = {
                "call_id": cid,
                "tool": "search_files",
                "arguments": args,
                "occurrence": i,
            }
            finish: Obj = {
                "call_id": cid,
                "tool": "search_files",
                "ok": True,
                "value": delivered,
                "error_kind": None,
                "injected_by": None,
            }
            events.extend(
                [
                    Event(trial_id=spec.trial_id, seq=2 * i, kind="tool_start", payload=start),
                    Event(
                        trial_id=spec.trial_id, seq=2 * i + 1, kind="tool_finish", payload=finish
                    ),
                ]
            )
            records.append(
                {
                    "tool": "search_files",
                    "occurrence": i,
                    "arguments_sha256": hash_record(args),
                    "result": finish,
                }
            )
            calls.append(query)
            history.append({"role": "tool", "tool_name": "search_files", "content": text})

        if opening != "none":
            first = call("todo" if opening == "bad" else "**/*todo*")
            history.append(
                {"role": "assistant", "content": "", "tool_calls": [{"function": first}]}
            )
            invoke(first)
        if fault in ("unknown tool", "budget", "later 503", "later malformed calls"):
            query = call("**/*todo*")
            if fault == "unknown tool":
                hidden: Obj = {"name": "absent", "arguments": {}}
                send({"role": "assistant", "tool_calls": [{"function": hidden}]})
                calls.append(hidden)
                history.append(
                    {
                        "role": "tool",
                        "tool_name": "absent",
                        "content": "MCP RPC error: "
                        "{'code': -32601, 'message': 'unknown tool absent'}",
                    }
                )
            elif fault == "budget":
                send({"role": "assistant", "tool_calls": [{"function": query} for _ in range(12)]})
                for _ in range(11):
                    invoke(query)
                calls.append(query)
                history.append(
                    {
                        "role": "tool",
                        "tool_name": "search_files",
                        "content": "arci: tool budget exceeded",
                    }
                )
            else:
                send({"role": "assistant", "tool_calls": [{"function": query}]})
                invoke(query)
        if spec.arm == "baseline" or opening == "none":
            query = call("todo" if opening == "none" else "**/*todo*")
            send({"role": "assistant", "content": "", "tool_calls": [{"function": query}]})
            invoke(query)
        passed = spec.arm == "baseline" or fault == "unearned pass"
        answer = ANSWER if spec.arm == "baseline" else "I could not find it."
        if fault == "budget":
            # ARCI skips the oracle after a budget latch, even for a correct final answer.
            answer = ANSWER
        if fault == "pending timeout":
            query = call("**/*todo*")
            send({"role": "assistant", "tool_calls": [{"function": query}]})
            start: Obj = {
                "call_id": "call-1",
                "tool": query["name"],
                "arguments": query["arguments"],
                "occurrence": 1,
            }
            events.append(Event(trial_id=spec.trial_id, seq=2, kind="tool_start", payload=start))
            incomplete.append(start)
        elif fault == "later malformed calls":
            send({"role": "assistant", "tool_calls": {"function": call("**/*todo*")}})
            answer = None
        elif fault == "eight steps":
            answer = None
            for _ in range(8):
                query = call("**/*todo*")
                send({"role": "assistant", "content": "", "tool_calls": [{"function": query}]})
                invoke(query)
        else:
            send({"role": "assistant", "content": answer})
        if fault in ("malformed as fail", "malformed as error", "later 503"):
            exchanges[-1]["response_b64"] = base64.b64encode(
                b"service unavailable"
                if fault == "later 503"
                else json.dumps(
                    {
                        "model": MODEL,
                        "done": True,
                        "message": {"role": "assistant"},
                        "received_sha256": exchanges[-1]["sha256"],
                    }
                ).encode()
            ).decode()
            if fault == "later 503":
                exchanges[-1]["status"] = 503
            answer = "" if fault == "malformed as fail" else None
        infra_error = fault in ("malformed as error", "later 503", "later malformed calls")
        timeout = fault in ("partial timeout", "pending timeout")
        stored = "different answer" if fault == "contradictory receipt" else answer
        if timeout:
            # The first response arrived, but the agent timed out before saving an answer.
            stored = answer = None
        receipt = {
            "run": RUN,
            "key_id": TASK,
            "seed": spec.seed,
            "arci_arm": spec.arm,
            "arm": arm_label,
            "opening": opening,
            "steps": len(exchanges),
            "calls": calls,
            "answer": stored,
            "complete": not timeout and not infra_error,
            "exchanges": exchanges,
        }
        key = json.dumps([RUN, TASK, spec.seed, spec.arm], separators=(",", ":")).encode()
        write(self.receipts / (hashlib.sha256(key).hexdigest() + ".json"), receipt)
        if fault == "missing call":
            _ = ledger.pop()
        return TrialEnvelope.create(
            spec_sha256=spec_sha256(spec),
            experiment_id=spec.experiment_id,
            trial_id=spec.trial_id,
            pair_id=spec.pair_id,
            arm=spec.arm,
            variant=spec.variant,
            task_id=spec.task_id,
            condition_id=spec.condition.condition_id,
            seed=spec.seed,
            outcome="ERROR"
            if infra_error or fault == "partial timeout"
            else ("PASS" if passed else "FAIL"),
            termination="harness_error"
            if infra_error
            else ("budget" if fault == "budget" else ("timeout" if timeout else "completed")),
            agent_claimed_success=not (infra_error or timeout),
            contract={"success": passed},
            recording=records,
            incomplete_calls=incomplete,
            events=events,
            final_state={"world": None, "answer": answer, "ledger": ledger},
            usage={
                "tool_calls": len(records) + len(incomplete),
                "wall_seconds": 120.05 if timeout else 0.504,
            },
        )

    def save(self) -> None:
        write_lines(self.store / "trials.jsonl", [t.model_dump(mode="json") for t in self.trials])
        write_lines(
            self.store / "events.jsonl",
            [e.model_dump(mode="json") for t in reversed(self.trials) for e in reversed(t.events)],
        )
        decision = (
            decide_suite(self.manifest, self.trials)
            if isinstance(self.manifest, SuiteManifest)
            else decide(self.manifest, self.trials)
        )
        write(self.store / "decision.json", decision.model_dump(mode="json"))
        self.verdict = decision.verdict.value

    def count(self) -> tuple[counter.Obj, str]:
        with (
            patch.object(counter, "Reference", StaticReference),
            patch.object(counter, "STUDY", self.study),
        ):
            return counter.verified_count(self.store, self.receipts, self.check)

    def receipt_path(self, side: str) -> Path:
        return next(p for p in self.receipts.iterdir() if counter.read(p)["arci_arm"] == side)

    def reseal(self, side: str, **updates: object) -> None:
        index = next(i for i, t in enumerate(self.trials) if t.arm == side)
        fields = self.trials[index].model_dump(exclude={"record_sha256"})
        self.trials[index] = TrialEnvelope.create(**(fields | updates))
        self.save()


class BlindCounter(unittest.TestCase):
    def root(self) -> Path:
        temp = TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(temp.cleanup)
        return Path(temp.name)

    def test_timeout_joins_final_start_seal_and_response_to_receipt_prefix(self) -> None:
        for fault in (
            "none",
            "persisted call",
            "wrong seal",
            "wrong response",
            "extra receipt call",
            "no start",
        ):
            with self.subTest(fault=fault):
                e = Evidence(self.root(), fault="pending timeout")
                t = next(t for t in e.trials if t.arm == "candidate")
                path = e.receipt_path(t.arm)
                receipt = counter.read(path)
                if fault == "wrong seal":
                    start: Obj = t.incomplete_calls[0].model_dump()
                    start["arguments"] = {}
                    e.reseal(t.arm, incomplete_calls=[start])
                elif fault == "wrong response":
                    exchange = counter.rows(receipt["exchanges"])[-1]
                    response = counter.parse(
                        base64.b64decode(counter.string(exchange["response_b64"]))
                    )
                    counter.obj(response["message"])["tool_calls"] = [{"function": call("todo")}]
                    exchange["response_b64"] = base64.b64encode(
                        json.dumps(response).encode()
                    ).decode()
                elif fault == "no start":
                    e.reseal(t.arm, events=t.events[:-1])
                elif fault in ("extra receipt call", "persisted call"):
                    counter.array(receipt["calls"]).append(call("**/*todo*"))
                    if fault == "extra receipt call":
                        counter.array(receipt["calls"]).append(call("todo"))
                write(path, receipt)
                if fault in ("none", "persisted call"):
                    with patch("sys.stderr", io.StringIO()):
                        output, _ = e.count()
                    counts = counter.obj(
                        counter.obj(counter.obj(output["arms"])["candidate"])["all"]
                    )
                    self.assertEqual((counts["failed"], counts["wall_timeouts"]), (1, 1))
                else:
                    with self.assertRaisesRegex(counter.Invalid, t.trial_id):
                        e.count()

    def test_later_malformed_tool_calls_requires_incomplete_error_without_answer(self) -> None:
        for fault in (
            "none",
            "completed receipt",
            "recorded answer",
            "wrong termination",
            "bad bytes",
            "first exchange",
        ):
            with self.subTest(fault=fault):
                e = Evidence(self.root(), fault="later malformed calls")
                path = e.receipt_path("candidate")
                receipt = counter.read(path)
                exchanges = counter.rows(receipt["exchanges"])
                if fault == "completed receipt":
                    receipt["complete"] = True
                elif fault == "recorded answer":
                    t = next(t for t in e.trials if t.arm == "candidate")
                    e.reseal(t.arm, final_state={**counter.obj(t.final_state), "answer": ""})
                elif fault == "wrong termination":
                    e.reseal("candidate", termination="crash", outcome="FAIL")
                elif fault == "bad bytes":
                    exchanges[-1]["response_b64"] = "%%%INVALID"
                elif fault == "first exchange":
                    response = counter.parse(
                        base64.b64decode(counter.string(exchanges[-1]["response_b64"]))
                    )
                    response["received_sha256"] = exchanges[0]["sha256"]
                    exchanges[0]["response_b64"] = base64.b64encode(
                        json.dumps(response).encode()
                    ).decode()
                write(path, receipt)
                if fault == "none":
                    output, _ = e.count()
                    self.assertEqual(counter.obj(output["pairs"])["errored"], 1)
                else:
                    with self.assertRaisesRegex(counter.Invalid, "F2:00000:candidate"):
                        e.count()

    def test_completed_answers_reject_unsupported_terminations(self) -> None:
        for side in ("baseline", "candidate"):
            for term in ("harness_error", "timeout", "grader_error"):
                with self.subTest(side=side, term=term):
                    e = Evidence(self.root())
                    t = next(t for t in e.trials if t.arm == side)
                    detail = "agent reported an infrastructure failure (exit <n>)"
                    e.reseal(
                        side,
                        outcome="FAIL" if term == "timeout" else "ERROR",
                        termination=term,
                        failure_detail=detail,
                        failure_fingerprint=fingerprint("harness", detail),
                        contract={"success": False},
                    )
                    with self.assertRaisesRegex(counter.Invalid, t.trial_id):
                        e.count()

    def test_elapsed_budget_alone_cannot_relabel_a_finished_answer(self) -> None:
        e = Evidence(self.root())
        t = next(t for t in e.trials if t.arm == "candidate")
        e.reseal(
            t.arm,
            termination="timeout",
            outcome="FAIL",
            usage={**t.usage.model_dump(), "wall_seconds": 120.1},
            failure_detail="trial exceeded max_seconds",
        )
        with self.assertRaisesRegex(
            counter.Invalid, t.trial_id + ": complete receipt contradicts timeout"
        ):
            e.count()

    def test_late_runner_failures_remain_counted_after_answer(self) -> None:
        for term, detail, clean_exit in (
            ("grader_error", "oracle raised ValueError", True),
            ("harness_error", "boundary exited before returning", True),
            ("harness_error", "event sink failed", True),
            ("harness_error", "agent reported an infrastructure failure (exit <n>)", False),
        ):
            with self.subTest(term=term, detail=detail):
                e = Evidence(self.root())
                e.reseal(
                    "baseline",
                    outcome="ERROR",
                    termination=term,
                    failure_detail=detail,
                    agent_claimed_success=clean_exit,
                    failure_fingerprint=fingerprint(
                        "grader" if term == "grader_error" else "harness", detail
                    ),
                    contract={
                        "success": detail == "event sink failed",
                        "grader_error": detail if term == "grader_error" else None,
                    },
                )
                output, _ = e.count()
                self.assertEqual(counter.obj(output["pairs"])["errored"], 1)

    def test_response_identity_and_completion_at_each_exchange(self) -> None:
        for live in (False, True):
            for step in (0, 1):
                for field, value in (
                    ("model", "other"),
                    ("done", False),
                    ("done", 1),
                    ("model", None),
                    ("done", None),
                ):
                    with self.subTest(live=live, step=step, field=field, value=value):
                        e = Evidence(self.root(), live=live)
                        path = e.receipt_path("baseline")
                        receipt = counter.read(path)
                        exchange = counter.rows(receipt["exchanges"])[step]
                        response = counter.parse(
                            base64.b64decode(counter.string(exchange["response_b64"]))
                        )
                        if value is None:
                            del response[field]
                        else:
                            response[field] = value
                        exchange["response_b64"] = base64.b64encode(
                            json.dumps(response).encode()
                        ).decode()
                        write(path, receipt)
                        if live:
                            e.publish()
                        with self.assertRaisesRegex(
                            counter.Invalid, f"F2:00000:baseline: response {field}"
                        ):
                            e.count()

    def test_registered_opening_requires_predicate_and_pinned_complete_reply(self) -> None:
        e = Evidence(self.root(), fault="changed opening")
        wrong = raw("Not what the server said")
        record: Obj = {"id": TASK, "cell": "F2", "bad_call": call("todo"), "original_result": wrong}
        e.transcript([record])
        original = StaticReference.original

        def changed_reference(ref: StaticReference, query: Obj) -> Obj:
            return wrong if query == call("todo") else original(ref, query)

        with (
            patch.object(StaticReference, "original", changed_reference),
            self.assertRaisesRegex(counter.Invalid, "predicate"),
        ):
            e.count()
        e = Evidence(self.root())
        for field in ("different object", "missing field", "untrusted bytes"):
            with self.subTest(field=field):
                e.transcript([{**record, "original_result": raw(SHIPPED)}])
                if field == "different object":
                    e.transcript([{**record, "original_result": {**raw(SHIPPED), "extra": None}}])
                elif field == "missing field":
                    e.transcript([{k: v for k, v in record.items() if k != "original_result"}])
                else:
                    with (e.check / "tasks.check.json").open("a") as stream:
                        _ = stream.write(" ")
                with self.assertRaisesRegex(counter.Invalid, "transcript|original_result"):
                    e.count()

    def test_published_http_write_without_standin_echo(self) -> None:
        # This constructs records only. A live HTTP backend does not echo a receipt digest.
        e = Evidence(self.root(), live=True)
        for path in e.receipts.iterdir():
            receipt = counter.read(path)
            for exchange in counter.rows(receipt["exchanges"]):
                del exchange["receiver_sha256"]
            write(path, receipt)
        e.publish()
        baseline = next(t for t in e.trials if t.arm == "baseline")
        self.assertEqual(counter.obj(baseline.final_state)["answer"], ANSWER)
        self.assertEqual(baseline.outcome.value, "PASS")
        result, _ = e.count()
        self.assertEqual(result["pairs"], {"minus": 1, "zero": 0, "plus": 0, "errored": 0})

    def test_receiver_digest_verifies_each_exchange(self) -> None:
        for fault in ("changed", "absent", "stand-in digest mismatch", "stand-in digest only"):
            with self.subTest(fault=fault):
                e = Evidence(self.root())
                for path in e.receipts.iterdir():
                    receipt = counter.read(path)
                    for exchange in counter.rows(receipt["exchanges"]):
                        if fault == "changed":
                            exchange["receiver_sha256"] = "0" * 64
                        else:
                            response = counter.parse(
                                base64.b64decode(counter.string(exchange["response_b64"]))
                            )
                            if fault == "absent":
                                del response["received_sha256"]
                            elif fault == "stand-in digest mismatch":
                                response["received_sha256"] = "1" * 64
                            else:
                                del exchange["receiver_sha256"]
                            exchange["response_b64"] = base64.b64encode(
                                json.dumps(response).encode()
                            ).decode()
                    write(path, receipt)
                e.publish()
                if fault == "stand-in digest only":
                    _ = e.count()
                else:
                    with self.assertRaisesRegex(counter.Invalid, "receiver"):
                        e.count()

    def test_correct_answer_with_invented_contract_violation(self) -> None:
        e = Evidence(self.root())
        t = next(t for t in e.trials if t.arm == "baseline")
        fields = t.model_dump(exclude={"record_sha256"})
        fields["outcome"] = "FAIL"
        fields["contract"]["violations"] = [
            {"invariant": "required_tools", "severity": "hard", "detail": "never used absent"}
        ]
        e.trials[e.trials.index(t)] = TrialEnvelope.create(**fields)
        e.save()
        with self.assertRaisesRegex(counter.Invalid, "violation"):
            e.count()

    def test_backend_missing_terminal_content(self) -> None:
        with self.assertRaisesRegex(counter.Invalid, "terminal|infrastructure"):
            Evidence(self.root(), fault="malformed as fail").count()
        result, _ = Evidence(self.root(), fault="malformed as error").count()
        self.assertEqual(counter.obj(result["pairs"])["errored"], 1)

    def test_aggregate_membership_and_content(self) -> None:
        e = Evidence(self.root())
        for filename in ("ledger.jsonl", "receipts.jsonl"):
            for fault in ("missing", "duplicate", "extra", "modified", "absent"):
                with self.subTest(filename=filename, fault=fault):
                    e.publish()
                    _ = e.count()
                    path = e.store / filename
                    records = list(counter.jsonl(path))
                    if fault == "absent":
                        path.unlink()
                    else:
                        if fault == "missing":
                            records.pop()
                        elif fault == "extra":
                            records.append({"extra": True})
                        elif fault == "duplicate":
                            records[0] = records[1]
                        else:
                            records[0]["extra"] = True
                        write_lines(path, records)
                    with self.assertRaisesRegex((ValueError, OSError), "aggregate|jsonl"):
                        e.count()

    def test_publication_requires_both_aggregates_even_when_neither_exists(self) -> None:
        e = Evidence(self.root())
        published = e.store.parent / "runs" / RUN
        published.parent.mkdir()
        e.store = e.store.rename(published)
        with self.assertRaisesRegex(counter.Invalid, "missing aggregate"):
            e.count()

    def test_boundary_history_is_derived_independently(self) -> None:
        for fault in ("unknown tool", "budget", "later 503"):
            with self.subTest(fault=fault):
                e = Evidence(self.root(), fault=fault)
                for path in e.receipts.iterdir():
                    receipt = counter.read(path)
                    if receipt["arci_arm"] != "candidate":
                        continue
                    exchanges = counter.rows(receipt["exchanges"])
                    if fault == "later 503":
                        exchanges[0].update(
                            status=503, response_b64=base64.b64encode(b"unavailable").decode()
                        )
                        reason = "unsuccessful chat response"
                    else:
                        exchange = exchanges[-1]
                        body = counter.parse(
                            base64.b64decode(counter.string(exchange["request_b64"]))
                        )
                        counter.rows(body["messages"])[-1]["content"] = "fabricated boundary reply"
                        data = json.dumps(body, ensure_ascii=False).encode()
                        sha = hashlib.sha256(data).hexdigest()
                        exchange.update(
                            request_b64=base64.b64encode(data).decode(),
                            sha256=sha,
                            receiver_sha256=sha,
                        )
                        reason = "independent history"
                    write(path, receipt)
                    with self.assertRaisesRegex(counter.Invalid, reason):
                        e.count()

    def test_boundary_refusal_budget_and_later_http_failure(self) -> None:
        for fault, termination in (
            ("unknown tool", "completed"),
            ("budget", "budget"),
            ("later 503", "harness_error"),
        ):
            with self.subTest(fault=fault):
                output, _ = Evidence(self.root(), fault=fault).count()
                counts = counter.obj(counter.obj(counter.obj(output["arms"])["candidate"])["all"])
                self.assertEqual(counts["by_termination"], {termination: 1})
                self.assertEqual(counts["errored"], int(fault == "later 503"))
                self.assertEqual(counts["call_budget"], int(fault == "budget"))

    def test_reference_file_info_uses_utc(self) -> None:
        e = Evidence(self.root())
        assert not isinstance(e.manifest, SuiteManifest)
        spec = next(iter(build_schedule(e.manifest)))
        env = Path(os.environ.get("REPLY0_ENV", "/Users/Shared/arci-reply0/env"))
        with ExitStack() as stack, patch.dict(os.environ, {"PATH": ""}):
            ref = counter.Reference(stack, counter.registration()[TASK], spec)
            confined = ["sandbox-exec", "-p", "(version 1)(allow default)(deny network*)"]
            self.assertEqual(
                ref.process.args,
                [
                    *([] if os.environ.get("REPLY0_NO_SANDBOX") == "1" else confined),
                    str(env / "node/bin/node"),
                    str(
                        env
                        / "node/node_modules/@modelcontextprotocol/server-filesystem/dist/index.js"
                    ),
                    FOLDER,
                ],
            )
            reply = ref.original(
                {"name": "get_file_info", "arguments": {"path": FOLDER + "/notes/todo.txt"}}
            )
            self.assertIn("GMT+0000 (Coordinated Universal Time)", counter.message_text(reply))

    def test_default_git_reference_confinement(self) -> None:
        e = Evidence(self.root())
        assert not isinstance(e.manifest, SuiteManifest)
        spec = next(iter(build_schedule(e.manifest)))
        with (
            ExitStack() as stack,
            patch.dict(os.environ, {"REPLY0_NO_SANDBOX": "0"}),
            patch.object(
                subprocess, "Popen", side_effect=OSError("captured before launch")
            ) as launch,
            self.assertRaisesRegex(OSError, "captured before launch"),
        ):
            counter.Reference(stack, counter.registration()["G1-g1"], spec)
        argv = launch.call_args.args[0]
        env = launch.call_args.kwargs["env"]
        self.assertEqual(
            argv[:3], ["sandbox-exec", "-p", "(version 1)(allow default)(deny network*)"]
        )
        self.assertEqual(
            (env["TZ"], env["LC_ALL"], env["PATH"]), ("UTC", "C", "/opt/homebrew/bin:/usr/bin:/bin")
        )
        self.assertEqual((env["GIT_CONFIG_GLOBAL"], env["GIT_CONFIG_NOSYSTEM"]), ("/dev/null", "1"))
        self.assertEqual(Path(env["HOME"]).name, "home")

    def test_verified_plain_counts(self) -> None:
        evidence = Evidence(self.root())
        output, verdict = evidence.count()
        self.assertEqual(verdict, evidence.verdict)
        self.assertEqual(set(output), {"experiment_id", "model", "cell", "phase", "pairs", "arms"})
        self.assertEqual(output["pairs"], {"minus": 1, "zero": 0, "plus": 0, "errored": 0})
        arms = counter.obj(output["arms"])
        for side, passed, retried in (("baseline", 1, "yes"), ("candidate", 0, "no")):
            arm_counts = counter.obj(arms[side])
            all_counts = counter.obj(arm_counts["all"])
            self.assertEqual(arm_counts["by_task"], {TASK: all_counts})
            self.assertEqual(all_counts["trials"], 1)
            self.assertEqual(all_counts["passed"], passed)
            self.assertEqual(all_counts["failed"], 1 - passed)
            self.assertEqual(all_counts["by_termination"], {"completed": 1})
            self.assertEqual(
                counter.obj(all_counts["corrected_same_tool"])[retried],
                {"trials": 1, "passed": passed},
            )

    def test_suite_rounds_and_gate(self) -> None:
        evidence = Evidence(self.root(), suite=True)
        result, verdict = evidence.count()
        self.assertEqual(result["pairs"], {"minus": 13, "zero": 0, "plus": 0, "errored": 0})
        self.assertEqual(verdict, evidence.verdict)

    def test_blind_faults_survive_resealing_but_fail_independent_check(self) -> None:
        for fault, reason in (
            ("missing call", "ledger call"),
            ("wrong original", "original server reply"),
            ("unearned pass", "answer"),
            ("contradictory receipt", "final response"),
        ):
            with self.subTest(fault=fault):
                evidence = Evidence(self.root(), fault=fault)
                self.assertTrue(all(t.validate_seal() for t in evidence.trials))
                with self.assertRaisesRegex(counter.Invalid, reason):
                    evidence.count()

    def test_duplicate_and_missing_observations(self) -> None:
        for fault in (
            "duplicate",
            "missing trial",
            "missing receipt",
            "extra receipt",
            "missing event",
            "duplicate event",
        ):
            with self.subTest(fault=fault):
                evidence = Evidence(self.root())
                path = evidence.store / "trials.jsonl"
                if fault == "duplicate":
                    with path.open("a") as stream:
                        _ = stream.write(evidence.trials[0].model_dump_json() + "\n")
                elif fault == "missing trial":
                    write_lines(path, [evidence.trials[0].model_dump(mode="json")])
                elif fault == "missing receipt":
                    next(evidence.receipts.iterdir()).unlink()
                elif fault == "extra receipt":
                    write(evidence.receipts / "extra.json", {})
                else:
                    path = evidence.store / "events.jsonl"
                    lines = path.read_text().splitlines()
                    _ = path.write_text(
                        "\n".join(lines[1:] if fault == "missing event" else lines + lines[:1])
                        + "\n"
                    )
                with self.assertRaises((ValueError, OSError)):
                    evidence.count()

    def test_unscripted_denominator_and_exposure(self) -> None:
        output, _ = Evidence(self.root(), opening="none").count()
        for side in ("baseline", "candidate"):
            counts = counter.obj(counter.obj(counter.obj(output["arms"])[side])["all"])
            self.assertEqual((counts["unscripted_exposed"], counts["unscripted_trials"]), (1, 1))
            self.assertEqual(
                counts["same_tool"],
                {"yes": {"trials": 0, "passed": 0}, "no": {"trials": 0, "passed": 0}},
            )

    def test_partial_timeout_and_eight_step_exhaustion(self) -> None:
        for fault in ("partial timeout", "eight steps"):
            with self.subTest(fault=fault):
                evidence = Evidence(self.root(), fault=fault)
                with patch("sys.stderr", new_callable=io.StringIO) as stderr:
                    output, _ = evidence.count()
                counts = counter.obj(counter.obj(counter.obj(output["arms"])["candidate"])["all"])
                self.assertEqual(counts["trials"], 1)
                self.assertEqual(counts["step_exhausted"], int(fault == "eight steps"))
                self.assertEqual(counts["wall_timeouts"], int(fault == "partial timeout"))
                self.assertEqual(counts["errored"], int(fault == "partial timeout"))
                self.assertEqual(
                    counter.obj(output["pairs"])["errored"], int(fault == "partial timeout")
                )
                self.assertEqual("R3" in stderr.getvalue(), fault == "partial timeout")

    def test_clean_same_label_and_canonical_cli(self) -> None:
        e = Evidence(self.root(), opening="clean")
        argv = [
            "count_b.py",
            str(e.store),
            "--check-dir",
            str(e.check),
            "--receipts",
            str(e.receipts),
        ]
        with (
            patch.object(counter, "Reference", StaticReference),
            patch.object(sys, "argv", argv),
            io.BytesIO() as buffer,
            io.TextIOWrapper(buffer, encoding="utf-8") as stream,
            patch.object(sys, "stdout", stream),
            patch.object(sys, "stderr", io.StringIO()) as err,
        ):
            self.assertEqual(counter.main(), 0)
            result = buffer.getvalue()
            decoded = json.loads(result)
            self.assertEqual(
                result,
                (
                    json.dumps(
                        decoded,
                        sort_keys=True,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                    + "\n"
                ).encode(),
            )
            self.assertEqual(decoded["phase"], "clean")
            self.assertEqual(
                [decoded["arms"][s]["all"]["passed"] for s in ("baseline", "candidate")], [1, 0]
            )
            self.assertIn(e.verdict, err.getvalue())

    def test_c0_separates_seeded_reply_injection_and_first_text(self) -> None:
        reg = counter.registration()["C0-c1"]
        original: Obj = {"isError": False, "content": [{"type": "text", "text": "paid 8712"}]}
        injected: Obj = {**original, "content": []}
        query: Obj = {"name": "lookup_order", "arguments": {"order_id": "ORD-103"}}
        argv: Obj = {"order_id": "ORD-103"}
        ledger: list[Obj] = [
            {
                "record": "call",
                "tool": "lookup_order",
                "arguments": argv,
                "seq": 0,
                "server_reply": original,
                "passed_on": original,
                "rule": None,
            }
        ]
        ref = create_autospec(counter.Reference, instance=True)
        ref.original.return_value = original
        for side, label, text in (
            ("baseline", "naming-sentence", reg.definition["sentence"]),
            ("candidate", "reply-as-given", ""),
        ):
            a = counter.Assignment("main", "bad", label, "none", "shipped", MODEL, RUN, False)
            uid = "C0:00000:" + side
            start: Obj = {
                "call_id": "lookup",
                "tool": "lookup_order",
                "occurrence": 0,
                "arguments": argv,
            }
            for injection in ("empty_result", None):
                finish: Obj = {
                    "call_id": "lookup",
                    "tool": "lookup_order",
                    "ok": True,
                    "value": injected,
                    "error_kind": None,
                    "injected_by": injection,
                }
                trial = TrialEnvelope.create(
                    spec_sha256="0" * 64,
                    experiment_id=RUN,
                    trial_id=uid,
                    pair_id="C0:00000",
                    arm=side,
                    variant=label,
                    task_id="C0-c1",
                    condition_id="C0",
                    seed=2,
                    outcome="FAIL",
                    termination="completed",
                    usage={},
                    events=[
                        {"kind": "tool_start", "trial_id": uid, "seq": 0, "payload": start},
                        {"kind": "tool_finish", "trial_id": uid, "seq": 1, "payload": finish},
                    ],
                    recording=[
                        {
                            "tool": "lookup_order",
                            "occurrence": 0,
                            "arguments_sha256": hash_record(argv),
                            "result": finish,
                        }
                    ],
                )
                if injection is None:
                    with self.assertRaisesRegex(counter.Invalid, "fault injection"):
                        counter.delivery(trial, ledger, reg, a, ref)
                else:
                    result = counter.delivery(trial, ledger, reg, a, ref)
                    self.assertEqual(result.texts, [text])
                    self.assertEqual(result.calls, [query])
                    contract = ContractSpec(oracle="reply0_oracle:passed")
                    fields = trial.model_dump(exclude={"record_sha256"})
                    fields.update(outcome="PASS", contract={"success": True})
                    counter.verify_grade(
                        TrialEnvelope.create(**fields), contract, "8712", ["8712"], []
                    )
                    fields.update(
                        outcome="FAIL",
                        contract={
                            "success": True,
                            "violations": [
                                {
                                    "invariant": "forbidden_tools",
                                    "severity": "hard",
                                    "detail": "used lookup_order",
                                }
                            ],
                        },
                    )
                    with self.assertRaisesRegex(counter.Invalid, "violation"):
                        counter.verify_grade(
                            TrialEnvelope.create(**fields), contract, "8712", ["8712"], []
                        )
                    registered_limit = ContractSpec(
                        oracle="reply0_oracle:passed", forbidden_tools=("lookup_order",)
                    )
                    counter.verify_grade(
                        TrialEnvelope.create(**fields), registered_limit, "8712", ["8712"], []
                    )

    def test_wrong_edited_source_with_self_consistent_digest(self) -> None:
        patch_bytes = (
            b"--- a/handler\n+++ b/handler\n@@ -1 +1 @@\n-old answer\n+registered answer\n"
        )
        counter.verify_patched_bytes(b"old answer\n", b"registered answer\n", patch_bytes)
        with self.assertRaisesRegex(counter.Invalid, "does not produce edited source"):
            counter.verify_patched_bytes(b"old answer\n", b"unregistered answer\n", patch_bytes)

    def test_wrong_decision_and_descriptor(self) -> None:
        e = Evidence(self.root())
        decision_path = e.store / "decision.json"
        fields = json.loads(decision_path.read_bytes())
        del fields["record_sha256"]
        fields["verdict"] = "BLOCK" if fields["verdict"] != "BLOCK" else "PASS"
        write(decision_path, GateDecision.create(**fields).model_dump(mode="json"))
        with self.assertRaisesRegex(ValueError, "decision mismatch"):
            e.count()
        e.save()
        path = e.store / "descriptor.yaml"
        changed = json.loads(path.read_bytes())
        changed["base_seed"] = 913
        write(path, changed)
        with self.assertRaisesRegex(ValueError, "compiled manifest"):
            e.count()

    def test_cli_rejects_invalid_input_without_verified_json(self) -> None:
        root = self.root()
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "harness/count_b.py"),
                str(root),
                "--receipts",
                str(root),
                "--check-dir",
                str(root),
            ],
            capture_output=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, b"")
        self.assertIn(b"invalid count", proc.stderr)
