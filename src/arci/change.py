"""Register and run a paired comparison using the released imported-outcomes rule."""

from __future__ import annotations

import errno
import hashlib
import json
import math
import os
import re
import select
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Generator, Sequence
from contextlib import ExitStack, closing, contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from fractions import Fraction
from io import BufferedReader
from pathlib import Path
from types import FrameType
from typing import Literal
from xml.etree import ElementTree

import yaml

from arci.convert import neutral_jsonl, stream_text
from arci.hashing import hash_bytes
from arci.importers import OutcomeValue, junit, promptfoo
from arci.outcome_report import TERMINAL_TASK_OVERFLOW, escape_terminal, render_terminal
from arci.outcome_schema import OutcomeDecision, OutcomeRule
from arci.outcomes import (
    decide_outcomes,
    input_format,
    load_rule,
    read_outcome_rows,
    rule_from_inventory,
    rule_of,
    rule_sha256,
)
from arci.schema import Verdict
from arci.suite_schedule import Arm, arm_order
from arci.suite_schema import SUITE_MAX_PAIRS, parse_rational
from arci.suite_stats import (
    check_rule_plan,
    default_max_rounds,
    earliest_block_round,
    earliest_pass_round,
    never_differs_pass_round,
)

ScoredFormat = Literal["junit", "csv", "jsonl"]
ChangeFormat = ScoredFormat | Literal["promptfoo"]
ASSUMPTIONS = """Conditions for the campaign bound:
Every round must rerun the agent with fresh answers. Matching outcomes alone cannot show a cache.
Pairs must be jointly independent across tasks and rounds. Each task's law must stay fixed.
Keep tasks, inputs, versions, grading and retry policy fixed. Grade both sides by the same rule.
Which side runs first must have no effect. Keep the registered order. Never omit or replace rounds.
Label infrastructure failures as errors.
Under these conditions at alpha 1/20, a wrong PASS and a wrong BLOCK each have probability
at most 2.5% over this campaign. PASS means the mean loss on these tasks is below the margin.
A wrong PASS occurs at or above that loss. A wrong BLOCK occurs at or below it."""


@contextmanager
def _directory(path: Path) -> Generator[int, None, None]:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        yield fd
    finally:
        os.close(fd)


