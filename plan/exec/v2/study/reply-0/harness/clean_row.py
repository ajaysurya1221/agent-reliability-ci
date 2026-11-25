"""Operate one registered Reply-0 slot. See run-reply0.sh for the command interface."""

from __future__ import annotations

import argparse
import base64
import binascii
import fcntl
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import time
from collections.abc import Generator
from contextlib import ExitStack, contextmanager, suppress
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import IO, Any
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# The shell verifies wiring_check.py against origin before this import. Validate
# the remaining local Python sources before importing modules with executable code.
if __name__ == "__main__" and sys.argv[1:2] in (["real"], ["check"]):
    from harness.wiring_check import registration

    try:
        registration()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        sys.exit(f"Reply-0: {exc}")

from harness import audit, make_suites, suite_process  # noqa: E402
from harness import wiring_check as wire  # noqa: E402
from harness.agent import atomic_json  # noqa: E402
from harness.wiring_check import probe_chat as ollama_chat  # noqa: E402

OPS = wire.CLAIMS
LOCK_SECONDS = 30.0
POSTRUN_SECONDS = 1800.0
RUNS = ROOT / "runs"
KEPT = ROOT / "clean-row/kept.json"
CHECKS = ROOT / "tasks/check"
ELIGIBLE = ("F1", "G1", "F2")
SIDES = ("baseline", "candidate")
STORE_FILES = ("manifest.json", "trials.jsonl", "events.jsonl", "decision.json")
EXPORTS = (
    "descriptor.yaml",
    *STORE_FILES,
    "ledger.jsonl",
    "receipts.jsonl",
    "audit.json",
    "count_a.json",
    "count_b.json",
    "run.log",
)
Row = dict[str, Any]


@dataclass(frozen=True)
class Slot:
    phase: str
    model: str
    cell: str = ""
    task: str = ""

    @property
    def id(self) -> str:
        return "-".join(filter(None, ("reply0", self.phase, self.model, self.cell, self.task)))

    @property
    def plain(self) -> bool:
        return self.phase in ("clean", "unscripted")


def slots(doc: Row) -> list[Slot]:
    result: list[Slot] = []
    for model in wire.MODELS:
        result.append(Slot("wiring", model))
        for cell, entry in doc["cells"].items():
            if model == "12B" and cell in ("F0", "G2"):
                continue
            for task in entry["main"] + entry["held_out"]:
                result.append(Slot("clean", model, cell, task["id"]))
            if cell in ELIGIBLE:
                result.extend(Slot("unscripted", model, cell, t["id"]) for t in entry["main"])
                result.append(Slot("generic", model, cell))
            result.append(Slot("main", model, cell))
            if cell == "F1":
                result.append(Slot("confirmation", model, cell))
    return result


def select(all_slots: list[Slot], run: str) -> list[Slot]:
    exact = [s for s in all_slots if s.id == run]
    if exact:
        return exact
    cell = [s for s in all_slots if s.plain and Slot(s.phase, s.model, s.cell).id == run]
    wire.need(bool(cell), "unknown registered RUN")
    return cell


@contextmanager
def locked(name: str = "admission") -> Generator[None, None, None]:
    wire.need(OPS.resolve() == OPS, "linked claim root")
    OPS.mkdir(exist_ok=True)
    with suite_process.locked_file(OPS / (name + ".lock"), LOCK_SECONDS):
        yield


def claim(slot: Slot, reg: wire.Registration, *, amendment: bool = False) -> Path:
    directory = OPS / (slot.id + (".amendment" if amendment else ""))
    wire.need(directory.parent.resolve() == directory.parent, "linked claim directory")
    directory.mkdir()
    atomic_json(
        directory / "claim.json",
        {
            "run": slot.id,
            "model": slot.model,
            "registration": reg.commit,
            "registration_sha256": reg.registration_sha256,
            "started": time.time(),
        },
        create=True,
    )
    return directory


