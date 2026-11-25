"""Offline component test adapter for hosts denying AF_UNIX bind.

Supply a released TrialSpec, use the installed 2.4.1 boundary's request, reply, recording
and fault methods verbatim. Only its two client I/O endpoints are redirected to stdio.
This test adapter produces recordings, never a sealed trial or decision.
"""

from __future__ import annotations

import json
import sys
from importlib import import_module
from pathlib import Path
from typing import Any

from arci.perturb import build
from arci.schema import TrialSpec


class Output:
    def sendall(self, data: bytes) -> None:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()


def main(spec_path: Path, work: Path) -> None:
    spec = TrialSpec.model_validate_json(spec_path.read_bytes())
    module: Any = import_module("arci.mcp_boundary")
    if not spec.command or "--offline" not in spec.command.argv or spec.decisions:
        raise ValueError("pipe adapter requires a stand-in and no decision endpoint")
    with (work / "boundary-frames.jsonl").open("xb") as frames:
        module._PROTOCOL = frames
        boundary: Any = module._Boundary("offline", spec, "", str(work))
        boundary.perturbations = tuple(build(fault) for fault in spec.condition.faults)
        boundary.connection = Output()
        boundary._start_server()
        try:
            for line in sys.stdin.buffer:
                boundary._client_message(line)
                while boundary.pending:
                    raw = boundary.server.stdout.readline()
                    if not raw:
                        raise EOFError("relay closed its output")
                    boundary._server_message(raw)
                if boundary.latches.harness or boundary.latches.budget:
                    raise ValueError("released boundary latched a fault")
            (work / "recording.json").write_text(
                json.dumps([call.model_dump(mode="json") for call in boundary.recording])
            )
        finally:
            boundary.server.stdin.close()
            try:
                boundary.server.wait(timeout=5)
            finally:
                if boundary.server.poll() is None:
                    boundary.server.kill()
                    boundary.server.wait()
                boundary.server.stdout.close()
                boundary.selector.close()


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
