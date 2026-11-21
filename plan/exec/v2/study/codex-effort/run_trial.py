"""Run and grade one member of a pair. The campaign driver owns live starts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import traceback
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from events import Audit, Evidence, classify, inspect_stream
from grade import AGENT_PYTHON, Grade, Outcome, Ticket, bounded, export, grade, outside, run_process

Arm = Literal["baseline", "candidate"]
MODEL = "gpt-6.2-astra"
EFFORT = {"baseline": "xhigh", "candidate": "high"}
LIMIT = 20 * 60


def utc() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class Executable:
    launcher: str
    native: str
    executable_sha256: str
    native_executable_sha256: str


def executable_identity(env: dict[str, str]) -> Executable:
    selected = shutil.which(env.get("CODEX_BIN", "codex"), path=env.get("PATH"))
    if selected is None:
        raise FileNotFoundError("agent executable missing")
    launcher = Path(selected).resolve(strict=True)
    with launcher.open("rb") as stream:
        header = stream.read(256).split(b"\n", 1)[0]
        stream.seek(0)
        launcher_digest = hashlib.file_digest(stream, "sha256").hexdigest()
    native = launcher
    if header == b"#!/usr/bin/env node" and launcher.name == "codex.js":
        # Match this npm launcher's createRequire(import.meta.url), Node architecture,
        # optional platform package, and bundled-vendor fallback on the registered Mac.
        resolve = """
          const p = require('node:path');
          const req = require('node:module').createRequire(process.argv[1]);
          const arch = process.arch, cpu = {arm64:'aarch64', x64:'x86_64'}[arch];
          if (!cpu || process.platform !== 'darwin') throw Error('unregistered platform');
          let root = p.dirname(p.dirname(process.argv[1]));
          try { root = p.dirname(req.resolve('@openai/codex-darwin-' + arch + '/package.json')); }
          catch {}
          console.log(p.join(root, 'vendor', cpu + '-apple-darwin', 'bin', 'codex'));
        """
        proc = bounded(["node", "-e", resolve, str(launcher)], launcher.parent, env=env)
        proc.check_returncode()
        native = Path(proc.stdout.decode().strip()).resolve(strict=True)
    elif header.startswith(b"#!"):
        # Offline stand-ins directly name their native Python interpreter.
        if header != b"#!" + os.fsencode(AGENT_PYTHON):
            raise ValueError("cannot resolve this executable wrapper")
        native = AGENT_PYTHON.resolve(strict=True)
    native_digest = launcher_digest
    if native != launcher:
        with native.open("rb") as stream:
            native_digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return Executable(str(launcher), str(native), launcher_digest, native_digest)


def command(executable: str, arm: Arm, task: str, last_message: Path) -> list[str]:
    return [
        executable,
        "exec",
        "-m",
        MODEL,
        "-c",
        f'model_reasoning_effort="{EFFORT[arm]}"',
        "-s",
        "workspace-write",
        "-c",
        'approval_policy="never"',
        "--skip-git-repo-check",
        "--json",
        "--ephemeral",
        "-o",
        str(last_message),
        task,
    ]


@dataclass(frozen=True)
class Trial:
    ticket: str
    round: int
    arm: Arm
    effort: str
    order: int
    start_time: str
    seconds: float
    agent_seconds: float
    grade_seconds: float
    outcome: Outcome
    diff_sha256: str | None
    grader_evidence: str
    agent_exit: int | None
    service_marker: str | None
    terminal_event_id: str
    hit_time_limit: bool
    export_root: str | None
    audit: Audit
    executable_sha256: str | None
    native_executable_sha256: str | None


def run_trial(
    ticket: Ticket,
    arm: Arm,
    round_no: int,
    order: int,
    work_root: Path,
    out: Path,
    *,
    seconds: float = LIMIT,
    expected_executable: Executable | None = None,
) -> Trial:
    work_root = outside(work_root)
    key = f"r{round_no:02d}-{ticket['id']}-{arm}"
    record = out / key
    record.mkdir()
    log = work_root / (key + ".transcript")
    start, start_time = time.monotonic(), utc()
    evidence = Evidence(audit=Audit(status="unauditable"))
    export_root = None
    timed_out = False
    rc = None
    marker = None
    identity = expected_executable
    agent_seconds = grade_seconds = 0.0
    (record / "start.json").write_text(
        json.dumps(
            {
                "ticket": ticket["id"],
                "round": round_no,
                "arm": arm,
                "order": order,
                "start_time": start_time,
                "task_sha256": hashlib.sha256(ticket["task"].encode()).hexdigest(),
                **(asdict(expected_executable) if expected_executable else {}),
            }
        )
        + "\n"
    )
    try:
        with tempfile.TemporaryDirectory(prefix="trial-", dir=work_root) as tmp:
            tree = Path(tmp) / "work"
            export_root = str(tree.relative_to(work_root))
            export(ticket["pre_fix_commit"], tree)
            env = dict(os.environ)
            for inherited in (
                "OLDPWD",
                "GIT_DIR",
                "GIT_COMMON_DIR",
                "GIT_WORK_TREE",
                "GIT_INDEX_FILE",
                "GIT_OBJECT_DIRECTORY",
                "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            ):
                env.pop(inherited, None)
            env.update(
                PWD=str(tree),
                PYTHONNOUSERSITE="1",
                PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                PATH=str(AGENT_PYTHON.parent) + os.pathsep + env.get("PATH", os.defpath),
                VIRTUAL_ENV=str(AGENT_PYTHON.parent.parent),
                PYTHONDONTWRITEBYTECODE="1",
                PYTEST_ADDOPTS="-p no:cacheprovider",
                PYTHONPATH=str(tree / "src"),
                GIT_CEILING_DIRECTORIES=str(tree.parent),
                NO_COLOR="1",
            )
            failure = None
            try:
                identity = executable_identity(env)
                if expected_executable is not None and identity != expected_executable:
                    raise RuntimeError("agent executable differs from the campaign start")
                began = time.monotonic()
                try:
                    rc = run_process(
                        command(
                            identity.launcher,
                            arm,
                            ticket["task"],
                            work_root / (key + ".last.txt"),
                        ),
                        tree,
                        env,
                        log,
                        seconds,
                        stderr=work_root / (key + ".stderr"),
                    )
                finally:
                    agent_seconds = time.monotonic() - began
                timed_out = rc is None
            except FileNotFoundError:
                failure = Grade("error", "agent executable missing")
            evidence = inspect_stream(log, tree, work_root, env)
            if failure is None:
                failure, marker = classify(evidence, rc)
            began = time.monotonic()
            try:
                result = grade(ticket, tree, record, agent_failure=failure)
            finally:
                grade_seconds = time.monotonic() - began
    except Exception as exc:
        (record / "grader-error.log").write_text(traceback.format_exc())
        patch = record / "change.patch"
        digest = hashlib.sha256(patch.read_bytes()).hexdigest() if patch.exists() else None
        reason = str(exc) if isinstance(exc, subprocess.TimeoutExpired) else type(exc).__name__
        result = Grade("error", f"grader failure: {reason}", digest)
    trial = Trial(
        ticket["id"],
        round_no,
        arm,
        EFFORT[arm],
        order,
        start_time,
        round(time.monotonic() - start, 3),
        round(agent_seconds, 3),
        round(grade_seconds, 3),
        result.outcome,
        result.diff_sha256,
        result.reason,
        rc,
        marker,
        evidence.terminal_id,
        timed_out,
        export_root,
        evidence.audit,
        identity.executable_sha256 if identity else None,
        identity.native_executable_sha256 if identity else None,
    )
    (record / "grade.json").write_text(json.dumps(asdict(trial), indent=2) + "\n")
    return trial