def result(slot: Slot) -> Row | None:
    marker = OPS / slot.id / "finished.json"
    if not marker.is_file():
        claimed = marker.parent / "claim.json"
        if not claimed.exists():
            return None
        with claimed.open("rb") as active:
            try:
                fcntl.flock(active, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return None
            if not marker.is_file():
                return {
                    "valid": False,
                    "counts_agree": False,
                    "statistical_block": False,
                    "interrupted": True,
                }
    info = audit.read(marker)
    folder = RUNS / slot.id
    audit.same(sorted(info["hashes"]), sorted(EXPORTS), "finished file inventory")
    for name, sha in info["hashes"].items():
        wire.need(
            name in EXPORTS and audit.digest(wire.safe_file(folder, name)) == sha,
            f"{slot.id}: changed {name}",
        )
    audited = audit.read(folder / "audit.json")
    audit.same(
        info["statistical_block"],
        audited.get("statistical_block", False),
        "stored statistical BLOCK",
    )
    if info["counts_agree"]:
        audit.same(
            audit.read(folder / "count_a.json"),
            audit.read(folder / "count_b.json"),
            "stored counts",
        )
    audit.same(info["valid"], bool(audited["valid"] and info["counts_agree"]), "reading conditions")
    return info


def clean_summary(doc: Row, all_slots: list[Slot]) -> Row:
    out: Row = {}
    for s in all_slots:
        if s.phase != "clean":
            continue
        finished = result(s)
        wire.need(
            finished is not None and finished["counts_agree"], f"missing verified clean pair {s.id}"
        )
        assert finished is not None
        by_model = out.setdefault(s.model, {})
        by_cell = by_model.setdefault(s.cell, {})
        parts = doc["cells"][s.cell]
        part = "main" if s.task in {t["id"] for t in parts["main"]} else "held_out"
        group = by_cell.setdefault(part, {"kept": [], "tasks": {}})
        counted = audit.read(RUNS / s.id / "count_a.json")
        audit.same(
            [counted[k] for k in ("experiment_id", "model", "phase", "cell")],
            [s.id, wire.MODELS[s.model], "clean", s.cell],
            "clean pair identity",
        )
        values = [counted["arms"][side]["by_task"][s.task] for side in SIDES]
        wire.need(all(v["trials"] == 1 for v in values), "clean pair incomplete")
        passed = sum(v["passed"] for v in values)
        group["tasks"][s.task] = {
            "passes": passed,
            "errors": sum(v["errored"] for v in values),
            "seconds_per_trial": finished["seconds"] / 2,
        }
        if passed:
            group["kept"].append(s.task)
    for cells in out.values():
        for parts in cells.values():
            for part in ("main", "held_out"):
                group = parts.setdefault(part, {"kept": [], "tasks": {}})
                group["rounds"] = make_suites.ROUNDS.get(len(group["kept"]))
                group["status"] = "eligible" if group["rounds"] else "not run"
                times = [t["seconds_per_trial"] for t in group["tasks"].values()]
                group["seconds_per_trial"] = sum(times) / len(times) if times else None
    return out


def wiring_state(*, ready: bool = True) -> Row:
    merged: Row = {}
    for key in wire.MODELS:
        attempts = []
        for suffix in ("", ".amendment"):
            p = OPS / ("reply0-wiring-" + key + suffix) / "wiring.json"
            if p.is_file():
                attempts.append(audit.read(p))
        if not attempts:
            wire.need(not ready, f"wiring missing for {key}")
            continue
        checks = attempts[-1]["checks"]
        fallback = None
        if ready or (len(checks) == 2 and checks[0]["status"] == 200 and checks[0]["message"]):
            try:
                fallback = wire.fallback(checks, wire.MODELS[key])
            except ValueError:
                if ready:
                    raise
        merged[key] = {"attempts": attempts, "empty_fallback_null": fallback}
    return merged


def retained(s: Slot, kept: Row) -> list[str]:
    return kept[s.model][s.cell]["held_out" if s.phase == "confirmation" else "main"]["kept"]


def valid_block(s: Slot) -> bool:
    info = result(s)
    return bool(info and info["valid"] and info["statistical_block"])


def finished_or_small(s: Slot, kept: Row) -> bool:
    return len(retained(s, kept)) < 5 or result(s) is not None


def suite_order(s: Slot, kept: Row) -> bool:
    """Enforce dependencies. Return whether the requested suite is shown only."""
    wire.need(len(retained(s, kept)) >= 5, "not run: fewer than five retained tasks")
    control = Slot("main", "4B", "C0")
    if s == control:
        return False
    wire.need(valid_block(control), "4B C0 lacks a valid statistical BLOCK")
    screens = [Slot("main", m, "F1") for m in wire.MODELS]
    first, second = screens
    if s == first:
        return False
    wire.need(finished_or_small(first, kept), "4B F1 must run first")
    chosen = next(
        (
            screen.model
            for screen in screens
            if valid_block(screen) and len(kept[screen.model]["F1"]["held_out"]["kept"]) >= 5
        ),
        None,
    )
    if s.phase == "confirmation":
        wire.need(s.model == chosen, "confirmation is not the first qualifying F1")
        return False
    if chosen:
        wire.need(
            result(Slot("confirmation", chosen, "F1")) is not None, "confirmation has priority"
        )
    if s == second and not chosen:
        return False
    if not chosen:
        wire.need(finished_or_small(second, kept), "12B F1 screen has priority")
    measured = [Slot("main", m, c) for m in wire.MODELS for c in ("G1", "F2")]
    if s in measured:
        return False
    wire.need(
        all(finished_or_small(other, kept) for other in measured),
        "measured G1/F2 runs have priority",
    )
    if s.phase == "generic":
        wire.need(
            all(
                finished_or_small(other, kept)
                for other in (
                    second,
                    Slot("main", "4B", "F0"),
                    Slot("main", "4B", "G2"),
                    Slot("main", "12B", "C0"),
                )
            ),
            "generic follow-up is last",
        )
        eligible = [screen for screen in [*screens, *measured] if len(retained(screen, kept)) >= 5]
        target = next((screen for screen in eligible if valid_block(screen)), eligible[0])
        wire.need(
            (s.model, s.cell) == (target.model, target.cell), "different generic follow-up selected"
        )
    return True


def deadline(now: datetime) -> datetime:
    # Day three is the second active local date after the design date.
    stamp = date(2026, 11, 25)
    dates = {
        datetime.fromtimestamp(int(t)).date()
        for t in wire.git("log", "--format=%ct", "HEAD", "--", ".").splitlines()
    }
    for clock in OPS.glob("reply0-*/trial-clock.json"):
        stores = clock.parent / "stores"
        if any(p.stat().st_size for p in stores.glob("*/events.jsonl")):
            dates.add(datetime.fromtimestamp(audit.read(clock)["started"]).date())
    active = sorted(d for d in dates | {now.date()} if d > stamp)
    last = active[1] if len(active) >= 2 else now.date() + timedelta(days=2 - len(active))
    return datetime.combine(last + timedelta(days=1), datetime.min.time())


def config(s: Slot, doc: Row, kept: Row, fallback: bool) -> Row:
    info = doc["cells"][s.cell]
    ids = [s.task] if s.plain else retained(s, kept)
    rows = [t for t in info["main"] + info["held_out"] if t["id"] in ids]
    return make_suites.descriptor(
        doc,
        audit.ENV,
        audit.FX,
        s.cell,
        s.phase,
        s.model,
        rows,
        run=s.id,
        plain=s.plain,
        edited=audit.ENV / "edited" if s.phase == "confirmation" else None,
        fallback=s.cell == "C0" and s.phase == "main" and fallback,
    )


def prepare(doc: Row, all_slots: list[Slot], kept: Row, wiring: Row) -> dict[str, str]:
    pins = {}
    for s in all_slots:
        if s.plain or s.phase == "wiring" or len(retained(s, kept)) < 5:
            continue
        p = RUNS / s.id / "descriptor.yaml"
        make_suites.write_json(p, config(s, doc, kept, wiring[s.model]["empty_fallback_null"]))
        pins[str(p.relative_to(ROOT))] = audit.digest(p)
    return pins


def operator_identifiers() -> set[str]:
    keys = (
        "HOME",
        "USER",
        "LOGNAME",
        "GIT_USER_NAME",
        "GIT_USER_EMAIL",
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
        "EMAIL",
    )
    values = {os.environ.get(key, "") for key in keys}
    for name in ("user.name", "user.email"):
        value = subprocess.run(
            ["/opt/homebrew/bin/git", "--no-optional-locks", "config", "--get", name],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=5,
        )
        wire.need(value.returncode in (0, 1), "cannot determine git identity")
        if value.returncode == 0:
            values.add(value.stdout.decode().strip())
    return {v.casefold() for v in values if v}


def safe_bytes(data: bytes, identifiers: set[str] | None = None) -> None:
    private = operator_identifiers() if identifiers is None else identifiers
    path = re.compile(r"/(?:Users/(?!Shared(?:/|\b))|home/)[A-Za-z0-9_.-]+(?:/|\b)")

    class Members(list[tuple[str, Any]]):
        """Retain every JSON member, including duplicate keys in a log."""

    binary_controls = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
    decoder = json.JSONDecoder(object_pairs_hook=Members)
    token = re.compile(r'["{\[]')
    encoded_field = re.compile(
        r"(?:.*_)?(?:b64|base64|data|blob|payload|body|log|logs|content|receipt|ledger|stdout|stderr|request|response)"
    )

    def visit(value: Any, key: str, depth: int) -> None:
        wire.need(depth < 64, "publication payload nesting exceeds scan limit")
        if isinstance(value, Members):
            if any(name in ("blob", "data") for name, _ in value):
                for name, item in value:
                    if name.casefold() in ("mimetype", "content-type") and isinstance(item, str):
                        charset = re.search(r"""(?i)\bcharset\s*=\s*["']?([^;' "]+)""", item)
                        wire.need(
                            charset is None
                            or charset[1].casefold() in {"utf-8", "utf8", "us-ascii"},
                            "uninspectable declared encoding",
                        )
            for name, item in value:
                if key == "resource" and name == "blob":
                    wire.need(isinstance(item, str), "uninspectable resource blob")
                scan(name, "", depth)
                visit(item, name, depth + 1)
        elif isinstance(value, list):
            for element in value:
                visit(element, key, depth + 1)
        elif isinstance(value, str):
            scan(value, key, depth)

    def scan(text: str, key: str = "", depth: int = 0) -> None:
        wire.need(depth < 64, "publication payload nesting exceeds scan limit")
        wire.need("\x00" not in text, "uninspectable text encoding")
        folded = text.casefold()
        wire.need(
            not path.search(text) and not any(v in folded for v in private),
            "personal identifier or path in publication or descriptor",
        )
        if "%" in text and (decoded := unquote(text)) != text:
            scan(decoded, key, depth + 1)
        name = key.casefold()
        strict = name in {"blob", "data", "base64", "b64"} or name.endswith(("_b64", "_base64"))
        if strict or encoded_field.fullmatch(name):
            compact = "".join(text.split())
            if strict or (compact and re.fullmatch(r"[A-Za-z0-9+/_-]+={0,2}", compact)):
                try:
                    decoded_bytes = base64.b64decode(
                        compact if strict else compact + "=" * (-len(compact) % 4),
                        altchars=b"-_",
                        validate=True,
                    )
                    decoded_text = decoded_bytes.decode("utf-8")
                except (binascii.Error, UnicodeDecodeError) as exc:
                    if strict:
                        raise ValueError("uninspectable encoded payload") from exc
                else:
                    if strict:
                        wire.need(
                            not binary_controls.search(decoded_text),
                            "uninspectable encoded payload",
                        )
                    if not binary_controls.search(decoded_text):
                        scan(decoded_text, depth=depth + 1)
        # Find JSON values even in a log with timestamps, prefixes or multiple records.
        offset = 0
        while match := token.search(text, offset):
            try:
                value, offset = decoder.raw_decode(text, match.start())
            except ValueError:
                offset = match.end()
            else:
                visit(value, "", depth + 1)

    scan(data.decode("utf-8", errors="strict"))


def live_claim(slot: Slot, reg: wire.Registration, *, amendment: bool = False) -> Path:
    name = slot.id + (".amendment" if amendment else "")
    wire.need(not os.path.lexists(OPS / name), "canonical slot already claimed")
    return claim(slot, reg, amendment=amendment)


def admission(s: Slot, reg: wire.Registration, doc: Row, all_slots: list[Slot]) -> tuple[Path, Row]:
    now = datetime.now()
    limit = deadline(now)
    time_check(s, now < limit)
    if s.phase == "wiring":
        initial = OPS / s.id
        amend = initial.exists()
        if amend:
            amendments = [
                audit.read(p)["registration"]
                for p in OPS.glob("reply0-wiring-*.amendment/claim.json")
            ]
            wire.need(
                all(commit == reg.commit for commit in amendments),
                "the single wiring amendment has been used",
            )
            old = audit.read(initial / "wiring.json")
            old_commit = old["registration"]
            checks = old["checks"]
            wire.need(
                (
                    len(checks) == 2
                    or (len(checks) == 1 and checks[0]["status"] == 200 and checks[0]["problem"])
                )
                and not (checks[0]["status"] == 200 and checks[0]["message"]),
                "wiring already claimed",
            )
            wire.need(
                old_commit != reg.commit
                and wire.git("merge-base", old_commit, reg.commit).decode().strip() == old_commit,
                "wiring needs a pushed amendment",
            )
            wire.need(
                wire.blob(old_commit, "harness/agent.py")
                != wire.blob(reg.commit, "harness/agent.py")
                and wire.blob(old_commit, wire.REG) != wire.blob(reg.commit, wire.REG),
                "agent and registration must be amended",
            )
            saved = json.loads(wire.blob(reg.commit, "wiring.json"))
            wire.need(
                saved[s.model]["attempts"][0] == old,
                "failed wiring evidence must be pushed",
            )
        return live_claim(s, reg, amendment=amend), {}
    wiring = wiring_state()
    amended_from = {
        attempts["attempts"][0]["registration"]
        for attempts in wiring.values()
        if len(attempts["attempts"]) == 2 and attempts["attempts"][-1]["registration"] == reg.commit
    }
    wire.need(
        all(
            row["attempts"][-1]["registration"] in {reg.commit, *amended_from}
            for row in wiring.values()
        ),
        "wiring was not performed under the pushed registration",
    )
    audit.same(audit.read(ROOT / "wiring.json"), wiring, "published wiring record")
    kept: Row = {}
    note = None
    pinned_descriptor = None
    if s.phase != "clean":
        kept = clean_summary(doc, all_slots)
        audit.same(audit.read(KEPT), kept, "retained sets")
    if s.phase == "unscripted":
        speed = kept[s.model][s.cell]["main"]["seconds_per_trial"]
        time_check(s, now + timedelta(seconds=2 * speed) < limit)
    if not s.plain:
        for u in all_slots:
            if u.phase == "unscripted":
                r = result(u)
                wire.need(r is not None and r["counts_agree"], f"unscripted row missing: {u.id}")
        note, pins = wire.descriptor_note(reg)
        freeze = {
            "registration": reg.commit,
            "note": note,
            "digest": audit.digest(ROOT / wire.NOTE),
        }
        if (OPS / "descriptor-freeze.json").exists():
            audit.same(
                audit.read(OPS / "descriptor-freeze.json"),
                freeze,
                "descriptor note at first deciding run",
            )
        # The dated note follows completion of the *last* clean pair.
        committed = int(wire.git("show", "-s", "--format=%ct", note))
        wire.need(
            committed
            >= int(
                max(
                    (OPS / u.id / "finished.json").stat().st_mtime
                    for u in all_slots
                    if u.phase == "clean"
                )
            ),
            "descriptor note predates clean row",
        )
        shown = suite_order(s, kept)
        if shown:
            groups = kept[s.model][s.cell]["main"]
            cap = 2 * len(retained(s, kept)) * groups["rounds"]
            time_check(s, now + timedelta(seconds=cap * groups["seconds_per_trial"]) < limit)
        relative = f"runs/{s.id}/descriptor.yaml"
        wire.need(relative in pins, "descriptor missing from pushed note")
        pinned_descriptor = pins[relative]
    descriptor = config(s, doc, kept, wiring[s.model]["empty_fallback_null"])
    path = RUNS / s.id / "descriptor.yaml"
    wire.need(path.resolve() == path, "linked descriptor or run directory")
    if not s.plain or path.exists():
        audit.same(audit.read(path), descriptor, "registered live descriptor")
    safe_bytes(audit.encoded(descriptor).encode())
    for side in SIDES:
        wire.need(
            "--offline" not in descriptor[side]["command"]["argv"],
            "offline descriptor on real path",
        )
    wire.need(
        not any(
            (RUNS / s.id / n).exists() or (RUNS / s.id / n).is_symlink()
            for n in EXPORTS
            if n != "descriptor.yaml"
        ),
        "run output already exists",
    )
    if s.phase == "confirmation":
        with TemporaryDirectory(dir=ROOT) as tmp:
            rebuilt = audit.build(audit.ENV, Path(tmp), "F1")
            actual = audit.ENV / "edited/F1"
            audit.same(
                audit.read(actual / "digests.json"),
                audit.read(rebuilt / "digests.json"),
                "edit manifest",
            )
            audit.same(
                audit.hashes(actual / "package"),
                audit.read(rebuilt / "digests.json")["after"],
                "edited package",
            )
            wire.need(
                (actual / "node_modules").resolve() == (audit.ENV / "node/node_modules").resolve(),
                "edited dependency path differs",
            )
    directory = live_claim(s, reg)
    if note is not None and not (OPS / "descriptor-freeze.json").exists():
        atomic_json(
            OPS / "descriptor-freeze.json",
            {"registration": reg.commit, "note": note, "digest": audit.digest(ROOT / wire.NOTE)},
            create=True,
        )
    if s.plain:
        make_suites.write_json(path, descriptor)
    actual_digest = audit.digest(path)
    if pinned_descriptor is not None:
        audit.same(actual_digest, pinned_descriptor, "admitted descriptor pin")
    return directory, {"descriptor": actual_digest, "descriptor_commit": note}


def bind_schedule(
    s: Slot, directory: Path, reg: wire.Registration, descriptor: Path, expected: str, token: str
) -> None:
    audit.same(audit.digest(ROOT / wire.REG), reg.registration_sha256, "admitted registration")
    audit.same(audit.digest(descriptor), expected, "admitted descriptor")
    manifest = audit.compile_run_descriptor(descriptor)
    audit.same(audit.digest(descriptor), expected, "compiled descriptor pin")
    specs = (
        [
            spec
            for rd in range(1, manifest.max_rounds + 1)
            for spec in audit.build_suite_round(manifest, rd)
        ]
        if isinstance(manifest, audit.SuiteManifest)
        else audit.build_schedule(manifest)
    )
    trials = {}
    for spec in specs:
        assert spec.command is not None
        argv = spec.command.argv
        key = wire.trial_binding(
            spec.task,
            spec.arm,
            spec.seed,
            spec.variant,
            argv[argv.index("--opening") + 1],
            argv[argv.index("--model") + 1],
            argv[argv.index("--prompt") + 1],
        )
        wire.need(key not in trials, "ambiguous scheduled identity")
        trials[key] = spec.trial_id
    atomic_json(
        directory / "schedule.json",
        {
            "run": s.id,
            "registration": reg.commit,
            "registration_sha256": reg.registration_sha256,
            "descriptor_sha256": expected,
            "token_sha256": wire.digest(token.encode()),
            "trials": trials,
        },
        create=True,
    )


def postrun(argv: list[str], output: IO[bytes], log: IO[str], env: dict[str, str]) -> int:
    with subprocess.Popen(
        argv, stdin=subprocess.DEVNULL, stdout=output, stderr=log, env=env, start_new_session=True
    ) as proc:
        try:
            return proc.wait(timeout=POSTRUN_SECONDS)
        except subprocess.TimeoutExpired:
            with suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            print("post-run deadline exceeded", Path(argv[2]).name, file=log, flush=True)
            raise


def run_trial_slot(s: Slot, directory: Path, reg: wire.Registration, evidence: Row) -> None:
    folder = RUNS / s.id
    receipts = directory / "receipts"
    receipts.mkdir()
    descriptor = folder / "descriptor.yaml"
    small_env = {
        "PATH": os.environ["PATH"],
        "HOME": str(audit.ENV / "home"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(ROOT / "harness"),
        "LC_ALL": "C",
        "TZ": "UTC",
        "REPLY0_RECEIPTS": str(receipts),
        "REPLY0_ENV": str(audit.ENV),
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    if os.environ.get("REPLY0_NO_SANDBOX") == "1":
        small_env["REPLY0_NO_SANDBOX"] = "1"
    token = secrets.token_hex(32)
    bind_schedule(s, directory, reg, descriptor, evidence["descriptor"], token)
    small_env["REPLY0_LAUNCH_TOKEN"] = token
    with (folder / "run.log").open("x") as log:
        print(
            audit.encoded(
                {
                    "run": s.id,
                    "registration": reg.commit,
                    "model_digest": reg.models[s.model],
                    "ollama_version": reg.version,
                    "context": 32768,
                    **evidence,
                }
            ),
            file=log,
            flush=True,
        )
        wire.warm(wire.MODELS[s.model], ollama_chat, directory / "warmup-response.bin")
        wire.metadata(reg, s.model, loaded=True)
        started = time.monotonic()
        now = datetime.now()
        remaining = (deadline(now) - now).total_seconds()
        wire.need(remaining > 0, "not run: time")
        atomic_json(directory / "trial-clock.json", {"started": time.time()}, create=True)
        process = subprocess.run(
            suite_process.command(
                directory,
                "run",
                ["run", str(descriptor), "--workers", "1", "--out", str(directory / "stores")],
            ),
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=small_env,
            timeout=remaining,
        )
        small_env.pop("REPLY0_LAUNCH_TOKEN")
        elapsed = time.monotonic() - started
        print("arci exit", process.returncode, file=log, flush=True)
        (store,) = (directory / "stores").iterdir()
        for name in STORE_FILES:
            os.link(store / name, folder / name)
        # Preserve all observations, even on disagreement or an invalid audit.
        with (folder / "receipts.jsonl").open("x") as out:
            for p in sorted(receipts.glob("*.json")):
                print(audit.encoded(audit.read(p)), file=out)
        with (folder / "ledger.jsonl").open("x") as out:
            for trial in audit.lines(folder / "trials.jsonl"):
                print(
                    audit.encoded(
                        {
                            "trial_id": trial["trial_id"],
                            "ledger": (trial.get("final_state") or {}).get("ledger"),
                        }
                    ),
                    file=out,
                )
        args = [str(folder), "--receipts", str(receipts), "--check-dir", str(CHECKS)]
        args += ["--descriptor-sha256", evidence["descriptor"]]
        if s.phase == "confirmation":
            args += ["--edited", str(audit.ENV / "edited")]
        status: dict[str, int] = {}
        for name in ("audit", "count_a", "count_b"):
            with (folder / (name + ".json")).open("xb") as output:
                status[name] = postrun(
                    suite_process.command(
                        directory,
                        "exec",
                        [sys.executable, "-B", str(ROOT / "harness" / (name + ".py")), *args],
                    ),
                    output,
                    log,
                    small_env,
                )
        summary = audit.read(folder / "audit.json")
        if summary.get("gate"):
            print(summary["gate"], file=log)
        counts_agree = (
            status["count_a"] == status["count_b"] == 0
            and (folder / "count_a.json").read_bytes() == (folder / "count_b.json").read_bytes()
        )
        valid = status["audit"] == 0 and summary["valid"] and counts_agree
        print(
            "audit/count exit codes", audit.encoded(status), "counts agree", counts_agree, file=log
        )
    audit.fixture()
    atomic_json(
        directory / "finished.json",
        {
            "hashes": {n: audit.digest(folder / n) for n in EXPORTS},
            "valid": valid,
            "counts_agree": counts_agree,
            "seconds": elapsed,
            "statistical_block": summary.get("statistical_block", False),
        },
        create=True,
    )
    wire.need(valid, f"{s.id}: reading conditions failed; evidence retained")


def execute(s: Slot, doc: Row, all_slots: list[Slot]) -> None:
    wire.live_paths(ROOT, Path(os.environ["REPLY0_ENV"]))
    reg = wire.registration()
    wire.versions(audit.ENV)
    audit.fixture()
    with locked("suite"), ExitStack() as stack:
        with locked():
            suite_process.clear(OPS)
            directory, evidence = admission(s, reg, doc, all_slots)
            active = stack.enter_context((directory / "claim.json").open("rb"))
            fcntl.flock(active, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with suite_process.registry(OPS) as path:
                atomic_json(
                    path,
                    {"claim": directory.name, "launcher": os.getpid(), "groups": []},
                    create=True,
                )
        token = wire.PROBE.set(wire.ProbeAdmission(directory, s.id, s.model, reg))
        try:
            launch(s, doc, all_slots, directory, reg, evidence)
        finally:
            wire.PROBE.reset(token)
            suite_process.clear(OPS, finishing=directory)


def launch(
    s: Slot, doc: Row, all_slots: list[Slot], directory: Path, reg: wire.Registration, evidence: Row
) -> None:
    wire.metadata(reg, s.model)
    if s.phase == "wiring":

        def save(checks: list[Row]) -> None:
            with locked():
                atomic_json(
                    directory / "wiring.json",
                    {"model": wire.MODELS[s.model], "registration": reg.commit, "checks": checks},
                )
                atomic_json(ROOT / "wiring.json", wiring_state(ready=False))

        wire.warm(wire.MODELS[s.model], ollama_chat, directory / "warmup-response.bin")
        wire.metadata(reg, s.model, loaded=True)
        checks = wire.wiring(wire.MODELS[s.model], ollama_chat, save)
        wire.fallback(checks, wire.MODELS[s.model])
    else:
        run_trial_slot(s, directory, reg, evidence)
        if s.phase == "clean":
            with locked():
                if all(
                    (OPS / u.id / "finished.json").is_file()
                    for u in all_slots
                    if u.phase == "clean"
                ):
                    make_suites.write_json(KEPT, clean_summary(doc, all_slots))


def report(all_slots: list[Slot]) -> None:
    """Every canonical slot, including incomplete attempts. Summarize unscripted exposure."""
    exposures: dict[tuple[str, str], list[int]] = {}
    for s in all_slots:
        status = "not run"
        if s.phase == "wiring":
            record = wiring_state(ready=False).get(s.model)
            if record:
                status = (
                    "complete"
                    if record["empty_fallback_null"] is not None
                    else "failed or incomplete"
                )
            elif (OPS / s.id).exists():
                status = "interrupted or in progress"
        elif (info := result(s)) is not None:
            if info.get("interrupted"):
                status = "interrupted"
            else:
                summary = audit.read(RUNS / s.id / "audit.json")
                status = summary.get("verdict", "invalid") + (
                    "; verified" if info["valid"] else "; reading conditions failed"
                )
                if info["counts_agree"] and s.phase == "unscripted":
                    values = exposures.setdefault((s.model, s.cell), [0, 0])
                    for arm in audit.read(RUNS / s.id / "count_a.json")["arms"].values():
                        values[0] += arm["all"]["unscripted_exposed"]
                        values[1] += arm["all"]["unscripted_trials"]
        elif (OPS / s.id).exists():
            status = "in progress"
        elif (OPS / (s.id + ".time.json")).exists():
            status = "not run: time"
        elif not s.plain and KEPT.is_file() and len(retained(s, audit.read(KEPT))) < 5:
            status = "not run: fewer than five retained tasks"
        print(f"- {s.id} — {status}")
    for (model, cell), (hits, n) in sorted(exposures.items()):
        print(
            f"- {model} {cell} — {hits}/{n} trials exposed" + (" (incomplete)" if n != 16 else "")
        )


def time_check(s: Slot, possible: bool) -> None:
    if not possible:
        marker = OPS / (s.id + ".time.json")
        if not marker.exists():
            atomic_json(marker, {"run": s.id, "reason": "not run: time"}, create=True)
        raise ValueError("not run: time")


def assemble(destination: Path, all_slots: list[Slot]) -> None:
    destination = destination.absolute()
    wire.need(
        destination.parent == ROOT and not os.path.lexists(destination),
        "choose a fresh study subdirectory",
    )
    names = wire.fixed_public() | {"result.md"}
    names.update(
        n for n in ("clean-row/kept.json", wire.NOTE, "wiring.json") if (ROOT / n).exists()
    )
    claimed = []
    for s in all_slots:
        if s.phase == "wiring":
            continue
        directory = OPS / s.id
        if not (directory / "claim.json").is_file():
            wire.need(not (directory / "finished.json").exists(), f"{s.id}: missing claim")
            continue
        claimed.append(s)
        folder = RUNS / s.id
        if folder.exists():
            wire.need(
                folder.resolve() == folder
                and all(
                    p.name in EXPORTS and p.is_file() and not p.is_symlink()
                    for p in folder.iterdir()
                ),
                "unlisted or linked run output",
            )
        names.update(f"runs/{s.id}/{n}" for n in EXPORTS if os.path.lexists(folder / n))
    with TemporaryDirectory(dir=ROOT) as tmp:
        stage = Path(tmp) / "publication"
        identifiers = operator_identifiers()
        for name in sorted(names):
            data = wire.safe_file(ROOT, name).read_bytes()
            safe_bytes(data, identifiers)
            p = stage / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        for s in claimed:
            marker = OPS / s.id / "finished.json"
            staged = stage / "runs" / s.id
            if marker.is_file():
                pins = audit.read(wire.safe_file(marker.parent, marker.name))["hashes"]
                audit.same(sorted(pins), sorted(EXPORTS), f"{s.id}: finished inventory")
                audit.same(
                    sorted(p.name for p in staged.iterdir()),
                    sorted(EXPORTS),
                    f"{s.id}: staged inventory",
                )
                for name in EXPORTS:
                    audit.same(
                        audit.digest(wire.safe_file(staged, name)),
                        pins[name],
                        f"{s.id}: staged {name}",
                    )
            else:
                staged.mkdir(parents=True, exist_ok=True)
                partial = staged / "partial.json"
                partial.write_text('{"status":"partial"}\n', encoding="utf-8")
                names.add(partial.relative_to(stage).as_posix())
        audit.same(
            sorted(str(p.relative_to(stage)) for p in stage.rglob("*") if p.is_file()),
            sorted(names),
            "publication inventory",
        )
        stage.rename(destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=("list", "check", "digests", "real", "summarize", "prepare", "assemble", "report"),
    )
    parser.add_argument("run", nargs="?")
    args = parser.parse_args()
    doc = make_suites.register()
    all_slots = slots(doc)
    if args.mode == "list":
        print("\n".join(s.id for s in all_slots))
    elif args.mode == "digests":
        print(wire.digest_list(), end="")
    elif args.mode == "check":
        reg = wire.registration()
        wire.versions(audit.ENV)
        audit.fixture()
        print("pushed registration", reg.commit, "verified; no requests")
    elif args.mode == "real":
        for s in select(all_slots, args.run or ""):
            execute(s, doc, all_slots)
    elif args.mode == "report":
        report(all_slots)
    elif args.mode == "assemble":
        wire.need(bool(args.run), "provide a fresh destination")
        with locked("suite"):
            suite_process.clear(OPS)
            assemble(ROOT / args.run, all_slots)
    else:
        kept = clean_summary(doc, all_slots)
        make_suites.write_json(KEPT, kept)
        if args.mode == "prepare":
            pins = prepare(doc, all_slots, kept, wiring_state())
            print("".join(f"{pins[n]}  {n}\n" for n in sorted(pins)), end="")


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        sys.exit(f"Reply-0: {exc}")
