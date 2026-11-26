"""One durable claim per canonical run and membership checks before loopback traffic."""

from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from common import LIST, NOTE, REG, ROOT, SPARES, Row, models, need, pin_name, read, schedule, sha
from inputs import descriptors, digests, file, outputs, sources
from suite_process import alive

CLAIMS = Path(os.environ.get("BOARD0_CLAIMS", "/private/var/tmp/arci-board0-claims"))
REF = "refs/remotes/origin/v2/phase0"


def git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(ROOT), *args], stdin=subprocess.DEVNULL, timeout=15
    )


def verify_blobs(commit: str, entries: str) -> None:
    for line in entries.splitlines():
        digest, name = line.split("  ", 1)
        try:
            blob = git("cat-file", "blob", f"{commit}:./{name}")
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"missing pushed blob: {name}") from exc
        need(sha(blob) == digest, f"pushed blob differs: {name}")


def registration() -> str:
    from importlib.metadata import version

    need(version("agent-reliability-ci") == "2.4.1", "ARCI 2.4.1 required")
    need(
        all(
            not p.resolve().is_relative_to(Path.home().resolve())
            for p in (ROOT, Path(os.environ["BOARD0_ENV"]))
        ),
        "neutral checkout and env required",
    )
    receipt = file(CLAIMS, "push-receipt.txt").read_text().strip()
    match = re.fullmatch(r"([0-9a-f]{40}) refs/heads/v2/phase0", receipt)
    need(match, "missing pushed branch receipt")
    assert match
    commit = match[1]
    need(git("merge-base", commit, REF).decode().strip() == commit, "unpublished registration")
    slots = models(ROOT / "models.json")
    for name, expected in [(LIST, digests(sources())), (NOTE, digests(descriptors(slots)))]:
        need(
            file(ROOT, name).read_text() == expected
            and git("cat-file", "blob", f"{commit}:./{name}") == expected.encode(),
            f"pushed digest list differs: {name}",
        )
        verify_blobs(commit, expected)
    reg = file(ROOT, REG).read_bytes()
    need(
        reg == git("cat-file", "blob", f"{commit}:./{REG}"), "registration differs from pushed blob"
    )
    need(b"PLACEHOLDER" not in reg and reg.strip(), "registration is a placeholder")
    return commit


def pin_record(claims: Path, slot: str) -> tuple[Row, bool]:
    run = pin_name(slot)
    need((claims / run / "finished.json").is_file(), f"unfinished pin {run}")
    record = read(file(claims, run + "/finished.json"))
    model = read(file(claims, run + "/claim.json"))["model"]
    need(
        record["run"] == run
        and type(record["ok"]) is bool
        and model["slot"] == slot
        and model["pin"] == run,
        f"invalid pin claim {run}",
    )
    return model, record["ok"]


def final_slots(slots: list[Row], claims: Path) -> list[Row]:
    originals = [pin_record(claims, m["slot"]) for m in slots]
    spares = iter(SPARES)
    result = []
    for original, passed in originals:
        model = original
        if not passed:
            spare = next(spares, None)
            if spare:
                substitute, passed = pin_record(claims, spare)
                if passed:
                    model = substitute | {"slot": original["slot"]}
            if not passed:
                model = original | {"vacant": True}
        result.append(model)
    return result


def order_guard(run: str, slots: list[Row], claims: Path, today: date) -> None:
    order = schedule(slots)
    need(run in order, "unregistered run")
    slot = run.split("-")[2]
    if "-pin2-" in run:
        need(not (claims / run).exists(), f"already claimed {run}")
        if slot in SPARES:
            failures = sum(not pin_record(claims, m["slot"])[1] for m in slots)
            need(failures >= int(slot[1:]), f"spare {slot} not required")
        return
    need(slots == final_slots(slots, claims), "roster differs from completed pins")
    vacant = {m["slot"] for m in slots if m.get("vacant")}
    need(slot not in vacant, f"vacant slot {slot}")
    for prev in order[: order.index(run)]:
        if "-pin2-" not in prev and prev.split("-")[2] not in vacant:
            need((claims / prev / "finished.json").is_file(), f"unfinished predecessor {prev}")
    if "-d2-" in run:
        first = read(claims / f"board0-d1-{slot}-clean" / "claim.json")
        need(today > date.fromisoformat(first["date"]), "day 2 requires a later local date")


def finished(run: str, claims: Path, commit: str, *, board: bool = False) -> None:
    record = read(file(claims, run + "/finished.json"))
    claim = read(file(claims, run + "/claim.json"))
    prior = claim["registration"]
    if board and "-pin2-" in run and commit != "FIFO stand-in":
        need(
            prior != commit and git("merge-base", prior, commit).decode().strip() == prior,
            "push amendment 2 before board tasks",
        )
        first = read(file(claims, pin_name("M1") + "/claim.json"))
        need(first["registration"] == prior, "corrected pin registrations differ")
    else:
        need(prior == commit, f"registration differs from prior claim {run}")
    need(record["files"] == digests(outputs(run)), f"completed evidence differs: {run}")
    if "-pin2-" in run:
        evidence = read(file(ROOT, outputs(run)[0]))
        need(
            evidence["run"] == run
            and evidence["model"] == claim["model"]
            and evidence["ok"] is record["ok"],
            f"pin evidence differs: {run}",
        )


def binding(task: object, side: str, seed: int, label: str, model: str, prompt: str) -> str:
    return sha(
        json.dumps(
            [task, side, seed, label, model, prompt], sort_keys=True, separators=(",", ":")
        ).encode()
    )


def active(run: str) -> Row:
    need(re.fullmatch(r"board0-(pin2-(?:M[1-5]|S[12])|d[12]-M[1-5]-(clean|E))", run), "invalid RUN")
    directory = CLAIMS / run
    active_suite = read(file(CLAIMS, "active-suite.json"))
    need(active_suite["claim"] == run and alive(active_suite["launcher"]), "inactive suite")
    with file(directory, "claim.json").open("rb") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise ValueError("inactive claim")
        claim = json.load(handle)
    need(
        claim["run"] == run
        and claim["token_sha256"] == sha(os.environ["BOARD0_TOKEN"].encode())
        and claim["registration_sha256"] == sha(file(ROOT, REG).read_bytes()),
        "claim binding",
    )
    return claim


def authorize_trial(receipt: Row, task: Any, model: str, prompt: str) -> None:
    run = receipt["run"]
    claim = active(run)
    directory = CLAIMS / run
    if run.endswith("-clean"):
        directory = directory / task["key_id"]
        name = f"clean/{run}/{task['key_id']}/descriptor.yaml"
    else:
        name = f"runs/{run}/descriptor.yaml"
    need(
        Path(os.environ["BOARD0_RECEIPTS"]).resolve() == directory / "receipts"
        and claim["descriptors"][name] == sha(file(ROOT, name).read_bytes())
        and binding(task, receipt["arci_arm"], receipt["seed"], receipt["arm"], model, prompt)
        in read(file(directory, "bindings.json")),
        "trial outside claimed schedule",
    )
