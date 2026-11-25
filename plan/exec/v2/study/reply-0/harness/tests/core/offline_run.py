"""Run released ARCI with local FIFOs in place of its Unix listener, for stand-ins only.

The released parent still launches and supervises the agent and grader, consumes protocol
frames, seals each trial, orders pairs, stops the suite and writes its decision.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from contextlib import ExitStack
from functools import partial
from importlib import import_module
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from typing import Any, BinaryIO
from unittest.mock import patch

HERE = Path(__file__).resolve()
STUDY = HERE.parents[3]


class PipeOutput:
    def __init__(self, stream: BinaryIO) -> None:
        self.stream = stream

    def sendall(self, data: bytes) -> None:
        self.stream.write(data)
        self.stream.flush()

    def close(self) -> None:
        self.stream.close()


def shim(work: Path) -> None:
    # Reply-0 uses serial requests. Notifications have no corresponding response.
    with (work / "client.fifo").open("wb") as sent, (work / "reply.fifo").open("rb") as replies:
        for line in sys.stdin.buffer:
            sent.write(line)
            sent.flush()
            if "id" in json.loads(line):
                reply = replies.readline()
                if not reply:
                    raise EOFError("boundary closed before reply")
                sys.stdout.buffer.write(reply)
                sys.stdout.buffer.flush()


def boundary() -> None:
    from arci.perturb import build

    module: Any = import_module("arci.mcp_boundary")
    nonce, spec, socket_name, folder, _, _, deadline = module._read_config()
    work = Path(folder)
    if not spec.command or "--offline" not in spec.command.argv or spec.decisions:
        raise ValueError("local pipe rehearsal requires an offline agent and no decision endpoint")
    engine = module._Boundary(nonce, spec, socket_name, folder, deadline=deadline)
    engine.emitter.emit(
        "trial_start", {"seed": spec.seed, "arm": spec.arm, "variant": spec.variant}
    )
    try:
        engine.perturbations = tuple(build(f) for f in spec.condition.faults)
        engine._start_server()
        for path in ("client.fifo", "reply.fifo"):
            os.mkfifo(work / path, 0o600)
        config = work / "mcp.json"
        mcp = json.loads(config.read_bytes())
        (server,) = mcp["mcpServers"].values()
        server["args"] = ["-B", str(HERE), "shim", folder]
        config.write_text(json.dumps(mcp))
        module._frame(nonce, "ready")
        with (work / "client.fifo").open("rb") as client, (work / "reply.fifo").open("wb") as out:
            engine.connection = PipeOutput(out)
            for line in client:
                engine._client_message(line)
                while engine.pending:
                    reply = engine.server.stdout.readline()
                    if not reply:
                        raise EOFError("relay closed before reply")
                    engine._server_message(reply)
    except Exception as exc:
        engine.latches.set_harness(exc)
    finally:
        engine._cleanup()
    engine.write_result()


def run(descriptor: Path, output: Path) -> int:
    from arci import cli, runner

    if version("agent-reliability-ci") != "2.4.1":
        raise ValueError("offline adapter requires released ARCI 2.4.1")
    config = json.loads(descriptor.read_bytes())
    for side in ("baseline", "candidate"):
        argv = config[side]["command"]["argv"]
        if "--offline" not in argv or not (
            argv[1:4] == ["-P", "-m", "agent"]
            or argv[1:3] == ["-P", str(STUDY / "harness/agent.py")]
        ):
            raise ValueError("both arms must use the study agent with a stand-in plan")
    temp = Path(tempfile.gettempdir()).resolve()
    if not temp.is_relative_to(STUDY) or not output.resolve().is_relative_to(STUDY):
        raise ValueError("rehearsal work and stores must stay in the study directory")

    def launch(argv: list[str], **kwargs: Any) -> subprocess.Popen[Any]:
        if argv == [sys.executable, "-P", "-m", "arci.mcp_boundary"]:
            argv = [sys.executable, "-B", str(HERE), "boundary"]
        return subprocess.Popen(argv, **kwargs)

    def workdir(*, prefix: str, dir: str) -> str:
        return tempfile.mkdtemp(prefix=prefix, dir=temp)

    processes = SimpleNamespace(**vars(subprocess))
    processes.Popen = launch
    with (
        patch.object(runner, "subprocess", processes),
        patch.object(runner, "tempfile", SimpleNamespace(mkdtemp=workdir)),
    ):
        return cli.main(["run", "--workers", "1", "--out", str(output), str(descriptor)])


def matrix(env: Path, out: Path, pipes: bool = True) -> int:
    """Use the task checker's existing schedule, seal, delivery and grading assertions."""
    sys.path.insert(0, str(STUDY))
    from harness.clean_row import safe_bytes
    from harness.tests.core.check_privacy import scan
    from harness.wiring_check import registered_node
    from tasks import check_tasks

    node = str(registered_node(env))
    original_session = check_tasks.Session

    def session(command: list[str], environ: dict[str, str]) -> Any:
        argv = [node if arg == "node" else arg for arg in command]
        return original_session(argv, environ)

    scanned: Counter[str] = Counter()
    neutral = env == Path("/Users/Shared/arci-reply0/env")

    def invoke(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        if argv[:7] == [sys.executable, "-P", "-m", "arci", "run", "--workers", "1"]:
            if len(argv) != 10 or argv[7] != "--out":
                raise ValueError("unexpected task checker run command")
            descriptor = Path(argv[9])
            result = subprocess.run(
                [sys.executable, "-B", str(HERE), argv[9], argv[8]] if pipes else argv, **kwargs
            )
            if neutral:
                scanned.update(scan(descriptor.parent))
            return result
        if argv[0] == "git":
            kwargs.setdefault("timeout", 15)
        return subprocess.run(argv, **kwargs)

    processes = SimpleNamespace(**vars(subprocess))
    processes.run = invoke
    check_edits = check_tasks.check_server_edits

    def verify_edits(env_dir: Path, fx: Path, work: Path, doc: Any) -> None:
        check_edits(env_dir, fx, work, doc)
        ledgers = sorted(work.glob("*/ledger.jsonl"))
        if len(ledgers) != 9:
            raise ValueError("missing edit parity ledgers")
        for ledger in ledgers:
            safe_bytes(ledger.read_bytes(), {os.environ["HOME"].casefold()})
        scanned["edit parity ledgers"] += len(ledgers)

    with ExitStack() as stack:
        stack.enter_context(patch.object(check_tasks, "Session", side_effect=session))
        stack.enter_context(patch.object(check_tasks, "subprocess", processes))
        if neutral:
            stack.enter_context(
                patch.object(
                    check_tasks, "relay_argv", partial(check_tasks.relay_argv, portable=True)
                )
            )
            stack.enter_context(patch.object(check_tasks, "check_server_edits", verify_edits))
        status = check_tasks.main(["check_tasks.py", str(env), str(out)])
    if neutral:
        if scanned["descriptors"] != 216 or scanned["receipts and ledgers"] != 432:
            raise ValueError("privacy scan did not cover the full 72-task matrix")
        print("Temporary matrix HOME scan clean:", dict(scanned))
    return status


if __name__ == "__main__":
    if sys.argv[1] == "boundary":
        boundary()
    elif sys.argv[1] == "shim":
        shim(Path(sys.argv[2]))
    elif sys.argv[1] in ("matrix", "native-matrix"):
        raise SystemExit(matrix(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[1] == "matrix"))
    else:
        raise SystemExit(run(Path(sys.argv[1]), Path(sys.argv[2])))
