"""S3: does a current MCP client SDK interoperate with ARCI's stdio bridge?

Run from the repository root with an interpreter that has the official `mcp` SDK:

    PYTHONPATH=src <python> plan/exec/v2/spikes/s3/mcp_client_check.py

Starts `arci.mcp_toolset_server` on the recipe world and tries `tools/list` through the SDK's
high-level client in each connect mode. Prints one line per mode. Exit 0 if any mode works.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import os
import sys
import tempfile
from pathlib import Path

from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[5]
RECIPE = ROOT / "examples" / "recipes" / "mcp_agent"
MODES = ("auto", "legacy", "2026-07-28")


def _leaves(exc: BaseException) -> list[BaseException]:
    nested = getattr(exc, "exceptions", None)
    if not nested:
        return [exc]
    return [leaf for inner in nested for leaf in _leaves(inner)]


async def probe(mode: str) -> bool:
    with tempfile.TemporaryDirectory() as workdir:
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                "-P",
                "-m",
                "arci.mcp_toolset_server",
                "--toolset",
                "world:make_world",
                "--workdir",
                workdir,
                "--seed",
                "0",
                "--task-file",
                str(RECIPE / "task.json"),
            ],
            env={**os.environ, "PYTHONPATH": f"{ROOT / 'src'}{os.pathsep}{RECIPE}"},
        )
        try:
            async with Client(params, mode=mode, raise_exceptions=True) as client:
                listed = await client.list_tools()
        except BaseException as exc:  # the spike reports any failure verbatim
            for leaf in _leaves(exc):
                first_line = str(leaf).splitlines()[0] if str(leaf) else ""
                print(f"mode={mode} FAIL {type(leaf).__name__}: {first_line}")
            return False
        print(f"mode={mode} OK tools={[tool.name for tool in listed.tools]}")
        return True


def main() -> int:
    print(f"mcp SDK {importlib.metadata.version('mcp')}")
    worked = [asyncio.run(asyncio.wait_for(probe(mode), timeout=30)) for mode in MODES]
    return 0 if any(worked) else 1


if __name__ == "__main__":
    raise SystemExit(main())