@contextmanager
def _regular(directory: int, name: str) -> Generator[BufferedReader, None, None]:
    # Inspect a FIFO without waiting for a writer.
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    with open(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError(f"{name}: expected a regular file")
        yield stream


class _Cancelled(Exception):
    """Leave the campaign once the active launch has released its process group."""


@dataclass
class _Cancellation:
    signum: int = 0
    launch_active: bool = False

    def request(self, signum: int, frame: FrameType | None) -> None:
        if not self.signum:
            self.signum = signum
            # During spawn and cleanup, leave ownership of the group with _execute.
            if not self.launch_active:
                raise _Cancelled

    @contextmanager
    def listen(self) -> Generator[None, None, None]:
        with ExitStack() as restore:
            for sig in (signal.SIGINT, signal.SIGTERM):
                restore.callback(signal.signal, sig, signal.getsignal(sig))
                signal.signal(sig, self.request)
            yield


def _has_waitid() -> bool:
    return callable(getattr(os, "waitid", None)) and all(
        hasattr(os, name) for name in ("P_PID", "WEXITED", "WNOWAIT", "WNOHANG")
    )


def _require_exit_observer() -> None:
    if not _has_waitid() and not (
        callable(getattr(select, "kqueue", None))
        and callable(getattr(select, "kevent", None))
        and all(
            hasattr(select, name)
            for name in (
                "KQ_FILTER_PROC",
                "KQ_EV_ADD",
                "KQ_EV_ONESHOT",
                "KQ_NOTE_EXIT",
                "KQ_EV_ERROR",
            )
        )
    ):
        raise ValueError("unsupported platform: cannot wait for a child without reaping it")


def _exited(pid: int, timeout: float, cancellation: _Cancellation | None = None) -> bool:
    """Observe the leader without reaping it."""
    deadline = time.monotonic() + timeout
    if not _has_waitid():
        # Python 3.11 and 3.12 on macOS expose NOTE_EXIT but not waitid.
        with closing(select.kqueue()) as queue:
            event = select.kevent(
                pid,
                filter=select.KQ_FILTER_PROC,
                flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT,
                fflags=select.KQ_NOTE_EXIT,
            )
            changes = [event]
            while True:
                remaining = max(0.0, deadline - time.monotonic())
                events = queue.control(changes, 1, min(0.05, remaining))
                if events or remaining == 0 or (cancellation and cancellation.signum):
                    break
                changes = []
        if events and events[0].flags & select.KQ_EV_ERROR:
            error = events[0].data
            if error != errno.ESRCH:  # Already exited before registration.
                raise OSError(error, os.strerror(error))
        return bool(events)
    while not os.waitid(os.P_PID, pid, os.WEXITED | os.WNOWAIT | os.WNOHANG):
        remaining = deadline - time.monotonic()
        if remaining <= 0 or (cancellation and cancellation.signum):
            return False
        time.sleep(min(0.01, remaining))
    return True


def _linux_group_has_live_member(pgid: int) -> bool:
    # An orphan's new parent may never reap it. Such a member cannot run or write.
    for entry in Path("/proc").iterdir():
        if entry.name.isdecimal():
            try:
                fields = (entry / "stat").read_bytes().rsplit(b")", 1)[1].split()
            except (FileNotFoundError, ProcessLookupError):
                continue
            if int(fields[2]) == pgid and fields[0] not in (b"Z", b"X"):
                return True
    return False


def _signal_group(child: subprocess.Popen[bytes]) -> None:
    # The leader has never been polled or reaped, even if it has already exited.
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        # Darwin can return EPERM for a group containing just its zombie leader.
        # Require both an exited child and an empty group before accepting that case.
        if sys.platform != "darwin" or not _exited(child.pid, 0):
            raise
        # If a live member prevented signalling, the observation below fails closed.
        return


def _confirm_group_stopped(pgid: int) -> None:
    # Observation only from here on; the kernel is free to recycle pgid.
    deadline = time.monotonic() + 5
    while True:
        try:
            os.getpriority(os.PRIO_PGRP, pgid)
        except ProcessLookupError:
            return
        if sys.platform.startswith("linux") and not _linux_group_has_live_member(pgid):
            return
        if time.monotonic() >= deadline:
            raise ValueError("could not confirm launch process group stopped")
        time.sleep(0.01)


def _execute(
    argv: list[str],
    arm: Arm,
    number: int,
    directory: int,
    timeout: float,
    cancellation: _Cancellation,
    fmt: ChangeFormat,
) -> tuple[int, bool, str | None]:
    def new_file(name: str, flags: int) -> int:
        return os.open(name, flags, 0o666, dir_fd=directory)

    if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
        raise ValueError("launch cleanup requires the default SIGCHLD disposition")
    env = {**os.environ, "ARCI_CHANGE_ARM": arm, "ARCI_CHANGE_ROUND": str(number)}
    if fmt == "promptfoo":
        env["PROMPTFOO_FAILED_TEST_EXIT_CODE"] = "100"
    with (
        open(f"{arm}.stdout", "xb", opener=new_file) as stdout,
        open(f"{arm}.stderr", "xb", opener=new_file) as stderr,
        subprocess.Popen(
            argv,
            stdout=stdout,
            stderr=stderr,
            env=env,
            start_new_session=True,
        ) as child,
    ):
        try:
            timed_out = not _exited(child.pid, timeout, cancellation)
        except ChildProcessError:
            # An external reaper has taken the leader. Its numeric id is no longer ours.
            raise
        except BaseException:
            _signal_group(child)
            raise
        _signal_group(child)
        code = child.wait()
        try:
            _confirm_group_stopped(child.pid)
        except (OSError, ValueError) as exc:
            return code, timed_out, str(exc)
        return code, timed_out, None


@dataclass(frozen=True)
class CapturedResult:
    path: Path
    snapshot: Path
    digest: str  # Scored snapshot, also the original's digest for byte-identical copies.
    original_digest: str | None = None

    def verify(self) -> None:
        _verify_digest(self.path, self.original_digest or self.digest)
        _verify_digest(self.snapshot, self.digest)


def _verify_digest(path: Path, digest: str) -> None:
    with _directory(path.parent) as fd, _regular(fd, path.name) as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
            raise ValueError(f"results changed: {path}")


LaunchResult = tuple[CapturedResult, dict[str, OutcomeValue | None]]


Timestamp = str | tuple[bool, Fraction]


def _timestamp(value: str) -> Timestamp:
    try:
        instant = datetime.fromisoformat(value)
    except ValueError:
        return hash_bytes(value.encode())
    # fromisoformat validates the spelling but rounds down to microseconds. Retain the
    # full fractions of both the local second and the UTC offset when comparing instants.
    whole_seconds = (
        (instant.toordinal() * 24 + instant.hour) * 60 + instant.minute
    ) * 60 + instant.second
    offset = instant.utcoffset()
    seconds = Fraction(whole_seconds)
    if offset is not None:
        seconds -= int(offset.total_seconds())
    parts = re.fullmatch(
        r"(?:\d{4}-?(?:W\d{2}(?:-?\d)?|\d{2}-?\d{2}))."
        r"[\d:]+(?:[.,](?P<local>\d+))?"
        r"(?:(?P<sign>[+-])[\d:]+(?:[.,](?P<offset>\d+))?|Z)?",
        value,
        re.DOTALL,
    )
    if parts:
        if digits := parts["local"]:
            seconds += Fraction(Decimal("0." + digits))
        if digits := parts["offset"]:
            fraction = Fraction(Decimal("0." + digits))
            seconds += fraction if parts["sign"] == "-" else -fraction
    return offset is not None, seconds


@dataclass
class _Campaign:
    root: Path
    commands: dict[Arm, list[str]]
    fmt: ChangeFormat
    timeout: float
    cancellation: _Cancellation = field(default_factory=_Cancellation)
    timestamps: dict[Arm, set[Timestamp]] = field(
        default_factory=lambda: {"baseline": set(), "candidate": set()}
    )
    record: list[str] = field(default_factory=list)
    tasks: frozenset[str] | None = None
    registration: dict[Path, bytes] = field(default_factory=dict)
    earlier_decisions: dict[Path, str] = field(default_factory=dict)
    last_decision: tuple[Path, bytes] | None = None
    captures: list[CapturedResult] = field(default_factory=list)
    run_ids: set[str] = field(default_factory=set)
    tool_version: str | None = None
    completed_pairs: int = 0
    old_passes: int = 0
    new_passes: int = 0

    @property
    def scored_format(self) -> ScoredFormat:
        return "jsonl" if self.fmt == "promptfoo" else self.fmt

    def promptfoo_snapshot(self, raw: bytes, arm: Arm, digest: str) -> bytes:
        result = promptfoo.read(raw)
        if any(row.round is not None for row in result.rows):
            raise ValueError("promptfoo repeats are not allowed")
        if result.cache is not False:
            raise ValueError("runtimeOptions.cache must be false: use --no-cache")
        if not result.run_id:
            raise ValueError("missing or empty evalId")
        if not result.run_time:
            raise ValueError("missing or empty results.timestamp")
        if not result.tool_version:
            raise ValueError("missing or empty promptfoo tool version")
        if result.run_id in self.run_ids:
            raise ValueError("repeated promptfoo evalId")
        stamp = _timestamp(result.run_time)
        if stamp in self.timestamps[arm]:
            raise ValueError("repeated promptfoo timestamp")
        if self.tool_version is not None and result.tool_version != self.tool_version:
            raise ValueError("promptfoo tool version differs from discovery")
        self.run_ids.add(result.run_id)
        self.timestamps[arm].add(stamp)
        self.tool_version = result.tool_version
        return neutral_jsonl(result, digest)

    def register(self, name: str, content: str) -> None:
        path = self.root / name
        data = content.encode()
        with path.open("xb") as file:
            file.write(data)
        self.registration[path] = data

    def verify(self) -> None:
        for path, expected in self.registration.items():
            with _directory(path.parent) as directory, _regular(directory, path.name) as stream:
                if stream.read() != expected:
                    raise ValueError(f"registration changed: {path}")
        if self.last_decision is not None:
            path, data = self.last_decision
            with _directory(path.parent) as directory, _regular(directory, path.name) as stream:
                if stream.read() != data:
                    raise ValueError(f"decision changed: {path}")
        for path, digest in self.earlier_decisions.items():
            with _directory(path.parent) as directory, _regular(directory, path.name) as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                    raise ValueError(f"decision changed: {path}")

    def count_round(self, pairs: int, old: int, new: int) -> None:
        self.completed_pairs += pairs
        self.old_passes += old
        self.new_passes += new

    def verify_results(self) -> None:
        for capture in self.captures:
            capture.verify()

    def save_decision(self, number: int, data: bytes) -> None:
        self.verify()
        self.verify_results()
        path = self.root / f"round-{number:03d}" / "decision.json"
        with path.open("xb") as file:
            file.write(data)
        if self.last_decision is not None:
            prior_path, prior_data = self.last_decision
            self.earlier_decisions[prior_path] = hash_bytes(prior_data)
        self.last_decision = path, data

    def launch(self, arm: Arm, number: int) -> LaunchResult:
        directory = self.root / (f"round-{number:03d}" if number else "discovery")
        directory.mkdir(exist_ok=True)
        suffix = {"junit": "xml", "promptfoo": "json"}.get(self.fmt, self.fmt)
        path = directory / f"{arm}.{suffix}"
        argv = [arg.replace("{out}", str(path)) for arg in self.commands[arm]]
        label = f"{directory.name}/{arm}"
        with _directory(directory) as fd:
            try:
                os.stat(path.name, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ValueError(f"result existed before launch: {path}")
            self.verify()
            self.verify_results()
            status = description = "could not start"
            try:
                self.cancellation.launch_active = True
                try:
                    code, timed_out, cleanup_error = _execute(
                        argv, arm, number, fd, self.timeout, self.cancellation, self.fmt
                    )
                    status = str(code)
                finally:
                    self.cancellation.launch_active = False
                    if sig := self.cancellation.signum:
                        description = f"cancelled by {signal.Signals(sig).name} (exit {status})"
                        raise _Cancelled
                if timed_out:
                    status = f"timeout (exit {code})"
                    description = status
                    raise ValueError(f"{label}: {status}")
                accepted = (0, 100) if self.fmt == "promptfoo" else (0, 1)
                if code < 0:
                    description = f"terminated by signal {-code} (exit {code})"
                elif code in accepted:
                    description = f"{'success' if code == 0 else 'test failure'} (exit {code})"
                else:
                    description = f"unexpected exit {code}"
                if cleanup_error:
                    description += f" (cleanup failed: {cleanup_error})"
                    raise ValueError(f"{label}: {description}")
                if code not in accepted:
                    raise ValueError(f"{label}: exit {code}")
            finally:
                self.record.append(f"{label}: {description}")
                exit_fd = os.open(
                    f"{arm}.exit", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666, dir_fd=fd
                )
                with os.fdopen(exit_fd, "w") as file:
                    file.write(status + "\n")
                self.verify()
            if not os.path.samestat(os.fstat(fd), directory.lstat()):
                raise ValueError(f"launch directory replaced: {directory}")
            snapshot = path.with_suffix(
                f".snapshot.{'jsonl' if self.fmt == 'promptfoo' else suffix}"
            )

            def new_snapshot(name: str, flags: int) -> int:
                return os.open(name, flags, 0o600, dir_fd=fd)

            try:
                with _regular(fd, path.name) as source_file:
                    raw = source_file.read()
                original_digest = hash_bytes(raw)
                content = raw
                snapshot_digest = original_digest
                if self.fmt == "promptfoo":
                    try:
                        content = self.promptfoo_snapshot(raw, arm, original_digest)
                    except ValueError as exc:
                        raise ValueError(f"{label}: {exc}") from exc
                    snapshot_digest = hash_bytes(content)
                with open(snapshot.name, "xb", opener=new_snapshot) as target:
                    target.write(content)
                capture = CapturedResult(path, snapshot, snapshot_digest, original_digest)
            except FileNotFoundError as exc:
                raise ValueError(f"missing results file: {exc.filename}") from exc

        self.captures.append(capture)
        capture.verify()
        try:
            source = content.decode("utf-8-sig")
            fmt = self.scored_format
            if fmt == "junit":
                parsed = junit.read(
                    source, path=str(path), arm=arm, position=number, tasks=self.tasks, seen=set()
                )
                stamps = {
                    _timestamp(stamp)
                    for suite in ElementTree.fromstring(source).iter()
                    if suite.tag in {"testsuite", "testsuites"}
                    and (stamp := suite.get("timestamp")) is not None
                }
                if self.timestamps[arm] & stamps:
                    raise ValueError("repeated JUnit timestamp")
                self.timestamps[arm].update(stamps)
            else:
                parsed = read_outcome_rows(
                    source, fmt=fmt, path=str(path), arm=arm, position=number, tasks=self.tasks
                )
            if tuple(parsed.rounds) != (number,):
                raise ValueError(f"file round contradicts assigned round {number}")
        except Exception as exc:
            raise ValueError(f"{label}: {exc}") from exc
        return capture, {row.task_id: row.outcome for row in parsed.rows}


def discover_rule(
    snapshots: Sequence[Path],
    *,
    tasks: Sequence[str],
    digest: str,
    fmt: ScoredFormat,
    margin: str,
    max_rounds: int,
) -> OutcomeRule:
    """Register the inventory already parsed from the single discovery snapshot."""
    (snapshot,) = snapshots
    input_format(str(snapshot), fmt)
    _verify_digest(snapshot, digest)
    return rule_from_inventory(tasks, margin=margin, max_rounds=max_rounds)


def _register(discovery: LaunchResult, fmt: ScoredFormat, margin: str, cap: int) -> OutcomeRule:
    capture, outcomes = discovery
    discovered = discover_rule(
        [capture.snapshot],
        tasks=tuple(outcomes),
        digest=capture.digest,
        fmt=fmt,
        margin=margin,
        max_rounds=cap,
    )
    capture.verify()
    if discovered.tasks != tuple(sorted(outcomes)):
        raise ValueError("registered tasks differ from captured discovery ids")
    return discovered.model_copy(update={"fixed_before_runs": True})


def _assess_prefix(
    rule: OutcomeRule,
    rule_path: Path,
    fmt: ScoredFormat,
    prefix: list[dict[Arm, CapturedResult]],
    previous: OutcomeDecision | None,
    predecessor: Path | None,
) -> OutcomeDecision:
    paths: dict[Arm, list[Path]] = {"baseline": [], "candidate": []}
    digests: dict[str, str] = {}
    for pair in prefix:
        for arm, capture in pair.items():
            capture.verify()
            paths[arm].append(capture.snapshot)
            digests[str(capture.snapshot)] = capture.digest
    decision = decide_outcomes(
        rule_path, paths["baseline"], paths["candidate"], fmt=fmt, previous=predecessor
    )
    if not decision.history:
        raise ValueError(" ".join(decision.reasons))
    if (
        decision.rule_sha256 != rule_sha256(rule)
        or decision.previous_sha256 != (previous.record_sha256 if previous else None)
        or decision.last_round_evaluated != len(prefix)
        or decision.rounds_supplied != len(prefix)
    ):
        raise ValueError("unexpected rule, predecessor or round in decision")
    for item in decision.inputs:
        if digests.pop(item.path, None) != item.sha256:
            raise ValueError("scored bytes differ from captured results")
    if digests:
        raise ValueError("decision omitted captured results")
    return decision


def run_rounds(
    order: Sequence[tuple[Arm, Arm]],
    launch: Callable[[Arm, int], LaunchResult],
    rule: OutcomeRule,
    rule_path: Path,
    fmt: ScoredFormat,
    save: Callable[[int, bytes], None],
    count: Callable[[int, int, int], None],
) -> tuple[OutcomeDecision, bool]:
    prefix: list[dict[Arm, CapturedResult]] = []
    identical = True
    previous = None
    predecessor = None
    for number, arms in enumerate(order, 1):
        results: dict[Arm, LaunchResult] = {arm: launch(arm, number) for arm in arms}
        a, b = results["baseline"][1], results["candidate"][1]
        count(
            len(rule.tasks),
            sum(v == "pass" for v in a.values()),
            sum(v == "pass" for v in b.values()),
        )
        identical &= len(a) == len(rule.tasks) and a == b
        prefix.append({arm: result[0] for arm, result in results.items()})
        decision = _assess_prefix(rule, rule_path, fmt, prefix, previous, predecessor)
        save(number, (decision.model_dump_json(indent=2) + "\n").encode())
        predecessor = rule_path.parent / f"round-{number:03d}/decision.json"
        if decision.verdict is not Verdict.INCONCLUSIVE or number == len(order):
            return decision, identical
        previous = decision
    raise ValueError("empty round plan")


def _run(
    campaign: _Campaign,
    baseline: str,
    candidate: str,
    margin: str,
    cap: int | None,
    plan_only: bool,
    emit: Callable[[str], None],
) -> int:
    if cap is not None and not 1 <= cap <= SUITE_MAX_PAIRS:
        raise ValueError("--max-rounds must be between 1 and 100000")
    if not 0 < parse_rational(margin) < 1:
        raise ValueError("--margin must be in (0, 1)")
    ceiling = OutcomeRule.model_validate(
        {
            "schema_version": "arci-outcomes/1",
            "suite_id": "margin-check",
            "tasks": ["task"],
            "margin": margin,
            "max_rounds": SUITE_MAX_PAIRS,
            "fixed_before_runs": False,
        }
    )
    min_pairs = never_differs_pass_round(rule_of(ceiling))
    if min_pairs is None:
        raise ValueError(
            "--margin cannot establish PASS with all ties within 100000 registered pairs"
        )
    _require_exit_observer()
    discovery = campaign.launch("baseline", 0)
    if cap is None:
        # Each round contributes one pair per task to the all-ties floor.
        n = len(discovery[1])
        cap = max(default_max_rounds(n), (min_pairs + n - 1) // n)
    registered = _register(discovery, campaign.scored_format, margin, cap)
    rule_path = campaign.root / "rule.yaml"
    campaign.register(
        rule_path.name,
        yaml.safe_dump(registered.model_dump(mode="json", exclude_none=True), sort_keys=False),
    )
    rule = load_rule(rule_path)
    if rule != registered:
        raise ValueError("registered rule differs from captured discovery rule")
    digest = rule_sha256(rule)
    campaign.register("rule.sha256", digest + "\n")
    stats = rule_of(rule)
    warnings = check_rule_plan(stats)
    order = [arm_order(digest, 0, r) for r in range(1, rule.max_rounds + 1)]
    plan = dict(
        baseline=baseline,
        candidate=candidate,
        format=campaign.fmt,
        margin=rule.margin,
        max_rounds=rule.max_rounds,
        timeout_seconds=campaign.timeout,
        tasks=rule.tasks,
        rule_sha256=digest,
        arm_order=order,
    )
    if campaign.tool_version is not None:
        plan.update(
            reader=promptfoo.READER,
            scored_format=campaign.scored_format,
            tool_version=campaign.tool_version,
        )
    campaign.register("plan.json", json.dumps(plan, indent=2) + "\n")
    emit(
        f"arci check-change plan: {len(rule.tasks)} tasks, {rule.max_rounds} rounds, "
        f"at most {1 + 2 * rule.max_rounds} launches including discovery."
    )
    emit(f"Earliest PASS: round {earliest_pass_round(stats)} (all wins).")
    block = earliest_block_round(stats)
    when = "unreachable within cap" if block is None else f"round {block}"
    emit(f"Earliest BLOCK: {when} (all losses).")
    emit(
        f"PASS with all ties: round {never_differs_pass_round(stats)}. "
        "These are extremes, not estimates."
    )
    for warning in warnings:
        emit(warning)
    campaign.verify()
    if plan_only:
        campaign.verify_results()
        return 0

    campaign.tasks = frozenset(rule.tasks)
    decision, identical = run_rounds(
        order,
        campaign.launch,
        rule,
        rule_path,
        campaign.scored_format,
        campaign.save_decision,
        campaign.count_round,
    )
    campaign.verify()
    campaign.verify_results()
    emit("arci check-change verdict")
    n_tasks = len(rule.tasks)
    points = 100 * parse_rational(rule.margin)
    loss = rule.margin + (f", {points} points" if points.denominator == 1 else "")
    if decision.verdict is Verdict.PASS:
        emit(
            f"PASS: on these {n_tasks} tasks the new version is not worse than the old one by "
            f"more than the allowed loss of {loss}. It does not say the new version is better."
        )
    elif decision.verdict is Verdict.BLOCK:
        emit(
            f"BLOCK: on these {n_tasks} tasks the new version is worse than the old one by "
            f"more than the allowed loss of {loss}."
        )
    elif decision.verdict is Verdict.INCONCLUSIVE:
        emit(
            f"INCONCLUSIVE: after {decision.last_round_evaluated} rounds the runs do not decide "
            "either way. That is an answer, not a failure: there is not enough evidence yet."
        )
    else:
        emit(ERROR_SENTENCE)
    _pass_counts(campaign, emit)
    block_text = render_terminal(decision).rstrip("\n")
    emit(block_text)
    if re.search(r"^\d+" + re.escape(TERMINAL_TASK_OVERFLOW.format(n="")) + "$", block_text, re.M):
        emit(f"Full task table: round-{decision.last_round_evaluated:03d}/decision.json")
    if campaign.tool_version is not None:
        version = escape_terminal(campaign.tool_version)
        emit(
            f"Results from promptfoo {version}, read by {promptfoo.READER}. "
            "To check one: arci convert --from promptfoo round-001/baseline.json --out check.jsonl"
        )
    _launch_record(campaign, emit)
    emit(
        f"Absolute passes: baseline {sum(t.baseline_successes for t in decision.tasks)}, "
        f"candidate {sum(t.candidate_successes for t in decision.tasks)}."
    )
    if identical:
        emit(
            "Warning: identical outcomes for every task in every evaluated round. "
            "A deterministic command can reach PASS even when both sides always fail."
        )
    losses = [t for t in decision.tasks if t.counts.minus >= 2]
    if losses:
        emit("Tasks lost in two or more rounds:")
    for task in losses:
        emit(f"  {escape_terminal(task.task_id)}: {task.counts.minus} losses")
    return decision.exit_code


ERROR_SENTENCE = "ERROR: the campaign could not be completed, so there is no verdict."


def _pass_counts(campaign: _Campaign, emit: Callable[[str], None]) -> None:
    n = campaign.completed_pairs
    if n:
        emit(
            f"Old version passed {campaign.old_passes} of {n} task runs. "
            f"New version passed {campaign.new_passes} of {n}."
        )


def _launch_record(campaign: _Campaign, emit: Callable[[str], None]) -> None:
    if campaign.tool_version is not None and campaign.tool_version not in promptfoo.TESTED_VERSIONS:
        version = escape_terminal(campaign.tool_version)
        emit(f"Notice: {promptfoo.READER} was not tested with promptfoo version {version}.")
    emit("Launch record (discovery excluded from scoring):")
    for entry in campaign.record:
        emit("  " + entry)


def check_change(
    *,
    baseline: str,
    candidate: str,
    fmt: ChangeFormat,
    margin: str,
    max_rounds: int | None,
    timeout_seconds: float,
    out_dir: str | None,
    plan_only: bool,
) -> int:
    try:
        commands: dict[Arm, list[str]] = {
            "baseline": shlex.split(baseline),
            "candidate": shlex.split(candidate),
        }
        for arm, args in commands.items():
            if not any("{out}" in arg for arg in args):
                raise ValueError(f"--{arm} must contain {{out}}")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("--timeout-seconds must be positive and finite")
        if out_dir is None:
            parent = Path.cwd() / "arci-changes"
            parent.mkdir(exist_ok=True)
            root = Path(tempfile.mkdtemp(dir=parent))
        else:
            root = Path(out_dir).absolute()
            root.mkdir(parents=True)
    except (ValueError, OSError) as exc:
        print("arci check-change verdict")
        print(ERROR_SENTENCE)
        print(escape_terminal(str(exc)))
        return 3
    campaign = _Campaign(root, commands, fmt, timeout_seconds)
    with (root / "verdict.txt").open("x", encoding="utf-8") as transcript:

        def emit(line: str) -> None:
            print(line, file=transcript, flush=True)
            print(stream_text(line, sys.stdout), flush=True)

        try:
            with campaign.cancellation.listen():
                try:
                    code = _run(campaign, baseline, candidate, margin, max_rounds, plan_only, emit)
                    if plan_only:
                        _launch_record(campaign, emit)
                except (_Cancelled, ValueError, OSError) as exc:
                    # A final evidence check may also fail as a cancelled launch unwinds.
                    if not (sig := campaign.cancellation.signum):
                        raise
                    emit("ERROR: the campaign was cancelled, so there is no verdict.")
                    if not isinstance(exc, _Cancelled):
                        emit(escape_terminal(str(exc)))
                    _launch_record(campaign, emit)
                    code = 128 + sig
        except (ValueError, OSError) as exc:
            emit("arci check-change verdict")
            emit(ERROR_SENTENCE)
            _pass_counts(campaign, emit)
            emit("VERDICT: ERROR (exit 3)")
            emit(escape_terminal(str(exc)))
            _launch_record(campaign, emit)
            code = 3
        emit(ASSUMPTIONS)
        emit(f"Files in {escape_terminal(str(root))}:")

        def index_order(path: Path) -> tuple[str, int, Path]:
            folder = path.relative_to(root).parts[0]
            if match := re.fullmatch(r"round-([0-9]+)", folder):
                return "round-", int(match[1]), path
            return folder, 0, path

        for path in sorted(root.rglob("*"), key=index_order if fmt == "promptfoo" else None):
            if not path.is_dir():
                emit("  " + escape_terminal(str(path.relative_to(root))))
        return code
