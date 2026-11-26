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

from common import LIST, NOTE, REG, ROOT, Row, models, need, read, schedule, sha
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


def order_guard(run: str, slots: list[Row], claims: Path, today: date) -> None:
    order = schedule(slots)
    need(run in order, "unregistered run")
    if "-pin-" in run:
        return
    for model in slots:
        need(
            (claims / f"board0-pin-{model['slot']}" / "finished.json").is_file(),
            "complete pins before board tasks",
        )
    slot = run.split("-")[2]
    pin = read(claims / f"board0-pin-{slot}" / "finished.json")
    need(pin["ok"] is True, "failed or missing model pin")
    for prev in order[: order.index(run)]:
        if "-pin-" not in prev:
            other = prev.split("-")[2]
            prior_pin = claims / f"board0-pin-{other}" / "finished.json"
            if prior_pin.is_file() and read(prior_pin)["ok"] is False:
                continue
            need((claims / prev / "finished.json").is_file(), f"unfinished predecessor {prev}")
    if "-d2-" in run:
        first = read(claims / f"board0-d1-{slot}-clean" / "claim.json")
        need(today > date.fromisoformat(first["date"]), "day 2 requires a later local date")


def finished(run: str, claims: Path, commit: str) -> None:
    record = read(file(claims, run + "/finished.json"))
    need(
        read(file(claims, run + "/claim.json"))["registration"] == commit,
        f"registration differs from prior claim {run}",
    )
    if record["ok"]:
        need(record["files"] == digests(outputs(run)), f"completed evidence differs: {run}")


def binding(task: object, side: str, seed: int, label: str, model: str, prompt: str) -> str:
    return sha(
        json.dumps(
            [task, side, seed, label, model, prompt], sort_keys=True, separators=(",", ":")
        ).encode()
    )


def active(run: str) -> Row:
    need(re.fullmatch(r"board0-(pin-M[1-5]|d[12]-M[1-5]-(clean|E))", run), "invalid RUN")
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
