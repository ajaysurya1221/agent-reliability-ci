"""Section 12.2. Check seven Task C rows and refuse a real advertised hidden tool."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from probe import Server  # noqa: E402


class StubServer(Server):
    def close(self) -> None:
        self.stop()
        for stream in (self._process.stdout, self._process.stderr):
            if stream:
                stream.close()


class StubTests(unittest.TestCase):
    def test_seven_rows_and_hidden(self) -> None:
        with TemporaryDirectory() as folder:
            d = Path(folder)
            (d / "reply0-arm.json").write_text(
                json.dumps({"arm": "reply-as-given", "rules": "none", "server": "shipped"})
            )
            task = d / "task.json"
            task.write_text('{"key_id":"stub"}')
            cases = [
                ("no_is_error", "fine, but no isError key", False),
                ("notify_first", "fine, after a notification", False),
                ("ask_roots_first", "fine; roots/list was answered with an error", False),
                ("internal_error", "Internal error: the lookup table is locked", True),
                ("noise_line", "fine, after a line of noise", False),
                ("second_page_tool", "fine: second_page_tool", False),
                ("plain", "fine: plain", False),
            ]
            env = {**os.environ, "ARCI_WORKDIR": folder, "ARCI_TASK_FILE": str(task)}
            prefix = [sys.executable, "-P", str(ROOT / "harness/relay.py")]
            command = ["--", sys.executable, "-B", str(ROOT / "boundary-check/stub_server.py")]
            server = StubServer(prefix + command, env, None, 10)

            def rpc(method: str, params: dict[str, Any]) -> dict[str, Any]:
                _, reply, others, problem = server.request(method, params)
                self.assertIsNone(problem)
                self.assertEqual(others, [])
                assert reply is not None
                return reply

            try:
                rpc(
                    "initialize", {"capabilities": {"roots": {}, "sampling": {}, "elicitation": {}}}
                )
                server.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                tools = rpc("tools/list", {})["result"]
                self.assertNotIn("nextCursor", tools)
                self.assertEqual({r["name"] for r in tools["tools"]}, {c[0] for c in cases})
                for seq, (name, text, error) in enumerate(cases):
                    if name == "plain":
                        # A client iterating to exhaustion still sees the page-one tool.
                        self.assertNotIn("nextCursor", rpc("tools/list", {})["result"])
                    result = rpc("tools/call", {"name": name, "arguments": {}})["result"]
                    self.assertEqual(
                        result, {"content": [{"type": "text", "text": text}], "isError": error}
                    )
                    last = json.loads((d / "ledger.jsonl").read_bytes().splitlines()[-1])
                    self.assertEqual(
                        (last["record"], last["seq"], last["passed_on"]), ("call", seq, result)
                    )
                rows = [json.loads(line) for line in (d / "ledger.jsonl").read_bytes().splitlines()]
                self.assertEqual(
                    {r["code"] for r in rows if r["record"] == "norm"},
                    {"N1", "N2", "N3", "N4", "N5", "N6", "N8", "N9"},
                )
            finally:
                server.close()
            with TemporaryDirectory() as hidden:
                work = Path(hidden)
                (work / "reply0-arm.json").write_bytes((d / "reply0-arm.json").read_bytes())
                server = StubServer(
                    [*prefix, "--allow-tool", "plain", *command],
                    {**env, "ARCI_WORKDIR": hidden},
                    None,
                    10,
                )
                try:
                    rpc("initialize", {})
                    self.assertEqual(
                        [r["name"] for r in rpc("tools/list", {})["result"]["tools"]], ["plain"]
                    )
                    self.assertEqual(
                        rpc("tools/call", {"name": "noise_line", "arguments": {}})["error"]["code"],
                        -32601,
                    )
                    rows = [
                        json.loads(line)
                        for line in (work / "ledger.jsonl").read_bytes().splitlines()
                    ]
                    self.assertEqual(
                        rows[-1], {"record": "refused", "tool": "noise_line", "arguments": {}}
                    )
                    self.assertFalse(any(r["record"] == "call" for r in rows))
                finally:
                    server.close()

    def test_arm_file_required(self) -> None:
        for content in (None, "{", "{}", '{"arm":"clean","server":"unknown","rules":"none"}'):
            with self.subTest(content=content), TemporaryDirectory() as folder:
                d = Path(folder)
                if content is not None:
                    (d / "reply0-arm.json").write_text(content)
                proc = subprocess.run(
                    [
                        sys.executable,
                        "-P",
                        str(ROOT / "harness/relay.py"),
                        "--",
                        sys.executable,
                        "-B",
                        str(ROOT / "boundary-check/stub_server.py"),
                    ],
                    env={**os.environ, "ARCI_WORKDIR": folder},
                    input='{"jsonrpc":"2.0","method":"initialize","id":1}\n',
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertNotEqual(proc.returncode, 0)
                self.assertEqual(proc.stdout, "")
                self.assertEqual(json.loads((d / "ledger.jsonl").read_bytes())["record"], "error")
